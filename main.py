"""
Faculty Workload and Scheduling Application
--------------------------------------------
A PyQt5-based desktop app to manage faculty workloads, course assignments,
and scheduling with conflict detection, data persistence via SQLite,
and PDF/CSV export.

Features: semester/term management, in-place editing, bulk import from CSV,
room/location tracking, weekly schedule view, dark/light theme toggle.

Author: Ulysses Cabayao, SJ (uscabayaosj@addu.edu.ph)
"""

import sys
import os
import datetime
import logging
import tempfile
import sqlite3
import csv
from copy import deepcopy

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QFileDialog, QStyleFactory,
    QHeaderView, QMenu, QAbstractItemView, QCheckBox, QGroupBox,
    QFrame, QGridLayout, QSplitter, QDialog, QDialogButtonBox,
    QFormLayout, QDateEdit, QTabWidget, QTextEdit, QSizePolicy,
    QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, QDate
from PyQt5.QtGui import QFont, QPalette, QColor, QBrush, QIcon
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOG_PATH = os.path.join(os.path.expanduser('~'), 'faculty_app_debug.log')

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        filename=LOG_PATH,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

setup_logging()
log = logging.getLogger(__name__)
log.info("Application starting — Python %s", sys.version)

# ---------------------------------------------------------------------------
# Temp directory setup (relevant when frozen via PyInstaller)
# ---------------------------------------------------------------------------

def get_temp_dir():
    if getattr(sys, 'frozen', False):
        bundle_dir = sys._MEIPASS
    else:
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
    custom_temp_dir = os.path.join(bundle_dir, 'temp')
    try:
        os.makedirs(custom_temp_dir, exist_ok=True)
    except OSError:
        custom_temp_dir = tempfile.gettempdir()
    os.environ['TMPDIR'] = custom_temp_dir
    tempfile.tempdir = custom_temp_dir
    return custom_temp_dir

custom_temp_dir = get_temp_dir()
log.info("Temp directory: %s", custom_temp_dir)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLASSIFICATIONS = ["Full-time PhD", "Full-time MA", "Part-time"]
YEAR_LEVELS = ["BA 1", "BA 2", "BA 3", "BA 4", "MA 1", "MA 2"]
UNIT_OPTIONS = ["3", "6"]
SCHEDULE_SLOTS = [
    "MW 07:40am-09:10am", "MW 09:20am-10:50am", "MW 12:25pm-01:55pm", "MW 02:05pm-03:35pm",
    "TTh 07:40am-09:10am", "TTh 09:20am-10:50am", "TTh 12:25pm-01:55pm", "TTh 02:05pm-03:35pm",
    "TTh 03:45pm-05:15pm", "TTh 05:50pm-07:20pm", "TTh 07:30pm-09:00pm",
    "Sat 09:00am-12:00pm", "Sat 01:00pm-04:00pm", "Sat 05:00pm-08:00pm",
]
# Day headers for weekly schedule
DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAY_CODES = {"MW": (0, 2), "TTh": (1, 3), "Sat": (4,)}
# Ordered timeslots for schedule view (extract unique time ranges)
UNIQUE_TIMES = sorted(set(s.split(None, 1)[1] for s in SCHEDULE_SLOTS if ' ' in s),
                      key=lambda t: datetime.datetime.strptime(t.split('-')[0].strip(), "%I:%M%p"))

# Theme palettes
DARK_PALETTE = {
    'window': QColor(53, 53, 53), 'windowText': Qt.white,
    'base': QColor(25, 25, 25), 'alternateBase': QColor(53, 53, 53),
    'toolTipBase': Qt.white, 'toolTipText': Qt.white,
    'text': Qt.white, 'button': QColor(53, 53, 53), 'buttonText': Qt.white,
    'brightText': Qt.red, 'link': QColor(42, 130, 218),
    'highlight': QColor(42, 130, 218), 'highlightedText': Qt.black,
}
LIGHT_PALETTE = {
    'window': QColor(240, 240, 240), 'windowText': Qt.black,
    'base': Qt.white, 'alternateBase': QColor(233, 231, 227),
    'toolTipBase': QColor(255, 255, 220), 'toolTipText': Qt.black,
    'text': Qt.black, 'button': QColor(240, 240, 240), 'buttonText': Qt.black,
    'brightText': Qt.red, 'link': QColor(0, 0, 255),
    'highlight': QColor(42, 130, 218), 'highlightedText': Qt.white,
}

# Status colours
STATUS_COLORS = {
    'under': QColor(255, 235, 59),       # amber
    'on_target': QColor(76, 175, 80),    # green
    'over': QColor(244, 67, 54),         # red
    'part_time': QColor(158, 158, 158),  # grey
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Semester:
    __slots__ = ('name', 'is_active', '_id')
    def __init__(self, name, is_active=False, db_id=None):
        self.name = name
        self.is_active = is_active
        self._id = db_id

class Course:
    __slots__ = ('name', 'year_level', 'units', 'schedule', 'room', 'semester_id', '_id')

    def __init__(self, name, year_level, units, schedule, room='', semester_id=None, db_id=None):
        self.name = name
        self.year_level = year_level
        self.units = units
        self.schedule = schedule
        self.room = room
        self.semester_id = semester_id
        self._id = db_id

class Faculty:
    __slots__ = ('name', 'classification', 'is_admin', 'courses', 'required_load', '_id')

    def __init__(self, name, classification, is_admin=False, db_id=None):
        self.name = name
        self.classification = classification
        self.is_admin = is_admin
        self.courses = []
        self.required_load = self.calculate_required_load()
        self._id = db_id

    def calculate_required_load(self):
        if self.classification == "Full-time PhD":
            return 15 - (12 if self.is_admin else 0)
        elif self.classification == "Full-time MA":
            return 18 - (12 if self.is_admin else 0)
        return 0

    def current_load(self):
        return sum(c.units for c in self.courses)

    def load_delta(self):
        return self.current_load() - self.required_load

    def load_status(self):
        delta = self.load_delta()
        if delta < 0:
            return f"Under by {-delta} unit{'s' if -delta != 1 else ''}"
        elif delta > 0:
            return f"Over by {delta} unit{'s' if delta != 1 else ''}"
        return "On target" if self.required_load > 0 else "N/A (PT)"

    def load_status_category(self):
        if self.required_load == 0:
            return 'part_time'
        delta = self.load_delta()
        if delta < 0:
            return 'under'
        elif delta > 0:
            return 'over'
        return 'on_target'

# ---------------------------------------------------------------------------
# Database manager
# ---------------------------------------------------------------------------

class Database:
    def __init__(self, db_path='faculty_workload.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        log.info("Database opened: %s", db_path)

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                classification TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                semester_id INTEGER,
                name TEXT NOT NULL,
                year_level TEXT NOT NULL,
                units INTEGER NOT NULL,
                schedule TEXT NOT NULL,
                room TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
                FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_courses_faculty ON courses(faculty_id);
            CREATE INDEX IF NOT EXISTS idx_courses_semester ON courses(semester_id);
        """)
        self.conn.commit()
        # Ensure at least one semester exists
        cur = self.conn.execute("SELECT COUNT(*) FROM semesters")
        if cur.fetchone()[0] == 0:
            year = datetime.date.today().year
            self.conn.execute(
                "INSERT INTO semesters (name, is_active) VALUES (?, 1)",
                (f"AY {year}-{year+1} Sem 1",)
            )
            self.conn.commit()
            log.info("Created default semester")

    # -- Semester CRUD ------------------------------------------------------

    def load_semesters(self):
        rows = self.conn.execute("SELECT * FROM semesters ORDER BY name").fetchall()
        return [Semester(r['name'], bool(r['is_active']), r['id']) for r in rows]

    def add_semester(self, name, is_active=False):
        cur = self.conn.execute(
            "INSERT INTO semesters (name, is_active) VALUES (?, ?)",
            (name, int(is_active))
        )
        self.conn.commit()
        return cur.lastrowid

    def set_active_semester(self, semester_id):
        self.conn.execute("UPDATE semesters SET is_active=0")
        self.conn.execute("UPDATE semesters SET is_active=1 WHERE id=?", (semester_id,))
        self.conn.commit()

    def delete_semester(self, semester_id):
        # Move courses to null semester first
        self.conn.execute("UPDATE courses SET semester_id=NULL WHERE semester_id=?", (semester_id,))
        self.conn.execute("DELETE FROM semesters WHERE id=?", (semester_id,))
        self.conn.commit()

    # -- Faculty CRUD -------------------------------------------------------

    def load_all_faculty(self):
        rows = self.conn.execute("SELECT * FROM faculty ORDER BY name").fetchall()
        return [Faculty(r['name'], r['classification'], bool(r['is_admin']), r['id'])
                for r in rows]

    def load_courses_for_semester(self, semester_id, faculty_list):
        """Load courses for a given semester into the faculty_list objects."""
        if not faculty_list:
            return
        # Build faculty_id -> Faculty map
        fac_map = {f._id: f for f in faculty_list}
        rows = self.conn.execute(
            "SELECT * FROM courses WHERE semester_id=? ORDER BY name",
            (semester_id,)
        ).fetchall()
        for r in rows:
            c = Course(r['name'], r['year_level'], r['units'],
                       r['schedule'], r['room'], r['semester_id'], r['id'])
            if r['faculty_id'] in fac_map:
                fac_map[r['faculty_id']].courses.append(c)

    def add_faculty(self, faculty):
        cur = self.conn.execute(
            "INSERT INTO faculty (name, classification, is_admin) VALUES (?, ?, ?)",
            (faculty.name, faculty.classification, int(faculty.is_admin))
        )
        self.conn.commit()
        faculty._id = cur.lastrowid
        return faculty._id

    def update_faculty(self, faculty):
        self.conn.execute(
            "UPDATE faculty SET name=?, classification=?, is_admin=? WHERE id=?",
            (faculty.name, faculty.classification, int(faculty.is_admin), faculty._id)
        )
        self.conn.commit()

    def delete_faculty(self, faculty_id):
        self.conn.execute("DELETE FROM faculty WHERE id=?", (faculty_id,))
        self.conn.commit()

    def delete_faculty_by_name(self, name):
        cur = self.conn.execute("SELECT id FROM faculty WHERE name=?", (name,))
        row = cur.fetchone()
        if row:
            self.delete_faculty(row['id'])

    # -- Course CRUD --------------------------------------------------------

    def add_course(self, faculty_id, course):
        cur = self.conn.execute(
            "INSERT INTO courses (faculty_id, semester_id, name, year_level, units, schedule, room) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (faculty_id, course.semester_id, course.name, course.year_level,
             course.units, course.schedule, course.room)
        )
        self.conn.commit()
        course._id = cur.lastrowid
        return course._id

    def update_course(self, course):
        self.conn.execute(
            "UPDATE courses SET name=?, year_level=?, units=?, schedule=?, room=? WHERE id=?",
            (course.name, course.year_level, course.units, course.schedule, course.room, course._id)
        )
        self.conn.commit()

    def delete_course(self, course_id):
        self.conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()
        log.info("Database closed.")

# ---------------------------------------------------------------------------
# Weekly Schedule Dialog
# ---------------------------------------------------------------------------

class WeeklyScheduleDialog(QDialog):
    """A dialog that shows a weekly timetable grid for all faculty."""

    TIMESLOT_LABELS = [
        "07:40am-09:10am", "09:20am-10:50am", "12:25pm-01:55pm",
        "02:05pm-03:35pm", "03:45pm-05:15pm", "05:50pm-07:20pm", "07:30pm-09:00pm",
    ]

    def __init__(self, faculty_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Weekly Schedule View")
        self.resize(1100, 700)

        layout = QVBoxLayout(self)

        # Faculty filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Show faculty:"))
        self.fac_filter = QComboBox()
        self.fac_filter.addItem("All Faculty")
        for f in faculty_list:
            self.fac_filter.addItem(f.name)
        self.fac_filter.currentIndexChanged.connect(self._rebuild)
        filter_layout.addWidget(self.fac_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Scroll area for timetable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.timetable_widget = QWidget()
        self.timetable_layout = QVBoxLayout(self.timetable_widget)
        scroll.setWidget(self.timetable_widget)
        layout.addWidget(scroll)

        self.faculty_list = faculty_list
        self._rebuild()

    def _rebuild(self):
        # Clear old content
        while self.timetable_layout.count():
            child = self.timetable_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        filter_name = self.fac_filter.currentText()
        if filter_name == "All Faculty":
            fac_list = self.faculty_list
        else:
            fac_list = [f for f in self.faculty_list if f.name == filter_name]

        if not fac_list:
            self.timetable_layout.addWidget(QLabel("No faculty data to display."))
            return

        # Build grid: rows = timeslots, columns = Mon/Tue/Wed/Thu/Fri/Sat
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

        # Collect all courses per (day_index, timeslot)
        grid = {}
        for f in fac_list:
            for c in f.courses:
                if ' ' not in c.schedule:
                    continue
                day_code, time_slot = c.schedule.split(None, 1)
                day_indices = DAY_CODES.get(day_code, ())
                for di in day_indices:
                    key = (di, time_slot)
                    grid.setdefault(key, []).append((f.name, c))

        # Create the table
        table = QTableWidget()
        table.setColumnCount(len(days) + 1)  # +1 for timeslot label
        table.setRowCount(len(self.TIMESLOT_LABELS))
        table.setHorizontalHeaderLabels(["Time"] + days)

        # Map timeslot to row
        for row, ts in enumerate(self.TIMESLOT_LABELS):
            table.setItem(row, 0, QTableWidgetItem(ts))
            for col in range(1, len(days) + 1):
                di = col - 1
                key = (di, ts)
                entries = grid.get(key, [])
                if entries:
                    text = "\n".join(f"{fac}: {c.name} ({c.room or 'no room'})"
                                     for fac, c in entries)
                    item = QTableWidgetItem(text)
                    item.setBackground(QColor(66, 133, 244, 80))
                    table.setItem(row, col, item)
                else:
                    table.setItem(row, col, QTableWidgetItem(""))

        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.timetable_layout.addWidget(table)

# ---------------------------------------------------------------------------
# Add Semester Dialog
# ---------------------------------------------------------------------------

class AddSemesterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Semester / Term")
        self.setModal(True)
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        year = datetime.date.today().year
        self.name_edit.setPlaceholderText(f"e.g. AY {year}-{year+1} Sem 2")
        layout.addRow("Semester name:", self.name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_name(self):
        return self.name_edit.text().strip()

# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class FacultyWorkloadApp(QMainWindow):
    def __init__(self):
        log.info("Initialising FacultyWorkloadApp …")
        super().__init__()
        self.setWindowTitle("Faculty Workload & Scheduling")
        self.setGeometry(100, 100, 1200, 900)

        self.db = Database()

        # Load semesters
        self.semesters = self.db.load_semesters()
        self.active_semester = next((s for s in self.semesters if s.is_active), None)
        if not self.active_semester and self.semesters:
            self.active_semester = self.semesters[0]

        # Load faculty (all, cross-semester)
        self.faculty_list = self.db.load_all_faculty()

        # Load courses for active semester only
        if self.active_semester:
            self.db.load_courses_for_semester(self.active_semester._id, self.faculty_list)

        self._is_dark = True
        self._suppress_cell_change = False  # guard against recursive cell edits

        self._init_ui()
        self._refresh_all()
        log.info("Initialisation complete.")

    # -- UI construction ----------------------------------------------------

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)

        # --- Top bar: semester + theme toggle + bulk import ---
        top_bar = QHBoxLayout()

        top_bar.addWidget(QLabel("Semester:"))
        self.semester_sel = QComboBox()
        self._populate_semester_sel()
        self.semester_sel.currentIndexChanged.connect(self._on_semester_changed)
        top_bar.addWidget(self.semester_sel)

        self.add_sem_btn = QPushButton("+ New Semester")
        self.add_sem_btn.clicked.connect(self._add_semester)
        self.add_sem_btn.setMaximumWidth(120)
        top_bar.addWidget(self.add_sem_btn)

        self.del_sem_btn = QPushButton("Delete Semester")
        self.del_sem_btn.clicked.connect(self._delete_semester)
        self.del_sem_btn.setMaximumWidth(120)
        top_bar.addWidget(self.del_sem_btn)

        top_bar.addStretch()

        self.import_btn = QPushButton("Import CSV…")
        self.import_btn.clicked.connect(self._bulk_import)
        top_bar.addWidget(self.import_btn)

        self.schedule_btn = QPushButton("Weekly Schedule")
        self.schedule_btn.clicked.connect(self._show_weekly_schedule)
        top_bar.addWidget(self.schedule_btn)

        self.theme_btn = QPushButton("☀ Light")
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.theme_btn.setMaximumWidth(80)
        top_bar.addWidget(self.theme_btn)

        main_layout.addLayout(top_bar)

        # --- Input section (faculty + course side-by-side) ---
        input_split = QSplitter(Qt.Horizontal)

        # Left: Faculty input
        fac_group = QGroupBox("Add / Edit Faculty")
        fac_grid = QGridLayout(fac_group)
        fac_grid.setSpacing(4)

        fac_grid.addWidget(QLabel("Name:"), 0, 0)
        self.fac_name_input = QLineEdit()
        self.fac_name_input.setPlaceholderText("e.g. Juan dela Cruz")
        fac_grid.addWidget(self.fac_name_input, 0, 1)

        fac_grid.addWidget(QLabel("Classification:"), 1, 0)
        self.fac_classification = QComboBox()
        self.fac_classification.addItems(CLASSIFICATIONS)
        fac_grid.addWidget(self.fac_classification, 1, 1)

        fac_grid.addWidget(QLabel("Admin:"), 2, 0)
        self.fac_admin_cb = QCheckBox("Administrator")
        fac_grid.addWidget(self.fac_admin_cb, 2, 1)

        fac_btn_row = QHBoxLayout()
        self.fac_add_btn = QPushButton("Add Faculty")
        self.fac_add_btn.clicked.connect(self._add_faculty)
        self.fac_delete_btn = QPushButton("Delete Selected")
        self.fac_delete_btn.clicked.connect(self._delete_selected_faculty)
        self.fac_delete_btn.setEnabled(False)
        fac_btn_row.addWidget(self.fac_add_btn)
        fac_btn_row.addWidget(self.fac_delete_btn)
        fac_grid.addLayout(fac_btn_row, 3, 0, 1, 2)

        input_split.addWidget(fac_group)

        # Right: Course input
        course_group = QGroupBox("Add Course")
        course_grid = QGridLayout(course_group)
        course_grid.setSpacing(4)

        course_grid.addWidget(QLabel("Faculty:"), 0, 0)
        self.course_faculty_sel = QComboBox()
        course_grid.addWidget(self.course_faculty_sel, 0, 1)

        course_grid.addWidget(QLabel("Course:"), 1, 0)
        self.course_name_input = QLineEdit()
        self.course_name_input.setPlaceholderText("e.g. Philo 101")
        course_grid.addWidget(self.course_name_input, 1, 1)

        course_grid.addWidget(QLabel("Year Level:"), 2, 0)
        self.year_level = QComboBox()
        self.year_level.addItems(YEAR_LEVELS)
        course_grid.addWidget(self.year_level, 2, 1)

        course_grid.addWidget(QLabel("Units:"), 3, 0)
        self.units = QComboBox()
        self.units.addItems(UNIT_OPTIONS)
        course_grid.addWidget(self.units, 3, 1)

        course_grid.addWidget(QLabel("Schedule:"), 4, 0)
        self.schedule = QComboBox()
        self.schedule.addItems(SCHEDULE_SLOTS)
        course_grid.addWidget(self.schedule, 4, 1)

        course_grid.addWidget(QLabel("Room:"), 5, 0)
        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("e.g. F-203")
        course_grid.addWidget(self.room_input, 5, 1)

        self.course_add_btn = QPushButton("Add Course")
        self.course_add_btn.clicked.connect(self._add_course)
        self.course_delete_btn = QPushButton("Delete Selected")
        self.course_delete_btn.clicked.connect(self._delete_selected_course)
        self.course_delete_btn.setEnabled(False)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.course_add_btn)
        btn_row.addWidget(self.course_delete_btn)
        course_grid.addLayout(btn_row, 6, 0, 1, 2)

        input_split.addWidget(course_group)
        input_split.setSizes([350, 500])
        main_layout.addWidget(input_split)

        # --- Summary bar ---
        self.summary_label = QLabel()
        self.summary_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.summary_label.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        main_layout.addWidget(self.summary_label)

        # --- Tables split ---
        table_split = QSplitter(Qt.Vertical)

        # Faculty table
        fac_label = QLabel("<b>Faculty Workload</b> — double-click to edit")
        table_split.addWidget(fac_label)

        self.faculty_table = QTableWidget()
        self.faculty_table.setColumnCount(7)  # added hidden ID column
        self.faculty_table.setHorizontalHeaderLabels(
            ["Name", "Classification", "Admin", "Req. Load", "Current Load", "Status", ""]
        )
        self.faculty_table.setColumnHidden(6, True)  # hidden ID
        self.faculty_table.horizontalHeader().setStretchLastSection(True)
        self.faculty_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.faculty_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.faculty_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.faculty_table.setSortingEnabled(True)
        self.faculty_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.faculty_table.customContextMenuRequested.connect(self._faculty_context_menu)
        self.faculty_table.itemSelectionChanged.connect(self._on_faculty_selection_changed)
        self.faculty_table.itemChanged.connect(self._on_faculty_cell_edited)
        self.faculty_table.verticalHeader().setVisible(False)
        table_split.addWidget(self.faculty_table)

        # Course table
        course_label = QLabel("<b>Course Assignments</b> — double-click to edit")
        table_split.addWidget(course_label)

        self.course_table = QTableWidget()
        self.course_table.setColumnCount(7)  # added hidden ID + semester_id
        self.course_table.setHorizontalHeaderLabels(
            ["Faculty", "Course", "Year Level", "Units", "Schedule", "Room", ""]
        )
        self.course_table.setColumnHidden(6, True)  # hidden ID
        self.course_table.horizontalHeader().setStretchLastSection(True)
        self.course_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.course_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.course_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.course_table.setSortingEnabled(True)
        self.course_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.course_table.customContextMenuRequested.connect(self._course_context_menu)
        self.course_table.itemSelectionChanged.connect(self._on_course_selection_changed)
        self.course_table.itemChanged.connect(self._on_course_cell_edited)
        self.course_table.verticalHeader().setVisible(False)
        table_split.addWidget(self.course_table)

        table_split.setSizes([350, 350])
        main_layout.addWidget(table_split, stretch=1)

        # --- Export bar ---
        export_layout = QHBoxLayout()
        self.export_pdf_btn = QPushButton("Export to PDF")
        self.export_pdf_btn.clicked.connect(self._export_pdf)
        self.export_csv_btn = QPushButton("Export to CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.clear_all_btn = QPushButton("Clear All Data")
        self.clear_all_btn.clicked.connect(self._clear_all)
        self.clear_all_btn.setStyleSheet("color: #e57373;")
        export_layout.addWidget(self.export_pdf_btn)
        export_layout.addWidget(self.export_csv_btn)
        export_layout.addStretch()
        export_layout.addWidget(self.clear_all_btn)
        main_layout.addLayout(export_layout)

        self._apply_theme()

    # -- Theme --------------------------------------------------------------

    def _apply_theme(self):
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create("Fusion"))
        palette = QPalette()
        colors = DARK_PALETTE if self._is_dark else LIGHT_PALETTE
        for role, color in colors.items():
            qrole = getattr(QPalette, role[0].upper() + role[1:])
            palette.setColor(qrole, color)
        app.setPalette(palette)
        self.theme_btn.setText("☀ Light" if self._is_dark else "☾ Dark")

    def _toggle_theme(self):
        self._is_dark = not self._is_dark
        self._apply_theme()

    # -- Semester management ------------------------------------------------

    def _populate_semester_sel(self):
        self.semester_sel.blockSignals(True)
        self.semester_sel.clear()
        for s in self.semesters:
            label = f"{'✓ ' if s.is_active else '  '}{s.name}"
            self.semester_sel.addItem(label, s._id)
        # Select active
        if self.active_semester:
            idx = self.semester_sel.findData(self.active_semester._id)
            if idx >= 0:
                self.semester_sel.setCurrentIndex(idx)
        self.semester_sel.blockSignals(False)

    def _on_semester_changed(self, idx):
        if idx < 0 or not self.semesters:
            return
        sem_id = self.semester_sel.itemData(idx)
        if sem_id == self.active_semester._id:
            return
        # Switch active semester
        self.db.set_active_semester(sem_id)
        self.active_semester = next((s for s in self.semesters if s._id == sem_id), None)
        # Reload courses for new semester
        for f in self.faculty_list:
            f.courses.clear()
        if self.active_semester:
            self.db.load_courses_for_semester(self.active_semester._id, self.faculty_list)
        self._populate_semester_sel()
        self._refresh_all()
        log.info("Switched to semester: %s", self.active_semester.name if self.active_semester else "None")

    def _add_semester(self):
        dlg = AddSemesterDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        name = dlg.get_name()
        if not name:
            QMessageBox.warning(self, "Error", "Semester name cannot be empty.")
            return
        try:
            self.db.add_semester(name)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicate", "A semester with this name already exists.")
            return
        self.semesters = self.db.load_semesters()
        self._populate_semester_sel()
        log.info("Added semester: %s", name)

    def _delete_semester(self):
        if not self.active_semester:
            return
        reply = QMessageBox.question(
            self, "Delete Semester",
            f"Delete semester '{self.active_semester.name}'?\n\n"
            "Courses in this semester will be unlinked (not deleted).",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        sem_id = self.active_semester._id
        self.db.delete_semester(sem_id)
        self.semesters = self.db.load_semesters()
        self.active_semester = next((s for s in self.semesters if s.is_active), None)
        if not self.active_semester and self.semesters:
            self.active_semester = self.semesters[0]
        # Reload
        for f in self.faculty_list:
            f.courses.clear()
        if self.active_semester:
            self.db.load_courses_for_semester(self.active_semester._id, self.faculty_list)
        self._populate_semester_sel()
        self._refresh_all()
        log.info("Deleted semester id=%s", sem_id)

    # -- Refresh helpers ----------------------------------------------------

    def _refresh_all(self):
        self._refresh_faculty_table()
        self._refresh_course_table()
        self._refresh_faculty_select()
        self._refresh_summary()

    def _refresh_faculty_table(self):
        self._suppress_cell_change = True
        self.faculty_table.setSortingEnabled(False)
        self.faculty_table.setRowCount(len(self.faculty_list))

        for row, fac in enumerate(self.faculty_list):
            name_item = QTableWidgetItem(fac.name)
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            name_item.setData(Qt.UserRole, fac._id)

            class_item = QTableWidgetItem(fac.classification)
            class_item.setFlags(class_item.flags() | Qt.ItemIsEditable)

            admin_item = QTableWidgetItem("Yes" if fac.is_admin else "No")
            admin_item.setFlags(admin_item.flags() | Qt.ItemIsEditable)

            self.faculty_table.setItem(row, 0, name_item)
            self.faculty_table.setItem(row, 1, class_item)
            self.faculty_table.setItem(row, 2, admin_item)
            self.faculty_table.setItem(row, 3, QTableWidgetItem(str(fac.required_load)))
            self.faculty_table.setItem(row, 4, QTableWidgetItem(str(fac.current_load())))

            status_item = QTableWidgetItem(fac.load_status())
            cat = fac.load_status_category()
            colour = STATUS_COLORS.get(cat, STATUS_COLORS['part_time'])
            status_item.setBackground(QBrush(colour))
            status_item.setForeground(QBrush(Qt.black if colour.lightness() > 128 else Qt.white))
            self.faculty_table.setItem(row, 5, status_item)

            # Hidden ID
            id_item = QTableWidgetItem(str(fac._id))
            self.faculty_table.setItem(row, 6, id_item)

        self.faculty_table.setSortingEnabled(True)
        self.faculty_table.resizeRowsToContents()
        self._suppress_cell_change = False

    def _refresh_course_table(self):
        self._suppress_cell_change = True
        self.course_table.setSortingEnabled(False)

        all_courses = []
        for fac in self.faculty_list:
            for c in fac.courses:
                all_courses.append((fac.name, fac, c))

        self.course_table.setRowCount(len(all_courses))
        for row, (fac_name, fac, course) in enumerate(all_courses):
            fac_item = QTableWidgetItem(fac_name)
            fac_item.setFlags(fac_item.flags() & ~Qt.ItemIsEditable)  # faculty is set by dropdown
            self.course_table.setItem(row, 0, fac_item)

            name_item = QTableWidgetItem(course.name)
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            name_item.setData(Qt.UserRole, course._id)
            self.course_table.setItem(row, 1, name_item)

            yr_item = QTableWidgetItem(course.year_level)
            yr_item.setFlags(yr_item.flags() | Qt.ItemIsEditable)
            self.course_table.setItem(row, 2, yr_item)

            units_item = QTableWidgetItem(str(course.units))
            units_item.setFlags(units_item.flags() | Qt.ItemIsEditable)
            self.course_table.setItem(row, 3, units_item)

            sched_item = QTableWidgetItem(course.schedule)
            sched_item.setFlags(sched_item.flags() | Qt.ItemIsEditable)
            self.course_table.setItem(row, 4, sched_item)

            room_item = QTableWidgetItem(course.room)
            room_item.setFlags(room_item.flags() | Qt.ItemIsEditable)
            self.course_table.setItem(row, 5, room_item)

            # Hidden ID
            id_item = QTableWidgetItem(str(course._id))
            self.course_table.setItem(row, 6, id_item)

        self.course_table.setSortingEnabled(True)
        self.course_table.resizeRowsToContents()
        self._suppress_cell_change = False

    def _refresh_faculty_select(self):
        current = self.course_faculty_sel.currentText()
        self.course_faculty_sel.clear()
        names = [f.name for f in self.faculty_list]
        self.course_faculty_sel.addItems(names)
        idx = self.course_faculty_sel.findText(current)
        if idx >= 0:
            self.course_faculty_sel.setCurrentIndex(idx)

    def _refresh_summary(self):
        total_fac = len(self.faculty_list)
        total_courses = sum(len(f.courses) for f in self.faculty_list)
        under = sum(1 for f in self.faculty_list if f.load_status_category() == 'under')
        over = sum(1 for f in self.faculty_list if f.load_status_category() == 'over')
        on_target = sum(1 for f in self.faculty_list if f.load_status_category() == 'on_target')
        pt = sum(1 for f in self.faculty_list if f.load_status_category() == 'part_time')
        sem = self.active_semester.name if self.active_semester else "No semester"
        self.summary_label.setText(
            f"[{sem}]  Faculty: {total_fac}  |  Courses: {total_courses}  |  "
            f"Under: {under}  |  On target: {on_target}  |  Over: {over}  |  "
            f"Part-time: {pt}"
        )

    # -- In-place editing (Faculty) ----------------------------------------

    def _on_faculty_cell_edited(self, item):
        if self._suppress_cell_change:
            return
        row = item.row()
        col = item.column()
        if col > 2:  # only name, classification, admin are editable
            return

        fac_id_item = self.faculty_table.item(row, 6)
        if not fac_id_item:
            return
        fac_id = int(fac_id_item.text())
        faculty = next((f for f in self.faculty_list if f._id == fac_id), None)
        if not faculty:
            return

        new_value = item.text().strip()
        old_name = faculty.name

        if col == 0:  # Name
            if not new_value:
                QMessageBox.warning(self, "Error", "Name cannot be empty.")
                self._refresh_all()
                return
            if new_value != faculty.name and any(f.name == new_value for f in self.faculty_list):
                QMessageBox.warning(self, "Duplicate", "A faculty member with this name already exists.")
                self._refresh_all()
                return
            faculty.name = new_value
        elif col == 1:  # Classification
            if new_value not in CLASSIFICATIONS:
                QMessageBox.warning(self, "Error", f"Classification must be one of: {', '.join(CLASSIFICATIONS)}")
                self._refresh_all()
                return
            faculty.classification = new_value
            faculty.required_load = faculty.calculate_required_load()
        elif col == 2:  # Admin
            faculty.is_admin = new_value.lower() in ('yes', 'true', '1')
            faculty.required_load = faculty.calculate_required_load()

        # Persist
        self.db.update_faculty(faculty)
        log.info("Edited faculty %s -> %s", old_name, faculty.name)
        self._refresh_all()

    # -- In-place editing (Course) -----------------------------------------

    def _on_course_cell_edited(self, item):
        if self._suppress_cell_change:
            return
        row = item.row()
        col = item.column()
        if col == 0:  # faculty column is read-only
            return

        id_item = self.course_table.item(row, 6)
        if not id_item:
            return
        course_id = int(id_item.text())

        # Find the course across all faculty
        course = None
        faculty = None
        for f in self.faculty_list:
            for c in f.courses:
                if c._id == course_id:
                    course = c
                    faculty = f
                    break
            if course:
                break

        if not course:
            return

        new_value = item.text().strip()
        try:
            if col == 1:  # Course name
                if not new_value:
                    QMessageBox.warning(self, "Error", "Course name cannot be empty.")
                    self._refresh_all()
                    return
                course.name = new_value
            elif col == 2:  # Year level
                if new_value not in YEAR_LEVELS:
                    QMessageBox.warning(self, "Error", f"Year level must be one of: {', '.join(YEAR_LEVELS)}")
                    self._refresh_all()
                    return
                course.year_level = new_value
            elif col == 3:  # Units
                units = int(new_value)
                if units not in (3, 6):
                    QMessageBox.warning(self, "Error", "Units must be 3 or 6.")
                    self._refresh_all()
                    return
                course.units = units
            elif col == 4:  # Schedule
                if new_value not in SCHEDULE_SLOTS:
                    QMessageBox.warning(self, "Error", f"'{new_value}' is not a valid schedule slot.")
                    self._refresh_all()
                    return
                course.schedule = new_value
            elif col == 5:  # Room
                course.room = new_value

            self.db.update_course(course)
            log.info("Edited course id=%s: col %d = '%s'", course_id, col, new_value)
            self._refresh_all()
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid value entered.")
            self._refresh_all()

    # -- Faculty operations -------------------------------------------------

    def _find_faculty_by_name(self, name):
        return next((f for f in self.faculty_list if f.name == name), None)

    def _add_faculty(self):
        name = self.fac_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Please enter a faculty name.")
            return

        if any(f.name == name for f in self.faculty_list):
            QMessageBox.warning(self, "Duplicate", "A faculty member with this name already exists.")
            return

        classification = self.fac_classification.currentText()
        is_admin = self.fac_admin_cb.isChecked()

        faculty = Faculty(name, classification, is_admin)
        self.db.add_faculty(faculty)
        self.faculty_list.append(faculty)
        self._refresh_all()
        self.fac_name_input.clear()
        log.info("Added faculty: %s", name)

    def _delete_selected_faculty(self):
        rows = self.faculty_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        name = self.faculty_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete faculty '{name}' and all their courses?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.db.delete_faculty_by_name(name)
        self.faculty_list = [f for f in self.faculty_list if f.name != name]
        self._refresh_all()
        log.info("Deleted faculty: %s", name)

    def _on_faculty_selection_changed(self):
        self.fac_delete_btn.setEnabled(
            bool(self.faculty_table.selectionModel().selectedRows())
        )

    def _faculty_context_menu(self, pos):
        row = self.faculty_table.rowAt(pos.y())
        if row < 0:
            return
        self.faculty_table.selectRow(row)
        name = self.faculty_table.item(row, 0).text()
        menu = QMenu()
        delete_action = menu.addAction(f"Delete '{name}'")
        action = menu.exec_(self.faculty_table.viewport().mapToGlobal(pos))
        if action == delete_action:
            self._delete_selected_faculty()

    # -- Course operations --------------------------------------------------

    def _add_course(self):
        course_name = self.course_name_input.text().strip()
        faculty_name = self.course_faculty_sel.currentText()

        if not course_name or not faculty_name:
            QMessageBox.warning(self, "Input Error", "Please enter a course name and select a faculty.")
            return

        faculty = self._find_faculty_by_name(faculty_name)
        if not faculty:
            QMessageBox.warning(self, "Error", "Selected faculty not found.")
            return

        year_level = self.year_level.currentText()
        units = int(self.units.currentText())
        schedule = self.schedule.currentText()
        room = self.room_input.text().strip()

        course = Course(course_name, year_level, units, schedule, room,
                        self.active_semester._id if self.active_semester else None)

        conflict = self._find_conflicts(faculty, course)
        if conflict:
            QMessageBox.warning(
                self, "Schedule Conflict",
                f"This course conflicts with '{conflict.name}' "
                f"({conflict.schedule}) for {faculty_name}."
            )
            return

        self.db.add_course(faculty._id, course)
        faculty.courses.append(course)
        self._refresh_all()
        self.course_name_input.clear()
        self.room_input.clear()
        log.info("Added course '%s' to %s", course_name, faculty_name)

    def _find_conflicts(self, faculty, new_course):
        days_new = new_course.schedule.split()[0] if new_course.schedule else ""
        for c in faculty.courses:
            if c.schedule == new_course.schedule:
                return c
            days_c = c.schedule.split()[0] if c.schedule else ""
            if c.year_level == new_course.year_level and days_c == days_new:
                return c
        for other in self.faculty_list:
            if other is faculty:
                continue
            for c in other.courses:
                if c.year_level == new_course.year_level and c.schedule == new_course.schedule:
                    return c
        return None

    def _delete_selected_course(self):
        rows = self.course_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        fac_name = self.course_table.item(row, 0).text()
        course_name = self.course_table.item(row, 1).text()
        schedule = self.course_table.item(row, 4).text()
        course_id_item = self.course_table.item(row, 6)
        course_id = int(course_id_item.text()) if course_id_item else -1

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete course '{course_name}' ({schedule}) for {fac_name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        faculty = self._find_faculty_by_name(fac_name)
        if faculty:
            faculty.courses = [c for c in faculty.courses
                               if not (c.name == course_name and c.schedule == schedule)]
        if course_id > 0:
            self.db.delete_course(course_id)

        self._refresh_all()
        log.info("Deleted course '%s' from %s", course_name, fac_name)

    def _on_course_selection_changed(self):
        self.course_delete_btn.setEnabled(
            bool(self.course_table.selectionModel().selectedRows())
        )

    def _course_context_menu(self, pos):
        row = self.course_table.rowAt(pos.y())
        if row < 0:
            return
        self.course_table.selectRow(row)
        course_name = self.course_table.item(row, 1).text()
        menu = QMenu()
        delete_action = menu.addAction(f"Delete '{course_name}'")
        action = menu.exec_(self.course_table.viewport().mapToGlobal(pos))
        if action == delete_action:
            self._delete_selected_course()

    # -- Bulk import from CSV ------------------------------------------------

    def _bulk_import(self):
        """Import faculty and courses from a CSV file.

        Expected columns:
          Faculty Name, Classification, Is Admin, Course Name,
          Year Level, Units, Schedule, Room
        Header row is required.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        if not self.active_semester:
            QMessageBox.warning(self, "Error", "Please create or select a semester first.")
            return

        log.info("Importing CSV from: %s", file_path)
        try:
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                QMessageBox.information(self, "Import", "CSV file is empty.")
                return

            added_faculty = 0
            added_courses = 0
            skipped = 0
            errors = []

            for i, row in enumerate(rows, start=2):  # 2 = header is row 1
                fac_name = row.get('Faculty Name', '').strip()
                classification = row.get('Classification', '').strip()
                is_admin_str = row.get('Is Admin', '0').strip()
                course_name = row.get('Course Name', '').strip()
                year_level = row.get('Year Level', '').strip()
                units_str = row.get('Units', '3').strip()
                schedule = row.get('Schedule', '').strip()
                room = row.get('Room', '').strip()

                if not fac_name or not course_name:
                    skipped += 1
                    errors.append(f"Row {i}: missing Faculty Name or Course Name")
                    continue

                # Find or create faculty
                faculty = self._find_faculty_by_name(fac_name)
                if not faculty:
                    if classification not in CLASSIFICATIONS:
                        classification = "Part-time"
                    is_admin = is_admin_str.lower() in ('yes', 'true', '1')
                    faculty = Faculty(fac_name, classification, is_admin)
                    self.db.add_faculty(faculty)
                    self.faculty_list.append(faculty)
                    added_faculty += 1

                if year_level not in YEAR_LEVELS:
                    year_level = "BA 1"
                try:
                    units = int(units_str)
                    if units not in (3, 6):
                        units = 3
                except ValueError:
                    units = 3
                if schedule not in SCHEDULE_SLOTS:
                    schedule = SCHEDULE_SLOTS[0]

                course = Course(course_name, year_level, units, schedule, room,
                                self.active_semester._id)
                # Check conflicts
                conflict = self._find_conflicts(faculty, course)
                if conflict:
                    skipped += 1
                    errors.append(f"Row {i}: conflict with '{conflict.name}' ({conflict.schedule})")
                    continue

                self.db.add_course(faculty._id, course)
                faculty.courses.append(course)
                added_courses += 1

            self._refresh_all()
            msg = (f"Import complete.\n\n"
                   f"Faculty added: {added_faculty}\n"
                   f"Courses added: {added_courses}\n"
                   f"Skipped: {skipped}")
            if errors:
                msg += f"\n\nErrors:\n" + "\n".join(errors[:10])
                if len(errors) > 10:
                    msg += f"\n... and {len(errors) - 10} more"
            QMessageBox.information(self, "Import Results", msg)
            log.info("CSV import: %d faculty, %d courses added, %d skipped",
                     added_faculty, added_courses, skipped)

        except Exception as e:
            log.error("CSV import failed: %s", e)
            QMessageBox.critical(self, "Import Failed", f"Error: {e}")

    # -- Weekly Schedule Dialog ---------------------------------------------

    def _show_weekly_schedule(self):
        if not self.faculty_list or not any(f.courses for f in self.faculty_list):
            QMessageBox.information(self, "No Data", "No courses assigned yet to display a schedule.")
            return
        dlg = WeeklyScheduleDialog(self.faculty_list, self)
        dlg.exec_()

    # -- Export -------------------------------------------------------------

    @staticmethod
    def _pdf_table_style():
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), rl_colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), rl_colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), rl_colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 1, rl_colors.black),
        ])

    def _export_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return

        log.info("Exporting PDF to %s", file_path)
        try:
            doc = SimpleDocTemplate(file_path, pagesize=landscape(letter))
            styles = getSampleStyleSheet()
            elements = []

            # Title
            sem_name = self.active_semester.name if self.active_semester else "All Semesters"
            elements.append(Paragraph(
                f"Faculty Workload Report — {sem_name}", styles['Title']))
            elements.append(Spacer(1, 12))

            # Faculty table
            fac_header = ["Name", "Class", "Admin", "Req", "Load", "Status"]
            fac_data = [fac_header]
            for f in self.faculty_list:
                fac_data.append([
                    f.name, f.classification, "Yes" if f.is_admin else "No",
                    str(f.required_load), str(f.current_load()), f.load_status(),
                ])
            ft = Table(fac_data)
            ft.setStyle(self._pdf_table_style())
            elements.append(Paragraph("<b>Faculty Workload</b>", styles['Heading2']))
            elements.append(ft)
            elements.append(Spacer(1, 16))

            # Course table with Room
            course_header = ["Faculty", "Course", "Year", "Units", "Schedule", "Room"]
            course_data = [course_header]
            for f in self.faculty_list:
                for c in f.courses:
                    course_data.append([f.name, c.name, c.year_level,
                                        str(c.units), c.schedule, c.room or '—'])
            if len(course_data) > 1:
                ct = Table(course_data)
                ct.setStyle(self._pdf_table_style())
                elements.append(Paragraph("<b>Course Assignments</b>", styles['Heading2']))
                elements.append(ct)
            else:
                elements.append(Paragraph("No course assignments.", styles['Normal']))

            doc.build(elements)
            QMessageBox.information(self, "Export Successful",
                                    f"Data exported to PDF:\n{file_path}")
            log.info("PDF export complete: %s", file_path)
        except Exception as e:
            log.error("PDF export failed: %s", e)
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    def _export_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return

        log.info("Exporting CSV to %s", file_path)
        sem_name = self.active_semester.name if self.active_semester else "All"
        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([f"Faculty Workload — {sem_name}"])
                writer.writerow([])
                writer.writerow(["Name", "Classification", "Admin",
                                 "Req. Load", "Current Load", "Status"])
                for f in self.faculty_list:
                    writer.writerow([
                        f.name, f.classification, "Yes" if f.is_admin else "No",
                        f.required_load, f.current_load(), f.load_status(),
                    ])
                writer.writerow([])
                writer.writerow(["Faculty", "Course", "Year Level",
                                 "Units", "Schedule", "Room"])
                for f in self.faculty_list:
                    for c in f.courses:
                        writer.writerow([f.name, c.name, c.year_level,
                                         c.units, c.schedule, c.room])

            QMessageBox.information(self, "Export Successful",
                                    f"Data exported to CSV:\n{file_path}")
            log.info("CSV export complete: %s", file_path)
        except Exception as e:
            log.error("CSV export failed: %s", e)
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    # -- Danger zone --------------------------------------------------------

    def _clear_all(self):
        reply = QMessageBox.warning(
            self, "Clear All Data",
            "This will permanently delete ALL faculty, course, and semester data.\n\n"
            "Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        reply2 = QMessageBox.question(
            self, "Confirm",
            "This cannot be undone. Proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply2 != QMessageBox.Yes:
            return

        self.db.conn.execute("DELETE FROM courses")
        self.db.conn.execute("DELETE FROM faculty")
        self.db.conn.execute("DELETE FROM semesters")
        self.db.conn.commit()

        # Recreate default semester
        year = datetime.date.today().year
        self.db.conn.execute(
            "INSERT INTO semesters (name, is_active) VALUES (?, 1)",
            (f"AY {year}-{year+1} Sem 1",)
        )
        self.db.conn.commit()

        self.semesters = self.db.load_semesters()
        self.active_semester = self.semesters[0] if self.semesters else None
        self.faculty_list.clear()
        self._populate_semester_sel()
        self._refresh_all()
        log.warning("All data cleared by user.")

    # -- Cleanup ------------------------------------------------------------

    def closeEvent(self, event):
        log.info("Application closing.")
        self.db.close()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window = FacultyWorkloadApp()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        log.critical("Unhandled exception: %s", e, exc_info=True)
        raise
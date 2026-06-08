"""
Faculty Workload and Scheduling Application
--------------------------------------------
A PyQt5-based desktop app to manage faculty workloads, course assignments,
and scheduling with conflict detection, data persistence via SQLite,
and PDF/CSV export.

Author: Ulysses Cabayao, SJ (uscabayaosj@addu.edu.ph)
"""

import sys
import os
import datetime
import logging
import tempfile
import sqlite3
import csv

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QFileDialog, QStyleFactory,
    QHeaderView, QMenu, QAbstractItemView, QCheckBox, QGroupBox,
    QFrame, QGridLayout, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor, QBrush, QIcon
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging():
    """Configure logging to a file in the user's home directory."""
    log_path = os.path.join(os.path.expanduser('~'), 'faculty_app_debug.log')
    logging.basicConfig(
        level=logging.DEBUG,
        filename=log_path,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    return logging.getLogger(__name__)


setup_logging()
log = logging.getLogger(__name__)
log.info("Application starting — Python %s", sys.version)

# ---------------------------------------------------------------------------
# Temp directory setup (relevant when frozen via PyInstaller)
# ---------------------------------------------------------------------------

def get_temp_dir():
    """Return a writable temporary directory, preferring a local 'temp' folder."""
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
# Data models
# ---------------------------------------------------------------------------

class Course:
    """A single course assigned to a faculty member."""

    __slots__ = ('name', 'year_level', 'units', 'schedule', '_id')

    def __init__(self, name, year_level, units, schedule, db_id=None):
        self.name = name
        self.year_level = year_level
        self.units = units
        self.schedule = schedule
        self._id = db_id


class Faculty:
    """A faculty member with classification, admin status, and course list."""

    __slots__ = ('name', 'classification', 'is_admin', 'courses', 'required_load', '_id')

    def __init__(self, name, classification, is_admin=False, db_id=None):
        self.name = name
        self.classification = classification
        self.is_admin = is_admin
        self.courses = []
        self.required_load = self.calculate_required_load()
        self._id = db_id

    def calculate_required_load(self):
        """Return the minimum units this faculty member must carry."""
        if self.classification == "Full-time PhD":
            return 15 - (12 if self.is_admin else 0)
        elif self.classification == "Full-time MA":
            return 18 - (12 if self.is_admin else 0)
        return 0  # Part-time

    def current_load(self):
        """Total assigned units."""
        return sum(c.units for c in self.courses)

    def load_delta(self):
        """Signed difference: negative = underloaded, positive = overloaded."""
        return self.current_load() - self.required_load

    def load_status(self):
        """Human-readable load status string."""
        delta = self.load_delta()
        if delta < 0:
            return f"Under by {-delta} unit{'s' if -delta != 1 else ''}"
        elif delta > 0:
            return f"Over by {delta} unit{'s' if delta != 1 else ''}"
        return "On target" if self.required_load > 0 else "N/A (PT)"

    def load_status_category(self):
        """Return 'under', 'on_target', or 'over' for color-coding."""
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
    """Thin wrapper around SQLite for persistence."""

    def __init__(self, db_path='faculty_workload.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        log.info("Database opened: %s", db_path)

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                classification TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                year_level TEXT NOT NULL,
                units INTEGER NOT NULL,
                schedule TEXT NOT NULL,
                FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_courses_faculty ON courses(faculty_id);
        """)
        self.conn.commit()

    # -- Faculty CRUD -------------------------------------------------------

    def load_all(self):
        """Load all faculty and their courses (single JOIN query)."""
        fac_rows = self.conn.execute(
            "SELECT * FROM faculty ORDER BY name"
        ).fetchall()

        faculty_by_id = {}
        faculty_list = []

        for row in fac_rows:
            f = Faculty(row['name'], row['classification'],
                        bool(row['is_admin']), row['id'])
            faculty_by_id[row['id']] = f
            faculty_list.append(f)

        if faculty_by_id:
            ids = tuple(faculty_by_id.keys())
            # SQLite doesn't support tuples of length 1 well
            placeholders = ','.join('?' for _ in ids)
            course_rows = self.conn.execute(
                f"SELECT * FROM courses WHERE faculty_id IN ({placeholders}) ORDER BY name",
                ids
            ).fetchall()
            for row in course_rows:
                c = Course(row['name'], row['year_level'],
                           row['units'], row['schedule'], row['id'])
                faculty_by_id[row['faculty_id']].courses.append(c)

        return faculty_list

    def add_faculty(self, faculty):
        """Insert a new faculty member and return the row ID."""
        cur = self.conn.execute(
            "INSERT INTO faculty (name, classification, is_admin) VALUES (?, ?, ?)",
            (faculty.name, faculty.classification, int(faculty.is_admin))
        )
        self.conn.commit()
        faculty._id = cur.lastrowid
        return faculty._id

    def update_faculty(self, faculty):
        """Update an existing faculty member."""
        self.conn.execute(
            "UPDATE faculty SET name=?, classification=?, is_admin=? WHERE id=?",
            (faculty.name, faculty.classification, int(faculty.is_admin), faculty._id)
        )
        self.conn.commit()

    def delete_faculty(self, faculty_id):
        """Delete a faculty member and all their courses (CASCADE)."""
        self.conn.execute("DELETE FROM faculty WHERE id=?", (faculty_id,))
        self.conn.commit()

    def delete_faculty_by_name(self, name):
        """Delete a faculty member by name."""
        cur = self.conn.execute("SELECT id FROM faculty WHERE name=?", (name,))
        row = cur.fetchone()
        if row:
            self.delete_faculty(row['id'])

    # -- Course CRUD --------------------------------------------------------

    def add_course(self, faculty_id, course):
        """Insert a course and return the row ID."""
        cur = self.conn.execute(
            "INSERT INTO courses (faculty_id, name, year_level, units, schedule) "
            "VALUES (?, ?, ?, ?, ?)",
            (faculty_id, course.name, course.year_level, course.units, course.schedule)
        )
        self.conn.commit()
        course._id = cur.lastrowid
        return course._id

    def delete_course(self, course_id):
        """Delete a course by ID."""
        self.conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()
        log.info("Database closed.")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ---------------------------------------------------------------------------
# Application GUI
# ---------------------------------------------------------------------------

# Colour palette for status indicators
COLORS = {
    'under': QColor(255, 235, 59),       # amber
    'on_target': QColor(76, 175, 80),    # green
    'over': QColor(244, 67, 54),         # red
    'part_time': QColor(158, 158, 158),  # grey
}


class FacultyWorkloadApp(QMainWindow):
    """Main application window."""

    def __init__(self):
        log.info("Initialising FacultyWorkloadApp …")
        super().__init__()
        self.setWindowTitle("Faculty Workload & Scheduling")
        self.setGeometry(100, 100, 1100, 850)

        self.db = Database()
        self.faculty_list = self.db.load_all()

        self._init_ui()
        self._refresh_all()
        log.info("Initialisation complete.")

    # -- UI construction ----------------------------------------------------

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)

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
        self.fac_classification.addItems(["Full-time PhD", "Full-time MA", "Part-time"])
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
        self.year_level.addItems(["BA 1", "BA 2", "BA 3", "BA 4", "MA 1", "MA 2"])
        course_grid.addWidget(self.year_level, 2, 1)

        course_grid.addWidget(QLabel("Units:"), 3, 0)
        self.units = QComboBox()
        self.units.addItems(["3", "6"])
        course_grid.addWidget(self.units, 3, 1)

        course_grid.addWidget(QLabel("Schedule:"), 4, 0)
        self.schedule = QComboBox()
        self.schedule.addItems([
            "MW 07:40am-09:10am", "MW 09:20am-10:50am", "MW 12:25pm-01:55pm", "MW 02:05pm-03:35pm",
            "TTh 07:40am-09:10am", "TTh 09:20am-10:50am", "TTh 12:25pm-01:55pm", "TTh 02:05pm-03:35pm",
            "TTh 03:45pm-05:15pm", "TTh 05:50pm-07:20pm", "TTh 07:30pm-09:00pm",
            "Sat 09:00am-12:00pm", "Sat 01:00pm-04:00pm", "Sat 05:00pm-08:00pm",
        ])
        course_grid.addWidget(self.schedule, 4, 1)

        self.course_add_btn = QPushButton("Add Course")
        self.course_add_btn.clicked.connect(self._add_course)
        self.course_delete_btn = QPushButton("Delete Selected")
        self.course_delete_btn.clicked.connect(self._delete_selected_course)
        self.course_delete_btn.setEnabled(False)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.course_add_btn)
        btn_row.addWidget(self.course_delete_btn)
        course_grid.addLayout(btn_row, 5, 0, 1, 2)

        input_split.addWidget(course_group)
        input_split.setSizes([350, 450])
        main_layout.addWidget(input_split)

        # --- Summary bar ---
        self.summary_label = QLabel()
        self.summary_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.summary_label.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        main_layout.addWidget(self.summary_label)

        # --- Tables split ---
        table_split = QSplitter(Qt.Vertical)

        # Faculty table
        fac_label = QLabel("<b>Faculty Workload</b>")
        table_split.addWidget(fac_label)

        self.faculty_table = QTableWidget()
        self.faculty_table.setColumnCount(6)
        self.faculty_table.setHorizontalHeaderLabels(
            ["Name", "Classification", "Admin", "Req. Load", "Current Load", "Status"]
        )
        self.faculty_table.horizontalHeader().setStretchLastSection(True)
        self.faculty_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.faculty_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.faculty_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.faculty_table.setSortingEnabled(True)
        self.faculty_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.faculty_table.customContextMenuRequested.connect(self._faculty_context_menu)
        self.faculty_table.itemSelectionChanged.connect(self._on_faculty_selection_changed)
        self.faculty_table.verticalHeader().setVisible(False)
        table_split.addWidget(self.faculty_table)

        # Course table
        course_label = QLabel("<b>Course Assignments</b>")
        table_split.addWidget(course_label)

        self.course_table = QTableWidget()
        self.course_table.setColumnCount(5)
        self.course_table.setHorizontalHeaderLabels(
            ["Faculty", "Course", "Year Level", "Units", "Schedule"]
        )
        self.course_table.horizontalHeader().setStretchLastSection(True)
        self.course_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.course_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.course_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.course_table.setSortingEnabled(True)
        self.course_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.course_table.customContextMenuRequested.connect(self._course_context_menu)
        self.course_table.itemSelectionChanged.connect(self._on_course_selection_changed)
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

        self._apply_dark_theme()

    # -- Theme --------------------------------------------------------------

    def _apply_dark_theme(self):
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create("Fusion"))
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)

    # -- Refresh helpers ----------------------------------------------------

    def _refresh_all(self):
        """Rebuild all UI elements from the current data model."""
        self._refresh_faculty_table()
        self._refresh_course_table()
        self._refresh_faculty_select()
        self._refresh_summary()

    def _refresh_faculty_table(self):
        self.faculty_table.setSortingEnabled(False)
        self.faculty_table.setRowCount(len(self.faculty_list))

        for row, fac in enumerate(self.faculty_list):
            name_item = QTableWidgetItem(fac.name)
            name_item.setData(Qt.UserRole, fac.name)

            self.faculty_table.setItem(row, 0, name_item)
            self.faculty_table.setItem(row, 1, QTableWidgetItem(fac.classification))
            self.faculty_table.setItem(row, 2, QTableWidgetItem("Yes" if fac.is_admin else "No"))
            self.faculty_table.setItem(row, 3, QTableWidgetItem(str(fac.required_load)))
            self.faculty_table.setItem(row, 4, QTableWidgetItem(str(fac.current_load())))

            status_item = QTableWidgetItem(fac.load_status())
            cat = fac.load_status_category()
            colour = COLORS.get(cat, COLORS['part_time'])
            status_item.setBackground(QBrush(colour))
            status_item.setForeground(QBrush(Qt.black if colour.lightness() > 128 else Qt.white))
            self.faculty_table.setItem(row, 5, status_item)

        self.faculty_table.setSortingEnabled(True)
        self.faculty_table.resizeRowsToContents()

    def _refresh_course_table(self):
        self.course_table.setSortingEnabled(False)
        # Flatten all courses
        all_courses = []
        for fac in self.faculty_list:
            for c in fac.courses:
                all_courses.append((fac.name, c))

        self.course_table.setRowCount(len(all_courses))
        for row, (fac_name, course) in enumerate(all_courses):
            self.course_table.setItem(row, 0, QTableWidgetItem(fac_name))
            self.course_table.setItem(row, 1, QTableWidgetItem(course.name))
            self.course_table.setItem(row, 2, QTableWidgetItem(course.year_level))
            self.course_table.setItem(row, 3, QTableWidgetItem(str(course.units)))
            sched_item = QTableWidgetItem(course.schedule)
            sched_item.setData(Qt.UserRole, course._id if course._id else -1)
            self.course_table.setItem(row, 4, sched_item)

        self.course_table.setSortingEnabled(True)
        self.course_table.resizeRowsToContents()

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

        self.summary_label.setText(
            f"Faculty: {total_fac}  |  Courses: {total_courses}  |  "
            f"Under: {under}  |  On target: {on_target}  |  Over: {over}  |  "
            f"Part-time: {pt}"
        )

    # -- Faculty operations -------------------------------------------------

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

        faculty = next((f for f in self.faculty_list if f.name == faculty_name), None)
        if not faculty:
            QMessageBox.warning(self, "Error", "Selected faculty not found.")
            return

        year_level = self.year_level.currentText()
        units = int(self.units.currentText())
        schedule = self.schedule.currentText()

        course = Course(course_name, year_level, units, schedule)

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
        log.info("Added course '%s' to %s", course_name, faculty_name)

    def _find_conflicts(self, faculty, new_course):
        """Return the first conflicting course, or None."""
        days_new = new_course.schedule.split()[0] if new_course.schedule else ""
        time_new = new_course.schedule.split()[1] if len(new_course.schedule.split()) > 1 else ""

        for c in faculty.courses:
            # Exact same timeslot
            if c.schedule == new_course.schedule:
                return c
            # Same day + same year level means conflict (assumes same period)
            days_c = c.schedule.split()[0] if c.schedule else ""
            if c.year_level == new_course.year_level and days_c == days_new and c.schedule != new_course.schedule:
                return c

        # Cross-faculty: same year level at same timeslot
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
        course_id = self.course_table.item(row, 4).data(Qt.UserRole)

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete course '{course_name}' ({schedule}) for {fac_name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Remove from model
        faculty = next((f for f in self.faculty_list if f.name == fac_name), None)
        if faculty:
            faculty.courses = [c for c in faculty.courses
                               if not (c.name == course_name and c.schedule == schedule)]

        # Remove from DB
        if course_id and course_id > 0:
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

    # -- Export -------------------------------------------------------------

    @staticmethod
    def _pdf_table_style():
        """Return a shared TableStyle for export tables."""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ])

    def _export_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return

        log.info("Exporting PDF to %s", file_path)
        try:
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            elements = []

            # Faculty table
            fac_header = ["Name", "Classification", "Admin", "Req. Load", "Current Load", "Status"]
            fac_data = [fac_header]
            for f in self.faculty_list:
                fac_data.append([
                    f.name, f.classification, "Yes" if f.is_admin else "No",
                    str(f.required_load), str(f.current_load()), f.load_status(),
                ])
            ft = Table(fac_data)
            ft.setStyle(self._pdf_table_style())
            elements.append(ft)
            elements.append(Spacer(1, 20))

            # Course table
            course_header = ["Faculty", "Course", "Year Level", "Units", "Schedule"]
            course_data = [course_header]
            for f in self.faculty_list:
                for c in f.courses:
                    course_data.append([f.name, c.name, c.year_level, str(c.units), c.schedule])
            ct = Table(course_data)
            ct.setStyle(self._pdf_table_style())
            elements.append(ct)

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
        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                writer.writerow(["Faculty Workload Summary"])
                writer.writerow(["Name", "Classification", "Admin", "Req. Load", "Current Load", "Status"])
                for f in self.faculty_list:
                    writer.writerow([
                        f.name, f.classification, "Yes" if f.is_admin else "No",
                        f.required_load, f.current_load(), f.load_status(),
                    ])

                writer.writerow([])
                writer.writerow(["Course Assignments"])
                writer.writerow(["Faculty", "Course", "Year Level", "Units", "Schedule"])
                for f in self.faculty_list:
                    for c in f.courses:
                        writer.writerow([f.name, c.name, c.year_level, c.units, c.schedule])

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
            "This will permanently delete ALL faculty and course data.\n\n"
            "Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Second confirmation
        reply2 = QMessageBox.question(
            self, "Confirm",
            "This cannot be undone. Proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply2 != QMessageBox.Yes:
            return

        self.db.conn.execute("DELETE FROM courses")
        self.db.conn.execute("DELETE FROM faculty")
        self.db.conn.commit()
        self.faculty_list.clear()
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
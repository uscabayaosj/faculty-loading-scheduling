"""
Faculty Workload and Scheduling Application
--------------------------------------------
A PyQt5-based desktop app to manage faculty workloads, course assignments,
and scheduling with conflict detection, data persistence via SQLite,
and PDF/CSV/PNG export.

Features:
  - Semester/term management, in-place editing, bulk CSV import, room tracking
  - Weekly schedule view (dialog), schedule PDF export, timetable PNG export
  - Auto-scheduler: greedy load-balanced course assignment suggestions
  - Google Calendar sync: push courses as calendar events via OAuth2

Author: Ulysses Cabayao, SJ (uscabayaosj@addu.edu.ph)
"""

import sys
import os
import datetime
import logging
import tempfile
import sqlite3
import csv
import webbrowser
import json
from copy import deepcopy
from collections import defaultdict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QFileDialog, QStyleFactory,
    QHeaderView, QMenu, QAbstractItemView, QCheckBox, QGroupBox,
    QFrame, QGridLayout, QSplitter, QDialog, QDialogButtonBox,
    QFormLayout, QScrollArea, QProgressDialog, QTextEdit,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QDate, QSize
from PyQt5.QtGui import (
    QFont, QPalette, QColor, QBrush, QIcon, QPixmap, QPainter,
    QTextDocument, QPageSize, QPageLayout
)
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table as RLTable, TableStyle, Spacer, Paragraph, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

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
# Temp directory setup
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
DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAY_CODES = {"MW": (0, 2), "TTh": (1, 3), "Sat": (4,)}
# Ordered timeslot labels for timetable grid
TIMESLOT_LABELS = [
    "07:40am-09:10am", "09:20am-10:50am", "12:25pm-01:55pm",
    "02:05pm-03:35pm", "03:45pm-05:15pm", "05:50pm-07:20pm", "07:30pm-09:00pm",
]
SCHEDULE_TO_TIMESLOT = {}
for s in SCHEDULE_SLOTS:
    parts = s.split(None, 1)
    if len(parts) == 2:
        SCHEDULE_TO_TIMESLOT[s] = parts[1]

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

STATUS_COLORS = {
    'under': QColor(255, 235, 59),
    'on_target': QColor(76, 175, 80),
    'over': QColor(244, 67, 54),
    'part_time': QColor(158, 158, 158),
}

# Day grid labels for export
GRID_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
GRID_DAY_INDICES = {"MW": [0, 2], "TTh": [1, 3], "Sat": [4]}

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

    def remaining_capacity(self):
        """How many more units this faculty can take before hitting target."""
        return max(0, self.required_load - self.current_load())

# ---------------------------------------------------------------------------
# Database
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
        cur = self.conn.execute("SELECT COUNT(*) FROM semesters")
        if cur.fetchone()[0] == 0:
            year = datetime.date.today().year
            self.conn.execute(
                "INSERT INTO semesters (name, is_active) VALUES (?, 1)",
                (f"AY {year}-{year+1} Sem 1",)
            )
            self.conn.commit()
            log.info("Created default semester")

    # -- Semesters ----------------------------------------------------------

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
        self.conn.execute("UPDATE courses SET semester_id=NULL WHERE semester_id=?", (semester_id,))
        self.conn.execute("DELETE FROM semesters WHERE id=?", (semester_id,))
        self.conn.commit()

    # -- Faculty ------------------------------------------------------------

    def load_all_faculty(self):
        rows = self.conn.execute("SELECT * FROM faculty ORDER BY name").fetchall()
        return [Faculty(r['name'], r['classification'], bool(r['is_admin']), r['id'])
                for r in rows]

    def load_courses_for_semester(self, semester_id, faculty_list):
        if not faculty_list:
            return
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

    # -- Courses ------------------------------------------------------------

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
# Scheduling Optimizer (greedy load-balanced algorithm)
# ---------------------------------------------------------------------------

class ScheduleSuggestion:
    """One proposed course-to-faculty assignment from the optimizer."""

    __slots__ = ('course_name', 'year_level', 'units', 'schedule', 'room',
                 'suggested_faculty', 'reason', 'accepted')

    def __init__(self, course_name, year_level, units, schedule, room,
                 suggested_faculty, reason):
        self.course_name = course_name
        self.year_level = year_level
        self.units = units
        self.schedule = schedule
        self.room = room
        self.suggested_faculty = suggested_faculty
        self.reason = reason
        self.accepted = False


class SchedulingOptimizer:
    """Greedy load-balanced scheduler.

    Strategy:
      1. Sort courses by priority (higher year levels first, then by units).
      2. For each course, score eligible faculty by:
         - Remaining capacity (closer to target = better)
         - Lower current load = higher priority
         - Part-time faculty get lowest priority
      3. Assign to highest-scored faculty with no conflict.
    """

    @staticmethod
    def optimize(unassigned_courses, faculty_list):
        """Return list of ScheduleSuggestion objects.

        Parameters
        ----------
        unassigned_courses : list of Course
            Courses that need to be assigned.
        faculty_list : list of Faculty
            All faculty (including those already with courses loaded).
        """
        if not unassigned_courses or not faculty_list:
            return []

        # Work on copies so we don't mutate originals during scoring
        suggestions = []

        # Sort courses: higher year levels first, then more units first
        def course_priority(c):
            yr_order = YEAR_LEVELS.index(c.year_level) if c.year_level in YEAR_LEVELS else 99
            # BA 4 > MA 2 > BA 1 (more advanced = higher priority for assignment)
            return (-yr_order, -c.units)

        sorted_courses = sorted(unassigned_courses, key=course_priority)

        for course in sorted_courses:
            best_faculty = None
            best_score = -1
            best_reason = ""

            for fac in faculty_list:
                # Skip if schedule conflict
                if SchedulingOptimizer._has_conflict(fac, course):
                    continue

                # Part-time faculty: no load limit, but lowest priority
                if fac.classification == "Part-time":
                    score = 5
                    reason = "Only available option (part-time)"
                else:
                    remaining = fac.remaining_capacity()
                    if remaining <= 0 and fac.current_load() > 0:
                        # Already at/over capacity — only consider if desperate
                        score = 1
                        reason = f"Over capacity ({fac.current_load()}/{fac.required_load})"
                    else:
                        # Score based on how close to target
                        # Prefer faculty who need this course to reach target
                        if remaining >= course.units:
                            # This course fits perfectly
                            fill_ratio = course.units / max(1, remaining)
                            score = 50 + int(50 * fill_ratio)
                            reason = f"Fits remaining capacity ({fac.current_load()}+{course.units}/{fac.required_load})"
                        else:
                            # Would cause overload but still has room
                            score = 20 + max(0, 30 - fac.load_delta())
                            reason = f"Would overload ({fac.current_load()}+{course.units}/{fac.required_load})"

                if score > best_score:
                    best_score = score
                    best_faculty = fac
                    best_reason = reason

            if best_faculty:
                suggestions.append(ScheduleSuggestion(
                    course_name=course.name,
                    year_level=course.year_level,
                    units=course.units,
                    schedule=course.schedule,
                    room=course.room or '',
                    suggested_faculty=best_faculty.name,
                    reason=best_reason,
                ))
            else:
                suggestions.append(ScheduleSuggestion(
                    course_name=course.name,
                    year_level=course.year_level,
                    units=course.units,
                    schedule=course.schedule,
                    room=course.room or '',
                    suggested_faculty="(none available)",
                    reason="No eligible faculty found (all have conflicts or capacity issues)",
                ))

        return suggestions

    @staticmethod
    def _has_conflict(faculty, new_course):
        """Check if new_course conflicts with any of faculty's existing courses."""
        for c in faculty.courses:
            if c.schedule == new_course.schedule:
                return True
        return False


# ---------------------------------------------------------------------------
# Schedule Suggestions Dialog
# ---------------------------------------------------------------------------

class ScheduleSuggestDialog(QDialog):
    """Dialog to review and accept/reject auto-scheduler suggestions."""

    def __init__(self, suggestions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto-Schedule Suggestions")
        self.resize(850, 600)
        self.setModal(True)
        self.suggestions = suggestions
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Review suggested course assignments below. "
            "Check/uncheck each suggestion to accept or reject it, then click Apply."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Table of suggestions
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Accept", "Course", "Year Level", "Units", "Schedule", "Room", "Suggested Faculty"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)

        self.table.setRowCount(len(self.suggestions))
        for row, s in enumerate(self.suggestions):
            # Checkbox column
            cb_item = QTableWidgetItem()
            cb_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            cb_item.setCheckState(Qt.Checked if "(none)" not in s.suggested_faculty else Qt.Unchecked)
            self.table.setItem(row, 0, cb_item)

            name_item = QTableWidgetItem(s.course_name)
            name_item.setToolTip(s.reason)
            if "(none)" in s.suggested_faculty:
                name_item.setBackground(QColor(255, 200, 200))
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(s.year_level))
            self.table.setItem(row, 3, QTableWidgetItem(str(s.units)))
            self.table.setItem(row, 4, QTableWidgetItem(s.schedule))

            room_item = QTableWidgetItem(s.room)
            self.table.setItem(row, 5, room_item)

            fac_item = QTableWidgetItem(s.suggested_faculty)
            fac_item.setToolTip(s.reason)
            self.table.setItem(row, 6, fac_item)

        self.table.resizeRowsToContents()
        layout.addWidget(self.table)

        # Summary
        assigned = sum(1 for s in self.suggestions if "(none)" not in s.suggested_faculty)
        unassigned = len(self.suggestions) - assigned
        self.summary_label = QLabel(
            f"Total: {len(self.suggestions)}  |  "
            f"Can assign: {assigned}  |  "
            f"Cannot assign: {unassigned}"
        )
        layout.addWidget(self.summary_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Apply Selected")
        self.apply_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all_checks(Qt.Checked))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._set_all_checks(Qt.Unchecked))

        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _set_all_checks(self, state):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(state)

    def get_accepted_suggestions(self):
        """Return list of (suggestion, faculty_name) for checked items."""
        accepted = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                s = self.suggestions[row]
                if "(none)" not in s.suggested_faculty:
                    accepted.append(s)
        return accepted


# ---------------------------------------------------------------------------
# Google Calendar Integration
# ---------------------------------------------------------------------------

# Try to import Google API libraries; store availability flag
_GOOGLE_CALENDAR_AVAILABLE = False
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    _GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    pass

SCOPES = ['https://www.googleapis.com/auth/calendar.events']
GCAL_CLIENT_SECRET_FILE = 'client_secret.json'
GCAL_TOKEN_FILE = 'gcal_token.json'
GCAL_APP_NAME = 'FacultyWorkloadScheduler'


def get_gcal_service():
    """Authenticate and return a Google Calendar API service, or None on failure.

    Returns
    -------
        (service, message) tuple. On success: (service, None).
        On failure: (None, error_message).
    """
    if not _GOOGLE_CALENDAR_AVAILABLE:
        return None, ("Google Calendar libraries not installed.\n\n"
                      "Run: pip install google-auth-oauthlib google-api-python-client")

    creds = None
    token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), GCAL_TOKEN_FILE)

    # Load existing token
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            log.warning("Could not load token: %s", e)

    # If no (valid) credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                log.warning("Token refresh failed: %s", e)
                creds = None

        if not creds:
            client_secret_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), GCAL_CLIENT_SECRET_FILE
            )
            if not os.path.exists(client_secret_path):
                return None, (
                    f"Google Calendar client secret not found.\n\n"
                    f"Please place your 'client_secret.json' from the "
                    f"Google Cloud Console in the app directory:\n"
                    f"{os.path.dirname(os.path.abspath(__file__))}/\n\n"
                    f"Steps:\n"
                    f"1. Go to https://console.cloud.google.com/\n"
                    f"2. Create a project or select existing\n"
                    f"3. Enable 'Google Calendar API'\n"
                    f"4. Create OAuth 2.0 credentials (Desktop app type)\n"
                    f"5. Download JSON and save as '{GCAL_CLIENT_SECRET_FILE}'"
                )
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secret_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception as e:
                log.error("OAuth flow failed: %s", e)
                return None, f"OAuth authentication failed:\n{e}"

        # Save token
        try:
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
            log.info("Saved OAuth token to %s", token_path)
        except Exception as e:
            log.warning("Could not save token: %s", e)

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service, None
    except Exception as e:
        return None, f"Could not create Calendar service:\n{e}"


def sync_courses_to_gcal(service, faculty_list, semester_name, calendar_id='primary'):
    """Create calendar events for all courses, updating existing ones by course ID.

    Parameters
    ----------
        service : Google Calendar API service
        faculty_list : list of Faculty
        semester_name : str — for event description
        calendar_id : str — default 'primary'

    Returns
    -------
        (created, updated, skipped, errors) tuple of counts and messages.
    """
    created = 0
    updated = 0
    skipped = 0
    errors = []

    for fac in faculty_list:
        for course in fac.courses:
            try:
                event_id = f"fls_{fac._id}_{course._id}" if course._id else None
                start_dt, end_dt, days_str = _parse_schedule(course.schedule)

                if not start_dt or not end_dt:
                    skipped += 1
                    errors.append(f"Could not parse schedule '{course.schedule}' for {course.name}")
                    continue

                # Parse day codes
                day_list = GRID_DAY_INDICES.get(course.schedule.split()[0], [])
                if not day_list:
                    skipped += 1
                    continue

                # Build RRULE for recurring weekly
                byday = []
                for d in day_list:
                    weekday_map = {0: 'MO', 1: 'TU', 2: 'WE', 3: 'TH', 4: 'FR', 5: 'SA'}
                    byday.append(weekday_map[d])
                rrule = f"FREQ=WEEKLY;BYDAY={','.join(byday)}"

                event_body = {
                    'summary': f"{course.name} — {fac.name}",
                    'location': course.room or '',
                    'description': (
                        f"Course: {course.name}\n"
                        f"Faculty: {fac.name}\n"
                        f"Year Level: {course.year_level}\n"
                        f"Units: {course.units}\n"
                        f"Room: {course.room or '—'}\n"
                        f"Semester: {semester_name}\n"
                        f"Schedule: {course.schedule}"
                    ),
                    'start': {
                        'dateTime': start_dt.isoformat(),
                        'timeZone': 'Asia/Manila',
                    },
                    'end': {
                        'dateTime': end_dt.isoformat(),
                        'timeZone': 'Asia/Manila',
                    },
                    'recurrence': [f"RRULE:{rrule}"],
                }

                # Check if event already exists (via extendedProperties)
                if event_id:
                    # Try to find existing by custom ID
                    existing = service.events().list(
                        calendarId=calendar_id,
                        privateExtendedProperty=f'fls_id={event_id}',
                        maxResults=1
                    ).execute().get('items', [])

                    if existing:
                        e = existing[0]
                        # Update
                        service.events().update(
                            calendarId=calendar_id,
                            eventId=e['id'],
                            body=event_body
                        ).execute()
                        updated += 1
                    else:
                        # Create with extended property for tracking
                        event_body['extendedProperties'] = {
                            'private': {'fls_id': event_id}
                        }
                        service.events().insert(
                            calendarId=calendar_id,
                            body=event_body
                        ).execute()
                        created += 1
                else:
                    # No DB ID — just insert
                    service.events().insert(
                        calendarId=calendar_id,
                        body=event_body
                    ).execute()
                    created += 1

            except Exception as e:
                errors.append(f"Error syncing '{course.name}': {e}")
                skipped += 1

    return created, updated, skipped, errors


def _parse_schedule(schedule):
    """Parse a schedule string like 'MW 09:20am-10:50am'.

    Returns (start_datetime, end_datetime, day_codes_string) or (None, None, '').
    Uses a fixed Monday reference date.
    """
    if ' ' not in schedule:
        return None, None, ''
    day_code, time_range = schedule.split(None, 1)
    if '-' not in time_range:
        return None, None, ''

    start_str, end_str = time_range.split('-', 1)
    # Use a Monday reference (April 6, 2026 was a Monday)
    ref_date = datetime.date(2026, 4, 6)

    try:
        start_dt = datetime.datetime.combine(
            ref_date, datetime.datetime.strptime(start_str.strip(), "%I:%M%p").time()
        )
        end_dt = datetime.datetime.combine(
            ref_date, datetime.datetime.strptime(end_str.strip(), "%I:%M%p").time()
        )
        return start_dt, end_dt, day_code
    except (ValueError, IndexError):
        return None, None, ''


# ---------------------------------------------------------------------------
# Weekly Schedule Builder (shared helper for dialog + exports)
# ---------------------------------------------------------------------------

def build_timetable_grid(faculty_list):
    """Build a 2D grid of timetable data.

    Returns
    -------
        grid : dict[(day_index, timeslot_label)] -> list of (faculty_name, course)
        timeslot_labels : list of str — ordered time ranges
        day_headers : list of str — ['Mon', 'Tue', ..., 'Sat']
    """
    grid = defaultdict(list)
    for f in faculty_list:
        for c in f.courses:
            if ' ' not in c.schedule:
                continue
            day_code, time_slot = c.schedule.split(None, 1)
            if time_slot not in TIMESLOT_LABELS:
                continue
            day_indices = GRID_DAY_INDICES.get(day_code, ())
            for di in day_indices:
                grid[(di, time_slot)].append((f.name, c))
    return grid, TIMESLOT_LABELS, GRID_DAYS


def timetable_cell_text(entries):
    """Format entries for a timetable cell."""
    lines = []
    for fac_name, c in entries:
        room = c.room or ''
        parts = [f"{fac_name}: {c.name}"]
        if room:
            parts.append(f"({room})")
        lines.append(' '.join(parts))
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class FacultyWorkloadApp(QMainWindow):
    def __init__(self):
        log.info("Initialising FacultyWorkloadApp …")
        super().__init__()
        self.setWindowTitle("Faculty Workload & Scheduling")
        self.setGeometry(100, 100, 1280, 950)

        self.db = Database()
        self.semesters = self.db.load_semesters()
        self.active_semester = next((s for s in self.semesters if s.is_active), None)
        if not self.active_semester and self.semesters:
            self.active_semester = self.semesters[0]

        self.faculty_list = self.db.load_all_faculty()
        if self.active_semester:
            self.db.load_courses_for_semester(self.active_semester._id, self.faculty_list)

        self._is_dark = True
        self._suppress_cell_change = False

        # Google Calendar service (cached)
        self._gcal_service = None

        self._init_ui()
        self._refresh_all()
        log.info("Initialisation complete.")

    # -- UI construction ----------------------------------------------------

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)

        # === Top bar ===
        top_bar = QHBoxLayout()

        top_bar.addWidget(QLabel("Semester:"))
        self.semester_sel = QComboBox()
        self._populate_semester_sel()
        self.semester_sel.currentIndexChanged.connect(self._on_semester_changed)
        top_bar.addWidget(self.semester_sel)

        self.add_sem_btn = QPushButton("+ New")
        self.add_sem_btn.setMaximumWidth(80)
        self.add_sem_btn.clicked.connect(self._add_semester)
        top_bar.addWidget(self.add_sem_btn)

        self.del_sem_btn = QPushButton("Del Semester")
        self.del_sem_btn.setMaximumWidth(100)
        self.del_sem_btn.clicked.connect(self._delete_semester)
        top_bar.addWidget(self.del_sem_btn)

        top_bar.addStretch()

        self.import_btn = QPushButton("Import CSV…")
        self.import_btn.clicked.connect(self._bulk_import)
        top_bar.addWidget(self.import_btn)

        self.suggest_btn = QPushButton("Suggest Schedule")
        self.suggest_btn.clicked.connect(self._auto_schedule)
        top_bar.addWidget(self.suggest_btn)

        self.gcal_btn = QPushButton("Google Calendar")
        self.gcal_btn.clicked.connect(self._google_calendar_sync)
        top_bar.addWidget(self.gcal_btn)

        self.schedule_btn = QPushButton("Weekly View")
        self.schedule_btn.clicked.connect(self._show_weekly_schedule)
        top_bar.addWidget(self.schedule_btn)

        self.theme_btn = QPushButton("☀ Light")
        self.theme_btn.setMaximumWidth(80)
        self.theme_btn.clicked.connect(self._toggle_theme)
        top_bar.addWidget(self.theme_btn)

        main_layout.addLayout(top_bar)

        # === Input section ===
        input_split = QSplitter(Qt.Horizontal)

        # -- Faculty input --
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

        # -- Course input --
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
        self.year_level_cb = QComboBox()
        self.year_level_cb.addItems(YEAR_LEVELS)
        course_grid.addWidget(self.year_level_cb, 2, 1)
        course_grid.addWidget(QLabel("Units:"), 3, 0)
        self.units_cb = QComboBox()
        self.units_cb.addItems(UNIT_OPTIONS)
        course_grid.addWidget(self.units_cb, 3, 1)
        course_grid.addWidget(QLabel("Schedule:"), 4, 0)
        self.schedule_cb = QComboBox()
        self.schedule_cb.addItems(SCHEDULE_SLOTS)
        course_grid.addWidget(self.schedule_cb, 4, 1)
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

        # === Summary bar ===
        self.summary_label = QLabel()
        self.summary_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.summary_label.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        main_layout.addWidget(self.summary_label)

        # === Tables ===
        table_split = QSplitter(Qt.Vertical)

        fac_label = QLabel("<b>Faculty Workload</b> — double-click to edit")
        table_split.addWidget(fac_label)

        self.faculty_table = QTableWidget()
        self.faculty_table.setColumnCount(7)
        self.faculty_table.setHorizontalHeaderLabels(
            ["Name", "Classification", "Admin", "Req. Load", "Current Load", "Status", ""]
        )
        self.faculty_table.setColumnHidden(6, True)
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

        course_label = QLabel("<b>Course Assignments</b> — double-click to edit")
        table_split.addWidget(course_label)

        self.course_table = QTableWidget()
        self.course_table.setColumnCount(7)
        self.course_table.setHorizontalHeaderLabels(
            ["Faculty", "Course", "Year Level", "Units", "Schedule", "Room", ""]
        )
        self.course_table.setColumnHidden(6, True)
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

        # === Export / Action bar ===
        export_layout = QHBoxLayout()

        self.export_pdf_btn = QPushButton("Workload PDF")
        self.export_pdf_btn.clicked.connect(self._export_workload_pdf)
        export_layout.addWidget(self.export_pdf_btn)

        self.export_sched_pdf_btn = QPushButton("Schedule PDF")
        self.export_sched_pdf_btn.clicked.connect(self._export_schedule_pdf)
        export_layout.addWidget(self.export_sched_pdf_btn)

        self.export_timetable_png_btn = QPushButton("Timetable PNG")
        self.export_timetable_png_btn.clicked.connect(self._export_timetable_png)
        export_layout.addWidget(self.export_timetable_png_btn)

        self.export_csv_btn = QPushButton("CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        export_layout.addWidget(self.export_csv_btn)

        export_layout.addStretch()

        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setStyleSheet("color: #e57373;")
        self.clear_all_btn.clicked.connect(self._clear_all)
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
        if self.active_semester:
            idx = self.semester_sel.findData(self.active_semester._id)
            if idx >= 0:
                self.semester_sel.setCurrentIndex(idx)
        self.semester_sel.blockSignals(False)

    def _on_semester_changed(self, idx):
        if idx < 0 or not self.semesters:
            return
        sem_id = self.semester_sel.itemData(idx)
        if self.active_semester and sem_id == self.active_semester._id:
            return
        self.db.set_active_semester(sem_id)
        self.active_semester = next((s for s in self.semesters if s._id == sem_id), None)
        for f in self.faculty_list:
            f.courses.clear()
        if self.active_semester:
            self.db.load_courses_for_semester(self.active_semester._id, self.faculty_list)
        self._populate_semester_sel()
        self._refresh_all()
        log.info("Switched to semester: %s",
                 self.active_semester.name if self.active_semester else "None")

    def _add_semester(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Semester / Term")
        dlg.setModal(True)
        layout = QFormLayout(dlg)
        name_edit = QLineEdit()
        year = datetime.date.today().year
        name_edit.setPlaceholderText(f"e.g. AY {year}-{year+1} Sem 2")
        layout.addRow("Semester name:", name_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addRow(buttons)

        if dlg.exec_() != QDialog.Accepted:
            return
        name = name_edit.text().strip()
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
            fac_item.setFlags(fac_item.flags() & ~Qt.ItemIsEditable)
            self.course_table.setItem(row, 0, fac_item)

            name_item = QTableWidgetItem(course.name)
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            name_item.setData(Qt.UserRole, course._id)
            self.course_table.setItem(row, 1, name_item)
            self.course_table.setItem(row, 2, QTableWidgetItem(course.year_level))
            self.course_table.setItem(row, 3, QTableWidgetItem(str(course.units)))
            self.course_table.setItem(row, 4, QTableWidgetItem(course.schedule))
            self.course_table.setItem(row, 5, QTableWidgetItem(course.room))

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
        has_gcal = " ✓" if self._gcal_service else ""
        self.summary_label.setText(
            f"[{sem}]  Faculty: {total_fac}  |  Courses: {total_courses}  |  "
            f"Under: {under}  |  On target: {on_target}  |  Over: {over}  |  "
            f"Part-time: {pt}  |  Google Calendar:{has_gcal}"
        )

    # -- In-place editing (Facility) ---------------------------------------

    def _on_faculty_cell_edited(self, item):
        if self._suppress_cell_change:
            return
        row = item.row()
        col = item.column()
        if col > 2:
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

        try:
            if col == 0:
                if not new_value:
                    raise ValueError("Name cannot be empty")
                if new_value != faculty.name and any(f.name == new_value for f in self.faculty_list):
                    raise ValueError("A faculty member with this name already exists")
                faculty.name = new_value
            elif col == 1:
                if new_value not in CLASSIFICATIONS:
                    raise ValueError(f"Must be one of: {', '.join(CLASSIFICATIONS)}")
                faculty.classification = new_value
                faculty.required_load = faculty.calculate_required_load()
            elif col == 2:
                faculty.is_admin = new_value.lower() in ('yes', 'true', '1')
                faculty.required_load = faculty.calculate_required_load()

            self.db.update_faculty(faculty)
            log.info("Edited faculty %s", faculty.name)
            self._refresh_all()
        except ValueError as e:
            QMessageBox.warning(self, "Edit Error", str(e))
            self._refresh_all()

    # -- In-place editing (Course) -----------------------------------------

    def _on_course_cell_edited(self, item):
        if self._suppress_cell_change:
            return
        row = item.row()
        col = item.column()
        if col == 0:
            return

        id_item = self.course_table.item(row, 6)
        if not id_item:
            return
        course_id = int(id_item.text())

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
            if col == 1:
                if not new_value:
                    raise ValueError("Course name cannot be empty")
                course.name = new_value
            elif col == 2:
                if new_value not in YEAR_LEVELS:
                    raise ValueError(f"Year level must be one of: {', '.join(YEAR_LEVELS)}")
                course.year_level = new_value
            elif col == 3:
                units = int(new_value)
                if units not in (3, 6):
                    raise ValueError("Units must be 3 or 6")
                course.units = units
            elif col == 4:
                if new_value not in SCHEDULE_SLOTS:
                    raise ValueError(f"Not a valid schedule slot")
                course.schedule = new_value
            elif col == 5:
                course.room = new_value

            self.db.update_course(course)
            log.info("Edited course id=%s", course_id)
            self._refresh_all()
        except ValueError as e:
            QMessageBox.warning(self, "Edit Error", str(e))
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
            QMessageBox.warning(self, "Input Error",
                                "Please enter a course name and select a faculty.")
            return
        faculty = self._find_faculty_by_name(faculty_name)
        if not faculty:
            QMessageBox.warning(self, "Error", "Selected faculty not found.")
            return
        year_level = self.year_level_cb.currentText()
        units = int(self.units_cb.currentText())
        schedule = self.schedule_cb.currentText()
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

    # -- Bulk import --------------------------------------------------------

    def _bulk_import(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
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

            for i, row in enumerate(rows, start=2):
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

    # -- Auto-schedule suggestions ------------------------------------------

    def _auto_schedule(self):
        """Open the auto-scheduler dialog."""
        if not self.active_semester:
            QMessageBox.warning(self, "Error", "Please select a semester first.")
            return

        # Find all courses currently assigned this semester
        assigned_names = set()
        for f in self.faculty_list:
            for c in f.courses:
                assigned_names.add(c.name)

        # We'll suggest for courses that are NOT yet assigned.
        # In practice, the user might want to use this for NEW courses.
        # For now, we treat ALL possible courses as unassigned.
        # But that's not useful — let's instead ask the user what to do.

        # Simplest approach: treat the current list as "to optimize" and
        # suggest a better assignment, replacing current ones.
        # Alternative: let user input courses in a text area.

        # Let's implement a dialog where the user can paste course lines.
        dlg = QDialog(self)
        dlg.setWindowTitle("Auto-Schedule: Enter Courses")
        dlg.setMinimumSize(500, 300)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel(
            "Enter course details (one per line):\n"
            "Course Name, Year Level, Units, Schedule, Room (optional)\n"
            "Example: Philo 101, BA 1, 3, MW 07:40am-09:10am, F-203"
        ))

        self._suggest_edit = QTextEdit()
        self._suggest_edit.setPlaceholderText(
            "Philo 101, BA 1, 3, MW 07:40am-09:10am, F-203\n"
            "Math 102, BA 2, 3, TTh 09:20am-10:50am, M-105"
        )
        layout.addWidget(self._suggest_edit)

        # Preset: use all courses already assigned + some suggestions
        hint_text = ""
        for f in self.faculty_list:
            for c in f.courses:
                hint_text += f"{c.name}, {c.year_level}, {c.units}, {c.schedule}, {c.room}\n"
        if not hint_text:
            hint_text = "Philo 101, BA 1, 3, MW 07:40am-09:10am, F-203\n"
        self._suggest_edit.setPlainText(hint_text.rstrip('\n'))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec_() != QDialog.Accepted:
            return

        # Parse the input
        raw = self._suggest_edit.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "Error", "No courses entered.")
            return

        unassigned = []
        parse_errors = []
        for line in raw.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 4:
                parse_errors.append(f"Too few fields: {line}")
                continue
            cname = parts[0]
            yr = parts[1] if parts[1] in YEAR_LEVELS else "BA 1"
            try:
                u = int(parts[2])
                if u not in (3, 6):
                    u = 3
            except ValueError:
                u = 3
            sched = parts[3] if parts[3] in SCHEDULE_SLOTS else SCHEDULE_SLOTS[0]
            room = parts[4] if len(parts) > 4 else ''
            unassigned.append(Course(cname, yr, u, sched, room))

        if not unassigned:
            QMessageBox.warning(self, "Error", "No valid courses parsed.")
            return

        if parse_errors:
            log.warning("Parse errors: %s", parse_errors)

        # Run optimizer
        suggestions = SchedulingOptimizer.optimize(unassigned, self.faculty_list)

        if not suggestions:
            QMessageBox.information(self, "Result", "No suggestions could be generated.")
            return

        # Show dialog
        dlg2 = ScheduleSuggestDialog(suggestions, self)
        if dlg2.exec_() != QDialog.Accepted:
            return

        accepted = dlg2.get_accepted_suggestions()
        if not accepted:
            QMessageBox.information(self, "Result", "No suggestions were accepted.")
            return

        # Apply accepted suggestions
        applied = 0
        for s in accepted:
            faculty = self._find_faculty_by_name(s.suggested_faculty)
            if not faculty:
                log.warning("Faculty '%s' no longer exists", s.suggested_faculty)
                continue
            course = Course(s.course_name, s.year_level, s.units, s.schedule, s.room,
                            self.active_semester._id)
            # Check for conflict one more time
            if self._find_conflicts(faculty, course):
                log.warning("Conflict detected on apply for '%s'", s.course_name)
                continue
            self.db.add_course(faculty._id, course)
            faculty.courses.append(course)
            applied += 1

        self._refresh_all()
        QMessageBox.information(
            self, "Schedule Applied",
            f"{applied} of {len(accepted)} course(s) assigned successfully."
        )
        log.info("Auto-schedule: %d courses applied", applied)

    # -- Google Calendar Sync -----------------------------------------------

    def _google_calendar_sync(self):
        """Connect or sync with Google Calendar."""
        if not _GOOGLE_CALENDAR_AVAILABLE:
            QMessageBox.critical(
                self, "Dependencies Missing",
                "Google Calendar libraries not installed.\n\n"
                "Run:  pip install google-auth-oauthlib google-api-python-client"
            )
            return

        if self._gcal_service is None:
            # First-time connection
            service, err = get_gcal_service()
            if err:
                QMessageBox.critical(self, "Google Calendar Error", err)
                return
            self._gcal_service = service
            QMessageBox.information(
                self, "Connected",
                "Connected to Google Calendar successfully!\n\n"
                "Click the button again to sync your courses."
            )
            self._refresh_summary()
            log.info("Connected to Google Calendar")
            return

        # Already connected — sync courses
        if not self.active_semester:
            QMessageBox.warning(self, "Error", "No active semester to sync.")
            return

        # Quick sanity: make sure we have data
        total_courses = sum(len(f.courses) for f in self.faculty_list)
        if total_courses == 0:
            QMessageBox.information(self, "No Data", "No courses to sync.")
            return

        progress = QProgressDialog("Syncing to Google Calendar…", None, 0, 100, self)
        progress.setWindowTitle("Please wait")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)

        try:
            sem_name = self.active_semester.name
            created, updated, skipped, errors = sync_courses_to_gcal(
                self._gcal_service, self.faculty_list, sem_name
            )
            progress.setValue(90)

            msg = (f"Google Calendar sync complete.\n\n"
                   f"Events created: {created}\n"
                   f"Events updated: {updated}\n"
                   f"Skipped: {skipped}")
            if errors:
                msg += f"\n\nWarnings ({len(errors)}):\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    msg += f"\n... and {len(errors) - 5} more"
            QMessageBox.information(self, "Sync Complete", msg)
            log.info("Google Calendar sync: %d created, %d updated, %d skipped",
                     created, updated, skipped)
        except Exception as e:
            log.error("Google Calendar sync failed: %s", e)
            QMessageBox.critical(self, "Sync Failed", f"Error: {e}")
        finally:
            progress.setValue(100)

    # -- Weekly Schedule Dialog ---------------------------------------------

    def _show_weekly_schedule(self):
        if not self.faculty_list or not any(f.courses for f in self.faculty_list):
            QMessageBox.information(self, "No Data", "No courses assigned yet to display a schedule.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Weekly Schedule View")
        dlg.resize(1100, 700)

        layout = QVBoxLayout(dlg)

        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Show faculty:"))
        fac_filter = QComboBox()
        fac_filter.addItem("All Faculty")
        for f in self.faculty_list:
            fac_filter.addItem(f.name)
        filter_layout.addWidget(fac_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        timetable_widget = QWidget()
        timetable_layout = QVBoxLayout(timetable_widget)
        scroll.setWidget(timetable_widget)
        layout.addWidget(scroll)

        def rebuild_schedule():
            # Clear
            while timetable_layout.count():
                child = timetable_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            filter_name = fac_filter.currentText()
            if filter_name == "All Faculty":
                flist = self.faculty_list
            else:
                flist = [f for f in self.faculty_list if f.name == filter_name]

            if not flist:
                timetable_layout.addWidget(QLabel("No data to display."))
                return

            grid, _, _ = build_timetable_grid(flist)

            table = QTableWidget()
            table.setColumnCount(7)
            table.setHorizontalHeaderLabels(["Time"] + GRID_DAYS)
            table.setRowCount(len(TIMESLOT_LABELS))

            for row_idx, ts in enumerate(TIMESLOT_LABELS):
                table.setItem(row_idx, 0, QTableWidgetItem(ts))
                for col_idx in range(1, 7):
                    day_idx = col_idx - 1
                    entries = grid.get((day_idx, ts), [])
                    if entries:
                        text = timetable_cell_text(entries)
                        item = QTableWidgetItem(text)
                        item.setBackground(QColor(66, 133, 244, 80))
                        table.setItem(row_idx, col_idx, item)
                    else:
                        table.setItem(row_idx, col_idx, QTableWidgetItem(""))

            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            timetable_layout.addWidget(table)

        fac_filter.currentIndexChanged.connect(rebuild_schedule)
        rebuild_schedule()
        dlg.exec_()

    # -- Export: Workload PDF -----------------------------------------------

    @staticmethod
    def _pdf_table_style():
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), rl_colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), rl_colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), rl_colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 1, rl_colors.black),
        ])

    def _export_workload_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Workload PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return
        log.info("Exporting workload PDF to %s", file_path)
        try:
            doc = SimpleDocTemplate(file_path, pagesize=landscape(letter))
            styles = getSampleStyleSheet()
            elements = []
            sem_name = self.active_semester.name if self.active_semester else "All Semesters"
            elements.append(Paragraph(f"Faculty Workload Report — {sem_name}", styles['Title']))
            elements.append(Spacer(1, 12))

            headers = ["Name", "Class", "Admin", "Req", "Load", "Status"]
            data = [headers]
            for f in self.faculty_list:
                data.append([f.name, f.classification, "Yes" if f.is_admin else "No",
                             str(f.required_load), str(f.current_load()), f.load_status()])
            ft = RLTable(data)
            ft.setStyle(self._pdf_table_style())
            elements.append(Paragraph("<b>Faculty Workload</b>", styles['Heading2']))
            elements.append(ft)
            elements.append(Spacer(1, 16))

            course_headers = ["Faculty", "Course", "Year", "Units", "Schedule", "Room"]
            course_data = [course_headers]
            for f in self.faculty_list:
                for c in f.courses:
                    course_data.append([f.name, c.name, c.year_level, str(c.units),
                                        c.schedule, c.room or '—'])
            if len(course_data) > 1:
                ct = RLTable(course_data)
                ct.setStyle(self._pdf_table_style())
                elements.append(Paragraph("<b>Course Assignments</b>", styles['Heading2']))
                elements.append(ct)

            doc.build(elements)
            QMessageBox.information(self, "Export Successful", f"Workload PDF saved:\n{file_path}")
            log.info("Workload PDF export complete: %s", file_path)
        except Exception as e:
            log.error("Workload PDF export failed: %s", e)
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    # -- Export: Schedule PDF (timetable as PDF) ----------------------------

    def _export_schedule_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Schedule PDF", "", "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        has_data = any(f.courses for f in self.faculty_list)
        if not has_data:
            QMessageBox.information(self, "No Data", "No courses to export.")
            return

        log.info("Exporting schedule PDF to %s", file_path)
        try:
            doc = SimpleDocTemplate(file_path, pagesize=landscape(A4),
                                    leftMargin=20, rightMargin=20,
                                    topMargin=20, bottomMargin=20)
            styles = getSampleStyleSheet()
            elements = []

            sem_name = self.active_semester.name if self.active_semester else "All Semesters"
            title_style = ParagraphStyle('ScheduleTitle', parent=styles['Title'],
                                         alignment=TA_CENTER, fontSize=16)
            elements.append(Paragraph(f"Weekly Schedule — {sem_name}", title_style))
            elements.append(Spacer(1, 12))

            for fac in self.faculty_list:
                if not fac.courses:
                    continue
                elements.append(Paragraph(
                    f"<b>{fac.name}</b> — {fac.classification}",
                    styles['Heading3']
                ))
                elements.append(Spacer(1, 6))

                # Build timetable for this single faculty member
                grid, _, days = build_timetable_grid([fac])

                # Create table: rows = timeslots, cols = time label + days
                header = ["Time"] + days
                data = [header]
                for ts in TIMESLOT_LABELS:
                    row = [ts]
                    for day_idx in range(6):
                        entries = grid.get((day_idx, ts), [])
                        if entries:
                            text = ' / '.join(
                                f"{cn.name}" + (f" ({cn.room})" if cn.room else "")
                                for fn, cn in entries
                            )
                        else:
                            text = ''
                        row.append(text)
                    data.append(row)

                # Build column widths
                col_widths = [1.2 * inch] + [0.9 * inch] * 6

                t = RLTable(data, colWidths=col_widths, repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), rl_colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('BACKGROUND', (0, 1), (-1, -1), rl_colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), rl_colors.black),
                    ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.black),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    # Light fill for cells with content
                    *[('BACKGROUND', (c, r), (c, r), rl_colors.Color(0.85, 0.92, 1.0))
                      for r in range(1, len(data))
                      for c in range(1, len(header))
                      if data[r][c]],
                ]))
                elements.append(t)
                elements.append(Spacer(1, 16))

            doc.build(elements)
            QMessageBox.information(self, "Export Successful",
                                    f"Schedule PDF saved:\n{file_path}")
            log.info("Schedule PDF export complete: %s", file_path)
        except Exception as e:
            log.error("Schedule PDF export failed: %s", e)
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    # -- Export: Timetable PNG ----------------------------------------------

    def _export_timetable_png(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Timetable PNG", "", "PNG Images (*.png)"
        )
        if not file_path:
            return

        has_data = any(f.courses for f in self.faculty_list)
        if not has_data:
            QMessageBox.information(self, "No Data", "No courses to export.")
            return

        log.info("Exporting timetable PNG to %s", file_path)
        try:
            # Build the timetable QTableWidget
            table = QTableWidget()
            table.setColumnCount(7)
            table.setHorizontalHeaderLabels(["Time"] + GRID_DAYS)
            table.setRowCount(len(TIMESLOT_LABELS))

            grid, _, _ = build_timetable_grid(self.faculty_list)

            for row_idx, ts in enumerate(TIMESLOT_LABELS):
                time_item = QTableWidgetItem(ts)
                time_item.setFlags(Qt.ItemIsEnabled)
                font = time_item.font()
                font.setBold(True)
                font.setPointSize(9)
                time_item.setFont(font)
                table.setItem(row_idx, 0, time_item)

                for col_idx in range(1, 7):
                    day_idx = col_idx - 1
                    entries = grid.get((day_idx, ts), [])
                    if entries:
                        text = timetable_cell_text(entries)
                        item = QTableWidgetItem(text)
                        item.setBackground(QColor(220, 235, 255))
                        item.setFlags(Qt.ItemIsEnabled)
                        font2 = item.font()
                        font2.setPointSize(8)
                        item.setFont(font2)
                        table.setItem(row_idx, col_idx, item)
                    else:
                        empty = QTableWidgetItem("")
                        empty.setFlags(Qt.ItemIsEnabled)
                        table.setItem(row_idx, col_idx, empty)

            # Style the table
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setMinimumWidth(800)

            # Render to pixmap — show briefly then hide
            # Use a temporary dialog to ensure proper layout
            temp_dlg = QDialog(self)
            temp_dlg.setWindowFlags(Qt.FramelessWindowHint)
            temp_dlg.resize(900, 600)
            temp_layout = QVBoxLayout(temp_dlg)
            temp_layout.addWidget(table)
            temp_dlg.show()
            # Force layout
            QApplication.processEvents()

            # Compute full size
            table.resizeRowsToContents()
            table.resizeColumnsToContents()
            total_width = table.horizontalHeader().length() + 2
            total_height = table.verticalHeader().length() + 2
            table.setFixedSize(total_width, total_height)

            # Grab
            pixmap = QPixmap(table.size())
            pixmap.fill(Qt.white)
            painter = QPainter(pixmap)
            table.render(painter)
            painter.end()

            temp_dlg.hide()
            temp_dlg.deleteLater()

            pixmap.save(file_path, 'PNG')
            QMessageBox.information(self, "Export Successful",
                                    f"Timetable PNG saved:\n{file_path}")
            log.info("Timetable PNG export complete: %s", file_path)
        except Exception as e:
            log.error("Timetable PNG export failed: %s", e)
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    # -- Export: CSV --------------------------------------------------------

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

            QMessageBox.information(self, "Export Successful", f"Data exported to CSV:\n{file_path}")
            log.info("CSV export complete: %s", file_path)
        except Exception as e:
            log.error("CSV export failed: %s", e)
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    # -- Clear all ----------------------------------------------------------

    def _clear_all(self):
        reply = QMessageBox.warning(
            self, "Clear All Data",
            "This will permanently delete ALL faculty, course, and semester data.\n\n"
            "Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        reply2 = QMessageBox.question(self, "Confirm", "This cannot be undone. Proceed?",
                                       QMessageBox.Yes | QMessageBox.No)
        if reply2 != QMessageBox.Yes:
            return

        self.db.conn.execute("DELETE FROM courses")
        self.db.conn.execute("DELETE FROM faculty")
        self.db.conn.execute("DELETE FROM semesters")
        self.db.conn.commit()

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
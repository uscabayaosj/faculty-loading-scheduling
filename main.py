import sys
import os
import datetime
import logging
import tempfile
import sqlite3
import csv
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog, QStyleFactory
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer

def write_debug(message):
    home_dir = os.path.expanduser('~')
    log_path = os.path.join(home_dir, 'faculty_app_debug.log')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, 'a') as f:
        f.write(f"{timestamp} - {message}\n")

write_debug("Application starting...")
write_debug(f"Python version: {sys.version}")
write_debug(f"Current working directory: {os.getcwd()}")
write_debug(f"Executable path: {sys.executable}")
write_debug(f"sys.path: {sys.path}")

def get_temp_dir():
    if getattr(sys, 'frozen', False):
        # we are running in a bundle
        bundle_dir = sys._MEIPASS
    else:
        # we are running in a normal Python environment
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
    
    custom_temp_dir = os.path.join(bundle_dir, 'temp')
    try:
        os.makedirs(custom_temp_dir, exist_ok=True)
    except Exception as e:
        write_debug(f"Error creating temp directory: {str(e)}")
        custom_temp_dir = tempfile.gettempdir()
    
    return custom_temp_dir

custom_temp_dir = get_temp_dir()
os.environ['TMPDIR'] = custom_temp_dir
tempfile.tempdir = custom_temp_dir

write_debug(f"Custom temporary directory: {custom_temp_dir}")
write_debug(f"Temporary directory exists: {os.path.exists(custom_temp_dir)}")
write_debug(f"Temporary directory permissions: {oct(os.stat(custom_temp_dir).st_mode)[-3:]}")

write_debug("All modules imported successfully")

# Log some initial information
logging.debug(f"Current working directory: {os.getcwd()}")
logging.debug(f"Home directory: {os.path.expanduser('~')}")
logging.debug(f"Temporary directory: {tempfile.gettempdir()}")

class Course:
    def __init__(self, name, year_level, units, schedule):
        self.name = name
        self.year_level = year_level
        self.units = units
        self.schedule = schedule

class Faculty:
    def __init__(self, name, classification, is_admin=False):
        self.name = name
        self.classification = classification
        self.is_admin = is_admin
        self.courses = []
        self.required_load = self.calculate_required_load()

    def calculate_required_load(self):
        if self.classification == "Full-time PhD":
            return 15 - (12 if self.is_admin else 0)
        elif self.classification == "Full-time MA":
            return 18 - (12 if self.is_admin else 0)
        else:  # Part-time
            return 0

    def current_load(self):
        return sum(course.units for course in self.courses)

    def load_status(self):
        current = self.current_load()
        if current < self.required_load:
            return f"Below required ({self.required_load - current} units short)"
        elif current > self.required_load:
            return f"Overload ({current - self.required_load} units excess)"
        else:
            return "Satisfied"

class FacultyWorkloadApp(QMainWindow):
    def __init__(self):
        write_debug("Initializing FacultyWorkloadApp...")
        super().__init__()
        write_debug("Setting up UI...")
        self.setWindowTitle("Faculty Workload and Scheduling Application")
        self.setGeometry(100, 100, 1000, 800)
        self.faculty_list = []
        write_debug("Connecting to database...")
        self.db_connection = sqlite3.connect('faculty_workload.db')
        write_debug("Creating tables...")
        self.create_tables()
        write_debug("Loading data from database...")
        self.load_data_from_db()
        write_debug("Initializing UI...")
        self.initUI()
        write_debug("Setting dark theme...")
        self.set_dark_theme()
        write_debug("FacultyWorkloadApp initialization complete.")

    def set_dark_theme(self):
        write_debug("Setting dark theme...")
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
        write_debug("Dark theme set.")

    def create_tables(self):
        cursor = self.db_connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                classification TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY,
                faculty_id INTEGER,
                name TEXT NOT NULL,
                year_level TEXT NOT NULL,
                units INTEGER NOT NULL,
                schedule TEXT NOT NULL,
                FOREIGN KEY (faculty_id) REFERENCES faculty (id)
            )
        ''')
        self.db_connection.commit()

    def load_data_from_db(self):
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT * FROM faculty")
        faculty_data = cursor.fetchall()
        for faculty in faculty_data:
            f = Faculty(faculty[1], faculty[2], faculty[3])
            cursor.execute("SELECT * FROM courses WHERE faculty_id = ?", (faculty[0],))
            courses_data = cursor.fetchall()
            for course in courses_data:
                c = Course(course[2], course[3], course[4], course[5])
                f.courses.append(c)
            self.faculty_list.append(f)

    def save_data_to_db(self):
        cursor = self.db_connection.cursor()
        cursor.execute("DELETE FROM faculty")
        cursor.execute("DELETE FROM courses")
        for faculty in self.faculty_list:
            cursor.execute('''
                INSERT INTO faculty (name, classification, is_admin)
                VALUES (?, ?, ?)
            ''', (faculty.name, faculty.classification, faculty.is_admin))
            faculty_id = cursor.lastrowid
            for course in faculty.courses:
                cursor.execute('''
                    INSERT INTO courses (faculty_id, name, year_level, units, schedule)
                    VALUES (?, ?, ?, ?, ?)
                ''', (faculty_id, course.name, course.year_level, course.units, course.schedule))
        self.db_connection.commit()

    def initUI(self):
        write_debug("Starting initUI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        # Faculty Input Section
        faculty_layout = QHBoxLayout()
        self.faculty_name_input = QLineEdit()
        self.faculty_classification = QComboBox()
        self.faculty_classification.addItems(["Full-time PhD", "Full-time MA", "Part-time"])
        self.is_admin_checkbox = QComboBox()
        self.is_admin_checkbox.addItems(["Not Admin", "Admin"])
        add_faculty_button = QPushButton("Add Faculty")
        add_faculty_button.clicked.connect(self.add_faculty)

        faculty_layout.addWidget(QLabel("Name:"))
        faculty_layout.addWidget(self.faculty_name_input)
        faculty_layout.addWidget(QLabel("Classification:"))
        faculty_layout.addWidget(self.faculty_classification)
        faculty_layout.addWidget(QLabel("Admin Status:"))
        faculty_layout.addWidget(self.is_admin_checkbox)
        faculty_layout.addWidget(add_faculty_button)

        layout.addLayout(faculty_layout)

        # Course Input Section
        course_layout = QHBoxLayout()
        self.course_name_input = QLineEdit()
        self.year_level = QComboBox()
        self.year_level.addItems(["BA 1", "BA 2", "BA 3", "BA 4", "MA 1", "MA 2"])
        self.units = QComboBox()
        self.units.addItems(["3", "6"])
        self.schedule = QComboBox()
        self.schedule.addItems([
            "MW 07:40am-09:10am", "MW 09:20am-10:50am", "MW 12:25pm-01:55pm", "MW 02:05pm-03:35pm",
            "TTh 07:40am-09:10am", "TTh 09:20am-10:50am", "TTh 12:25pm-01:55pm", "TTh 02:05pm-03:35pm",
            "TTh 03:45pm-05:15pm", "TTh 05:50pm-07:20pm", "TTh 07:30pm-09:00pm",
            "Sat 09:00am-12:00pm", "Sat 01:00pm-04:00pm", "Sat 05:00pm-08:00pm"
        ])
        self.faculty_select = QComboBox()
        add_course_button = QPushButton("Add Course")
        add_course_button.clicked.connect(self.add_course)

        course_layout.addWidget(QLabel("Course:"))
        course_layout.addWidget(self.course_name_input)
        course_layout.addWidget(QLabel("Year:"))
        course_layout.addWidget(self.year_level)
        course_layout.addWidget(QLabel("Units:"))
        course_layout.addWidget(self.units)
        course_layout.addWidget(QLabel("Schedule:"))
        course_layout.addWidget(self.schedule)
        course_layout.addWidget(QLabel("Faculty:"))
        course_layout.addWidget(self.faculty_select)
        course_layout.addWidget(add_course_button)

        layout.addLayout(course_layout)

        # Faculty Workload Table
        self.faculty_table = QTableWidget()
        self.faculty_table.setColumnCount(5)
        self.faculty_table.setHorizontalHeaderLabels(["Name", "Classification", "Admin", "Current Load", "Status"])
        layout.addWidget(self.faculty_table)

        # Course Schedule Table
        self.course_table = QTableWidget()
        self.course_table.setColumnCount(5)
        self.course_table.setHorizontalHeaderLabels(["Faculty", "Course", "Year", "Units", "Schedule"])
        layout.addWidget(self.course_table)

        # Export Buttons
        export_layout = QHBoxLayout()
        export_pdf_button = QPushButton("Export to PDF")
        export_csv_button = QPushButton("Export to CSV")
        export_pdf_button.clicked.connect(self.export_pdf)
        export_csv_button.clicked.connect(self.export_csv)
        export_layout.addWidget(export_pdf_button)
        export_layout.addWidget(export_csv_button)
        layout.addLayout(export_layout)

        central_widget.setLayout(layout)

        self.update_faculty_table()
        self.update_course_table()
        self.update_faculty_select()

        write_debug("initUI complete.")

    def add_faculty(self):
        name = self.faculty_name_input.text()
        classification = self.faculty_classification.currentText()
        is_admin = self.is_admin_checkbox.currentText() == "Admin"
        
        if name:
            if any(f.name == name for f in self.faculty_list):
                QMessageBox.warning(self, "Input Error", "A faculty member with this name already exists.")
            else:
                faculty = Faculty(name, classification, is_admin)
                self.faculty_list.append(faculty)
                self.update_faculty_table()
                self.update_faculty_select()
                self.faculty_name_input.clear()
                self.save_data_to_db()
        else:
            QMessageBox.warning(self, "Input Error", "Please enter a faculty name.")

    def add_course(self):
        course_name = self.course_name_input.text()
        year_level = self.year_level.currentText()
        units = int(self.units.currentText())
        schedule = self.schedule.currentText()
        faculty_name = self.faculty_select.currentText()

        if course_name and faculty_name:
            course = Course(course_name, year_level, units, schedule)
            faculty = next((f for f in self.faculty_list if f.name == faculty_name), None)
            
            if faculty:
                if self.check_schedule_conflict(faculty, course):
                    QMessageBox.warning(self, "Schedule Conflict", "This course conflicts with the faculty's existing schedule.")
                else:
                    faculty.courses.append(course)
                    self.update_faculty_table()
                    self.update_course_table()
                    self.course_name_input.clear()
                    self.save_data_to_db()
            else:
                QMessageBox.warning(self, "Faculty Not Found", "Selected faculty not found.")
        else:
            QMessageBox.warning(self, "Input Error", "Please enter all course details and select a faculty.")

    def check_schedule_conflict(self, faculty, new_course):
        # Check for conflicts within the same faculty's schedule
        for course in faculty.courses:
            if course.schedule == new_course.schedule:
                return True
            if course.year_level == new_course.year_level and course.schedule.split()[0] == new_course.schedule.split()[0]:
                return True
        
        # Check for conflicts with other faculty members' schedules
        for other_faculty in self.faculty_list:
            if other_faculty != faculty:  # Skip the current faculty
                for course in other_faculty.courses:
                    if course.year_level == new_course.year_level and course.schedule == new_course.schedule:
                        return True
        
        return False

    def update_faculty_table(self):
        self.faculty_table.setRowCount(len(self.faculty_list))
        for row, faculty in enumerate(self.faculty_list):
            self.faculty_table.setItem(row, 0, QTableWidgetItem(faculty.name))
            self.faculty_table.setItem(row, 1, QTableWidgetItem(faculty.classification))
            self.faculty_table.setItem(row, 2, QTableWidgetItem("Yes" if faculty.is_admin else "No"))
            self.faculty_table.setItem(row, 3, QTableWidgetItem(str(faculty.current_load())))
            self.faculty_table.setItem(row, 4, QTableWidgetItem(faculty.load_status()))

    def update_course_table(self):
        courses = [course for faculty in self.faculty_list for course in faculty.courses]
        self.course_table.setRowCount(len(courses))
        for row, course in enumerate(courses):
            faculty = next(f for f in self.faculty_list if course in f.courses)
            self.course_table.setItem(row, 0, QTableWidgetItem(faculty.name))
            self.course_table.setItem(row, 1, QTableWidgetItem(course.name))
            self.course_table.setItem(row, 2, QTableWidgetItem(course.year_level))
            self.course_table.setItem(row, 3, QTableWidgetItem(str(course.units)))
            self.course_table.setItem(row, 4, QTableWidgetItem(course.schedule))

    def update_faculty_select(self):
        self.faculty_select.clear()
        self.faculty_select.addItems([faculty.name for faculty in self.faculty_list])

    def export_pdf(self):
        write_debug("Starting PDF export...")
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if file_path:
            write_debug(f"Saving PDF to: {file_path}")
            try:
                doc = SimpleDocTemplate(file_path, pagesize=letter)
                elements = []

                # Faculty Table
                write_debug("Creating faculty table...")
                faculty_data = [["Name", "Classification", "Admin", "Current Load", "Status"]]
                for faculty in self.faculty_list:
                    faculty_data.append([
                        faculty.name,
                        faculty.classification,
                        "Yes" if faculty.is_admin else "No",
                        str(faculty.current_load()),
                        faculty.load_status()
                    ])
                faculty_table = Table(faculty_data)
                faculty_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('TOPPADDING', (0, 1), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(faculty_table)
                write_debug("Adding Spacer...")
                elements.append(Spacer(1, 20))

                # Course Table
                write_debug("Creating course table...")
                course_data = [["Faculty", "Course", "Year", "Units", "Schedule"]]
                for faculty in self.faculty_list:
                    for course in faculty.courses:
                        course_data.append([
                            faculty.name,
                            course.name,
                            course.year_level,
                            str(course.units),
                            course.schedule
                        ])
                course_table = Table(course_data)
                course_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('TOPPADDING', (0, 1), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(course_table)

                write_debug("Building PDF...")
                doc.build(elements)
                write_debug("PDF export completed successfully.")
                QMessageBox.information(self, "Export Successful", f"Data exported to PDF: {file_path}")
            except Exception as e:
                write_debug(f"Error during PDF export: {str(e)}")
                QMessageBox.critical(self, "Export Failed", f"An error occurred while exporting to PDF: {str(e)}")

    def export_csv(self):
        write_debug("Starting CSV export...")
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if file_path:
            write_debug(f"Saving CSV to: {file_path}")
            try:
                with open(file_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["Faculty Information"])
                    writer.writerow(["Name", "Classification", "Admin", "Current Load", "Status"])
                    for faculty in self.faculty_list:
                        writer.writerow([
                            faculty.name,
                            faculty.classification,
                            "Yes" if faculty.is_admin else "No",
                            faculty.current_load(),
                            faculty.load_status()
                        ])
                    writer.writerow([])
                    writer.writerow(["Course Information"])
                    writer.writerow(["Faculty", "Course", "Year", "Units", "Schedule"])
                    for faculty in self.faculty_list:
                        for course in faculty.courses:
                            writer.writerow([
                                faculty.name,
                                course.name,
                                course.year_level,
                                course.units,
                                course.schedule
                            ])
                write_debug("CSV export completed successfully.")
                QMessageBox.information(self, "Export Successful", f"Data exported to CSV: {file_path}")
            except Exception as e:
                write_debug(f"Error during CSV export: {str(e)}")
                QMessageBox.critical(self, "Export Failed", f"An error occurred while exporting to CSV: {str(e)}")

    def closeEvent(self, event):
        write_debug("Closing application...")
        self.save_data_to_db()
        self.db_connection.close()
        write_debug("Application closed.")
        super().closeEvent(event)

if __name__ == "__main__":
    try:
        write_debug("Creating application instance...")
        app = QApplication(sys.argv)
        write_debug("Creating main window...")
        ex = FacultyWorkloadApp()
        write_debug("Showing main window...")
        ex.show()
        write_debug("Entering main event loop...")
        sys.exit(app.exec_())
    except Exception as e:
        write_debug(f"Error in main execution: {str(e)}")
        raise

write_debug("Application ending...")
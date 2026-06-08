# Faculty Workload and Scheduling Application

A **PyQt5** desktop application for managing faculty workloads, course assignments, and class schedules at the tertiary level. Built for academic department chairs, secretaries, and administrators who need a quick, offline way to track teaching loads, detect scheduling conflicts, and export reports.

> **Author:** Ulysses Cabayao, SJ — Ateneo de Davao University  
> **License:** Educational use

---

## Features

| Feature | Description |
|---|---|
| **Faculty Management** | Add, view, edit, and delete faculty members with classification and admin status |
| **Course Assignment** | Assign courses to faculty with year level, units, schedule slot, and room |
| **Workload Tracking** | Automatically calculates required vs. current load per faculty member |
| **Visual Load Status** | Colour-coded table cells — 🟢 green (on target), 🟡 amber (under), 🔴 red (over) |
| **Schedule Conflict Detection** | Blocks conflicting assignments (same timeslot for same year level) |
| **In-Place Editing** | Double-click any cell in the faculty or course table to edit — persists immediately |
| **Semester / Term Management** | Create, switch, and delete academic terms; course data is scoped per semester |
| **Bulk Import from CSV** | Import faculty and course data from a structured CSV file |
| **Weekly Schedule View** | A visual timetable grid showing all courses by day and timeslot, filterable by faculty |
| **Room / Location Tracking** | Each course can have a room assigned (e.g., F-203) |
| **Dark / Light Theme Toggle** | Switch between dark Fusion and light themes with one click |
| **Sortable Tables** | Click any column header to sort by that field |
| **Right-Click Context Menus** | Delete faculty or courses directly from the table |
| **Summary Bar** | Live counts: total faculty, courses, under/on-target/over breakdown |
| **PDF Export** | Professional two-table report (faculty workload + course assignments with rooms) |
| **CSV Export** | Machine-readable spreadsheet export |
| **Persistent Storage** | SQLite database with WAL mode for safe, fast reads |

---

## Screenshot

*(Add a screenshot of the running application here)*

```
┌──────────────────────────────────────────────────────────────────┐
│ [Semester: AY 2025-2026 Sem 1 ▼] [+New] [Del]    [Import] [Sched] [☀] │
├──────────────────────┬───────────────────────────────────────────┤
│ Add / Edit Faculty   │ Add Course                                │
│ ┌──────────────────┐ │ ┌───────────────────────────────────────┐ │
│ │ Name: [________] │ │ │ Faculty: [___________    ▼]          │ │
│ │ Class:  [_____ ▼]│ │ │ Course:  [___________               ]│ │
│ │ ☐ Admin          │ │ │ Year:    [______ ▼]                  │ │
│ │ [Add] [Delete..]  │ │ │ Units:   [___ ▼]                    │ │
│ └──────────────────┘ │ │ Schedule:[________________ ▼]        │ │
│                      │ │ Room:    [___________               ]│ │
│                      │ │ [Add] [Delete Selected]              │ │
│                      │ └───────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│ [AY 2025-2026 Sem 1] Faculty: 5 | Courses: 24 | Under:1 | OK:3 |Over:1│
├──────────────────────────────────────────────────────────────────┤
│ Faculty Workload — double-click to edit                          │
│ ┌──────┬──────────┬────┬──────┬───┬──────────┐                  │
│ │ Name │ Class    │Adm │ Req. │Curr│ ██ Status│                  │
│ ├──────┼──────────┼────┼──────┼───┼──────────┤                  │
│ │ ...  │ ...      │... │ ...  │... │ ██color██│                  │
│ └──────┴──────────┴────┴──────┴───┴──────────┘                  │
│ Course Assignments — double-click to edit                        │
│ ┌────┬──────┬────┬────┬──────────┬─────┐                        │
│ │Fac │Course│Year│Un. │ Schedule │Room │                        │
│ └────┴──────┴────┴────┴──────────┴─────┘                        │
├──────────────────────────────────────────────────────────────────┤
│ [Export to PDF] [Export to CSV]                   [Clear All]   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Installation

### Prerequisites

- **Python 3.8+**
- **pip** (Python package installer)

### Setup

```sh
# 1. Clone the repository
git clone https://github.com/uscabayaosj/faculty-loading-scheduling.git
cd faculty-loading-scheduling

# 2. (Recommended) Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install PyQt5 reportlab
```

### Running the Application

```sh
python main.py
```

The database (`faculty_workload.db`) is created automatically in the current working directory on first launch.

---

## Usage Guide

### Semester Management
Use the top bar to manage academic terms:
- **Semester dropdown** — Switch between semesters. Courses are scoped per semester; faculty members persist across all semesters.
- **+ New Semester** — Create a new semester (e.g., "AY 2025-2026 Sem 2").
- **Delete Semester** — Remove the current semester. Courses in it are unlinked (not deleted).

### Adding Faculty
1. Enter the faculty member's **Name**.
2. Select their **Classification** (Full-time PhD / Full-time MA / Part-time).
3. Check **Admin** if they hold an administrative role (reduces teaching load).
4. Click **Add Faculty**.

### Adding Courses
1. Select the **Faculty** member from the dropdown.
2. Enter the **Course** name (e.g., *Philo 101*).
3. Choose the **Year Level** (BA 1–4, MA 1–2).
4. Set **Units** (3 or 6).
5. Pick a **Schedule** slot from the preset list (MW/TTh/Sat timeslots).
6. Optionally enter a **Room** (e.g., F-203).
7. Click **Add Course**.

### Editing In-Place
- **Double-click** any cell in the Faculty or Course table to edit it directly.
- Changes are validated and saved to the database immediately.
- Faculty editable fields: Name, Classification, Admin (Yes/No).
- Course editable fields: Course Name, Year Level, Units, Schedule, Room.

### Deleting Items
- **Faculty:** Select a row in the Faculty table, then click **Delete Selected** (or right-click).
- **Courses:** Select a row in the Course table, then click **Delete Selected** (or right-click).

### Bulk Import from CSV

Prepare a CSV file with the following columns (header required):

```csv
Faculty Name,Classification,Is Admin,Course Name,Year Level,Units,Schedule,Room
Juan dela Cruz,Full-time PhD,Yes,Philo 101,BA 1,3,MW 07:40am-09:10am,F-203
Maria Santos,Full-time MA,No,Math 101,BA 1,3,TTh 09:20am-10:50am,M-105
```

Then click **Import CSV…** and select your file. A sample template (`sample_import.csv`) is included in the repository.

### Weekly Schedule View
Click **Weekly Schedule** to open a visual timetable grid:
- Rows = daily time slots (07:40am–09:10pm)
- Columns = Monday through Saturday
- Shows all assigned courses with faculty name, course name, and room
- Use the dropdown to filter by a specific faculty member

### Viewing Load Status
The **Status** column in the Faculty table is colour-coded:
- 🟢 **Green** — Load is on target
- 🟡 **Amber** — Below required load
- 🔴 **Red** — Overload
- ⚫ **Grey** — Part-time (no required load)

### Theme Toggle
Click **☀ Light** / **☾ Dark** in the top-right corner to switch between themes.

### Exporting
- **PDF:** Produces a two-section report (faculty workloads + course assignments with rooms).
- **CSV:** Writes a structured CSV file readable by Excel, Google Sheets, etc.

### Clearing All Data
Click **Clear All Data** (bottom-right). This requires two confirmations, then resets to a fresh default semester.

---

## How It Works

### Architecture (single-file, ~700 lines)

```
main.py
  ├── setup_logging()           — File + stream logging
  ├── get_temp_dir()            — Temp directory (PyInstaller-aware)
  ├── Semester class            — Data model for term management
  ├── Course class              — Data model with room field
  ├── Faculty class             — Data model + load calculations
  ├── Database class            — SQLite CRUD with semester scoping
  ├── WeeklyScheduleDialog      — Timetable grid pop-up
  ├── AddSemesterDialog         — Semester creation dialog
  └── FacultyWorkloadApp class  — PyQt5 GUI (QMainWindow)
        ├── UI construction with top bar
        ├── Semester switching
        ├── In-place editing via cellChanged signals
        ├── Faculty add / delete / edit
        ├── Course add / delete / edit with conflict detection
        ├── Bulk CSV import
        ├── Weekly schedule view
        ├── Dark/light theme toggle
        ├── PDF / CSV export
        └── Clear all / close events
```

### Database Schema

#### `semesters` table
| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Row ID |
| name | TEXT (UNIQUE) | e.g., "AY 2025-2026 Sem 1" |
| is_active | INTEGER | 1 if currently selected |

#### `faculty` table
| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Row ID |
| name | TEXT (UNIQUE) | Faculty member's name |
| classification | TEXT | Full-time PhD / Full-time MA / Part-time |
| is_admin | INTEGER | 1 if administrator |

#### `courses` table
| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Row ID |
| faculty_id | INTEGER (FK) | Owning faculty member |
| semester_id | INTEGER (FK) | Owning semester (nullable) |
| name | TEXT | Course name |
| year_level | TEXT | e.g., BA 1, MA 2 |
| units | INTEGER | 3 or 6 |
| schedule | TEXT | Timeslot string |
| room | TEXT | Room/location (optional) |

### Key Design Decisions

- **Semester-scoped courses** — Faculty persist across semesters; course assignments belong to a specific term. Switching semesters reloads only that term's courses.
- **Targeted DB operations** — Each add/edit/delete issues a single INSERT/UPDATE/DELETE instead of wiping and reloading.
- **Single JOIN query for loading** — Faculty loaded in one query; courses loaded per semester in one query (no N+1).
- **In-place editing** — `cellChanged` signals are debounced via a `_suppress_cell_change` guard to avoid recursive triggers during table rebuilds.
- **Colour-coded status** — Brushes applied to the Status column for instant visual parsing.
- **WAL journal mode** — Enables concurrent reads during writes without locking.

---

## Comparison: Original vs. Previous vs. Current

| Feature | Original | Previous (Round 1) | Current (Round 2) |
|---|---|---|---|
| DB save strategy | Full DELETE+reINSERT | Targeted INSERT/DELETE | ✓ + UPDATE for edits |
| DB load strategy | N+1 queries | Single JOIN | ✓ Semester-filtered JOIN |
| Delete items | ❌ | ✅ Buttons + context menus | ✓ + In-place delete |
| Edit items | ❌ | ❌ | ✅ Double-click in-place |
| Semester management | ❌ | ❌ | ✅ Create, switch, delete |
| Bulk CSV import | ❌ | ❌ | ✅ With conflict detection |
| Weekly schedule view | ❌ | ❌ | ✅ Timetable grid dialog |
| Room/location | ❌ | ❌ | ✅ Per-course room field |
| Theme toggle | ❌ | ❌ | ✅ Dark/Light switch |
| Table sorting | ❌ | ✅ Click-to-sort | ✓ |
| Visual load status | ❌ | ✅ Colour-coded | ✓ |
| Summary bar | ❌ | ✅ Live counts | ✓ + semester label |
| Admin selector | Dropdown | Checkbox | ✓ |
| Context menus | ❌ | ✅ Right-click | ✓ |
| PDF export | ✅ (no room) | ✅ (no room) | ✓ Includes rooms |
| Logging | Raw file writes | Python logging module | ✓ |
| README accuracy | Wrong filenames | Accurate | ✓ Fully updated |

---

## Sample CSV Import Template

A `sample_import.csv` file is included in the repository:

```csv
Faculty Name,Classification,Is Admin,Course Name,Year Level,Units,Schedule,Room
Juan dela Cruz,Full-time PhD,Yes,Philo 101,BA 1,3,MW 07:40am-09:10am,F-203
Juan dela Cruz,Full-time PhD,Yes,Philo 102,BA 2,3,TTh 09:20am-10:50am,F-204
Maria Santos,Full-time MA,No,Math 101,BA 1,3,MW 09:20am-10:50am,M-105
Maria Santos,Full-time MA,No,Math 102,BA 2,3,TTh 07:40am-09:10am,M-105
Pedro Reyes,Part-time,No,Eng 101,BA 1,3,Sat 09:00am-12:00pm,E-301
```

---

## Roadmap (Completed)

All items from the original roadmap are now implemented:
- ✅ Edit faculty/course in place (double-click table cells)
- ✅ Bulk import from CSV
- ✅ Semester/term management
- ✅ Printable weekly schedule view per faculty
- ✅ Room/location tracking
- ✅ Dark/Light theme toggle

### Future Ideas

- [ ] Export schedule as PDF (separate from workload report)
- [ ] Export timetable as image (PNG)
- [ ] Multi-user / network shared database
- [ ] Auto-generate optimal schedule suggestions
- [ ] Integration with Google Calendar

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **"No module named PyQt5"** | Run `pip install PyQt5` (in your virtual environment) |
| **"No module named reportlab"** | Run `pip install reportlab` |
| **Cannot add faculty** | Check that the name field is non-empty and not a duplicate |
| **Cannot add course** | Ensure at least one faculty and semester exist, and the course name is non-empty |
| **Schedule conflict warning** | The timeslot or year-level/day combination already exists for that faculty |
| **In-place edit rejected** | Check the validation message — classification must be Full-time PhD/MA or Part-time, units must be 3 or 6, year level must match the list |
| **Import fails** | Ensure CSV uses UTF-8 encoding and has the exact header row shown above |
| **Export fails** | Ensure you have write permissions for the target directory |
| **App won't start / crashes** | Check `~/faculty_app_debug.log` for stack traces |

---

## Contributing

Suggestions, bug reports, and pull requests are welcome via [GitHub Issues](https://github.com/uscabayaosj/faculty-loading-scheduling/issues).
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
| **Auto-Schedule Suggestions** | Greedy load-balanced algorithm suggests optimal course-to-faculty assignments with a review dialog |
| **Google Calendar Sync** | Push course assignments to Google Calendar as recurring weekly events via OAuth2 |
| **Schedule PDF Export** | Per-faculty weekly timetable rendered as a professional PDF |
| **Timetable PNG Export** | Full-colour timetable grid exported as a PNG image |
| **Dark / Light Theme Toggle** | Switch between dark Fusion and light themes with one click |
| **Sortable Tables** | Click any column header to sort by that field |
| **Right-Click Context Menus** | Delete faculty or courses directly from the table |
| **Summary Bar** | Live counts: total faculty, courses, under/on-target/over breakdown |
| **Workload PDF Export** | Professional report (faculty workload + course assignments with rooms) |
| **CSV Export** | Machine-readable spreadsheet export |
| **Persistent Storage** | SQLite database with WAL mode for safe, fast reads |

---

## Screenshot

*(Add a screenshot of the running application here)*

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [AY 2025-2026 Sem 1 ▼] [+New] [Del]  [Import] [Suggest] [GCal] [View] [☀] │
├─────────────────────┬────────────────────────────────────────────────────┤
│ Add Faculty         │ Add Course                                         │
│ ┌─────────────────┐ │ ┌────────────────────────────────────────────────┐ │
│ │ Name: [_______] │ │ │ Faculty: [___________    ▼]                    │ │
│ │ Class: [____ ▼] │ │ │ Course:  [___________                        ]│ │
│ │ ☐ Admin         │ │ │ Year:    [______ ▼]    Units: [___ ▼]        │ │
│ │ [Add] [Delete..] │ │ │ Schedule:[________________ ▼]                │ │
│ └─────────────────┘ │ │ Room:    [___________                        ]│ │
│                     │ │ [Add] [Delete Selected]                       │ │
│                     │ └───────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────┤
│ [AY 2025-2026 Sem 1] Faculty: 5 | Courses: 24 | U:1 | ✓:3 | O:1 | GC: ✓│
├──────────────────────────────────────────────────────────────────────────┤
│ Faculty Workload — double-click to edit                                  │
│ Course Assignments — double-click to edit                                │
├──────────────────────────────────────────────────────────────────────────┤
│ [Workload PDF] [Schedule PDF] [Timetable PNG] [CSV]         [Clear All] │
└──────────────────────────────────────────────────────────────────────────┘
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

# 3. Install core dependencies
pip install PyQt5 reportlab

# 4. (Optional) For Google Calendar sync
pip install google-auth-oauthlib google-api-python-client google-auth-httplib2
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
- **+ New** — Create a new semester (e.g., "AY 2025-2026 Sem 2").
- **Del Semester** — Remove the current semester. Courses in it are unlinked (not deleted).

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
- **Double-click** any editable cell in the Faculty or Course table to edit it directly.
- Changes are validated and saved to the database immediately.
- Faculty editable fields: Name, Classification, Admin.
- Course editable fields: Course Name, Year Level, Units, Schedule, Room.

### Deleting Items
- **Faculty:** Select a row in the Faculty table, then click **Delete Selected** (or right-click).
- **Courses:** Select a row in the Course table, then click **Delete Selected** (or right-click).

### Bulk Import from CSV
Click **Import CSV…** and select a CSV file with this header:

```csv
Faculty Name,Classification,Is Admin,Course Name,Year Level,Units,Schedule,Room
Juan dela Cruz,Full-time PhD,Yes,Philo 101,BA 1,3,MW 07:40am-09:10am,F-203
```

A `sample_import.csv` is included as a template.

### Auto-Schedule Suggestions
1. Click **Suggest Schedule** in the top bar.
2. In the dialog, enter courses you want to assign (one per line):
   ```
   Course Name, Year Level, Units, Schedule, Room (optional)
   Philo 101, BA 1, 3, MW 07:40am-09:10am, F-203
   Math 102, BA 2, 3, TTh 09:20am-10:50am, M-105
   ```
3. The **greedy load-balanced algorithm** scores each course-to-faculty assignment based on:
   - Remaining capacity (prefer filling toward target load)
   - Schedule availability (no conflicts)
   - Faculty classification (full-time > part-time priority)
4. Review suggestions in the dialog — check/uncheck to accept/reject.
5. Click **Apply Selected** to commit the chosen assignments.

### Google Calendar Sync
1. **Prerequisites:** Install extra dependencies (`pip install google-auth-oauthlib google-api-python-client`).
2. **Set up Google Cloud:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project (or select existing)
   - Enable **Google Calendar API**
   - Create **OAuth 2.0 credentials** (Desktop app type)
   - Download the JSON file and save it as **`client_secret.json`** in the app directory
3. Click **Google Calendar** in the top bar.
   - **First click:** Initiates OAuth — your browser opens for consent. After authorizing, a token is cached locally (`gcal_token.json`).
   - **Subsequent clicks:** Syncs all course assignments to Google Calendar as recurring weekly events, with:
     - Event title: `{Course Name} — {Faculty Name}`
     - Location: Room
     - Description: Full course details
     - Recurrence: Weekly on the correct days (MW, TTh, or Sat)
     - Time zone: Asia/Manila
4. Events are tracked via a private extended property (`fls_id`) — re-syncing updates existing events rather than creating duplicates.

### Weekly Schedule View
Click **Weekly View** to open a visual timetable grid:
- Rows = daily time slots (07:40am–09:00pm)
- Columns = Monday through Saturday
- Shows all assigned courses with faculty name, course name, and room
- Use the dropdown to filter by a specific faculty member

### Export Options

| Button | Output | Description |
|---|---|---|
| **Workload PDF** | .PDF (landscape) | Faculty workload table + course assignments with rooms |
| **Schedule PDF** | .PDF (landscape) | Per-faculty weekly timetable grids |
| **Timetable PNG** | .PNG | Full-colour timetable image (all faculty combined) |
| **CSV** | .CSV | Machine-readable faculty + course data |

### Theme Toggle
Click **☀ Light** / **☾ Dark** in the top-right to switch between themes.

### Clearing All Data
Click **Clear All Data** (bottom-right). Two confirmations required, then resets to a fresh default semester.

---

## How It Works

### Architecture (~2,300 lines, single file)

```
main.py
  ├── Logging setup, constants, colour palettes
  ├── Data models: Semester, Course, Faculty (with __slots__)
  ├── Database: SQLite CRUD with WAL mode and semester scoping
  ├── SchedulingOptimizer: Greedy load-balanced assignment algorithm
  ├── ScheduleSuggestDialog: Review/accept/reject suggestions
  ├── Google Calendar: OAuth2 flow, event creation, RRULE generation
  ├── build_timetable_grid(): Shared timetable grid builder
  ├── FacultyWorkloadApp (QMainWindow):
  │     ├── Top bar: semester + Suggest + GCal + View + Theme
  │     ├── Input panels: Faculty + Course (with Room)
  │     ├── Tables: Faculty workload + Course assignments
  │     ├── Export bar: Workload PDF, Schedule PDF, Timetable PNG, CSV
  │     ├── Semester switching, in-place editing
  │     ├── Faculty/Course CRUD with conflict detection
  │     ├── Bulk CSV import with conflict-aware parsing
  │     ├── Auto-schedule with greedy optimizer dialog
  │     ├── Google Calendar sync (OAuth + event CRUD)
  │     ├── Schedule PDF (per-faculty timetable grids)
  │     ├── Timetable PNG (offscreen QTableWidget render)
  │     └── Dark/Light theme toggle
  └── Entry point
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
| faculty_id | INTEGER (FK → faculty) | Owning faculty member |
| semester_id | INTEGER (FK → semesters) | Owning semester (nullable) |
| name | TEXT | Course name |
| year_level | TEXT | e.g., BA 1, MA 2 |
| units | INTEGER | 3 or 6 |
| schedule | TEXT | Timeslot string |
| room | TEXT | Room/location (optional) |

### Auto-Scheduler Algorithm (`SchedulingOptimizer`)

The greedy algorithm works as follows:

1. **Sort** courses by priority (higher year levels first, then by units descending).
2. For each course, **score every eligible faculty member**:
   - If the course fits within remaining capacity: high score (50–100), proportional to fill ratio
   - If the course would cause overload but faculty has space: medium score (20–50)
   - Part-time faculty: base score of 5 (lowest priority)
   - Faculty with conflicts: excluded entirely
3. **Assign** to the highest-scoring faculty member.
4. **No backtracking** — once assigned, the assignment is final (greedy, not exhaustive).

### Google Calendar Integration

- Uses **OAuth 2.0** desktop flow (`InstalledAppFlow.run_local_server()`).
- Token is cached as `gcal_token.json` in the app directory.
- Each course becomes a **recurring weekly event** with an RRULE.
- Events are tagged with a private extended property (`fls_id=facultyID_courseID`) for idempotent re-syncing.
- Time zone: **Asia/Manila**.
- Only events for the **active semester** are synced.

---

## Version History

| Round | Features |
|---|---|
| **Original** | Basic add faculty/course, PDF/CSV export, dark theme |
| **Round 1** | Targeted DB saves, delete buttons, sorting, colour-coded status, admin checkbox, summary bar |
| **Round 2** | Semester management, in-place editing, bulk CSV import, weekly schedule view, room tracking, theme toggle |
| **Round 3 (current)** | **Schedule PDF** (per-faculty timetable), **Timetable PNG** export, **Auto-schedule suggestions** (greedy optimizer), **Google Calendar sync** (OAuth + recurring events) |

---

## Dependencies

| Package | Required for | Install |
|---|---|---|
| **PyQt5** | Core GUI framework | `pip install PyQt5` |
| **reportlab** | PDF generation | `pip install reportlab` |
| google-auth-oauthlib | Google Calendar OAuth2 | `pip install google-auth-oauthlib` |
| google-api-python-client | Google Calendar API | `pip install google-api-python-client` |
| google-auth-httplib2 | Google Auth transport | `pip install google-auth-httplib2` |

Packages in **bold** are required. Packages in normal weight are optional (for Google Calendar sync only).

---

## Sample CSV Import Template

```csv
Faculty Name,Classification,Is Admin,Course Name,Year Level,Units,Schedule,Room
Juan dela Cruz,Full-time PhD,Yes,Philo 101,BA 1,3,MW 07:40am-09:10am,F-203
Juan dela Cruz,Full-time PhD,Yes,Philo 102,BA 2,3,TTh 09:20am-10:50am,F-204
Maria Santos,Full-time MA,No,Math 101,BA 1,3,MW 09:20am-10:50am,M-105
Pedro Reyes,Part-time,No,Eng 101,BA 1,3,Sat 09:00am-12:00pm,E-301
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **"No module named PyQt5"** | Run `pip install PyQt5` (in your virtual environment) |
| **"No module named reportlab"** | Run `pip install reportlab` |
| **"Google Calendar libraries not installed"** | Run `pip install google-auth-oauthlib google-api-python-client` |
| **"client_secret.json not found"** | See [Google Calendar setup](#google-calendar-sync) above |
| **Cannot add faculty** | Check that the name field is non-empty and not a duplicate |
| **Cannot add course** | Ensure at least one faculty and semester exist |
| **Schedule conflict warning** | The timeslot or year-level/day combination already exists |
| **In-place edit rejected** | Check validation — classification must be on the allowed list, units must be 3 or 6 |
| **Import fails** | Ensure CSV uses UTF-8 and has the exact headers shown above |
| **Export fails** | Ensure write permissions for the target directory |
| **App won't start / crashes** | Check `~/faculty_app_debug.log` for stack traces |

---

## Contributing

Suggestions, bug reports, and pull requests are welcome via [GitHub Issues](https://github.com/uscabayaosj/faculty-loading-scheduling/issues).
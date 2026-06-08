# Faculty Workload and Scheduling Application

A **PyQt5** desktop application for managing faculty workloads, course assignments, and class schedules at the tertiary level. Built for academic department chairs, secretaries, and administrators who need a quick, offline way to track teaching loads, detect scheduling conflicts, and export reports.

> **Author:** Ulysses Cabayao, SJ — Ateneo de Davao University  
> **License:** Educational use

---

## Features

| Feature | Description |
|---|---|
| **Faculty Management** | Add, view, and delete faculty members with classification (Full-time PhD, Full-time MA, Part-time) and admin status |
| **Course Assignment** | Assign courses to faculty with year level, units, and schedule slot |
| **Workload Tracking** | Automatically calculates required vs. current load per faculty member |
| **Visual Load Status** | Colour-coded table cells — **green** (on target), **amber** (under), **red** (over) |
| **Schedule Conflict Detection** | Blocks conflicting assignments (same timeslot for same year level) |
| **Sortable Tables** | Click any column header to sort by that field |
| **Right-Click Context Menus** | Delete faculty or courses directly from the table |
| **Summary Bar** | Live counts: total faculty, courses, under/on-target/over breakdown |
| **Dark Theme** | Fusion dark palette for reduced eye strain |
| **PDF Export** | Professional two-table report (faculty workload + course assignments) |
| **CSV Export** | Machine-readable spreadsheet export |
| **Persistent Storage** | SQLite database with WAL mode for safe, fast reads |

---

## Screenshot

*(Add a screenshot of the running application here)*

```
┌─────────────────────────────────────────────────────────────┐
│  Faculty Workload & Scheduling                              │
├──────────────────────┬──────────────────────────────────────┤
│ Add / Edit Faculty   │ Add Course                           │
│ ┌──────────────────┐ │ ┌────────────────────────────────┐  │
│ │ Name: [________] │ │ │ Faculty: [___________    ▼]   │  │
│ │ Class: [_____ ▼] │ │ │ Course:  [___________        ]│  │
│ │ ☐ Admin          │ │ │ Year:    [______ ▼]           │  │
│ │ [Add] [Delete..]  │ │ │ Units:   [___ ▼]             │  │
│ └──────────────────┘ │ │ Schedule:[________________ ▼] │  │
│                      │ │ [Add] [Delete Selected]       │  │
│                      │ └────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│ Faculty: 5 | Courses: 24 | Under: 1 | On target: 3 | Over:1│
├─────────────────────────────────────────────────────────────┤
│ Faculty Workload (click headers to sort)                    │
│ ┌──────┬──────────┬────┬──────┬───┬──────────┐             │
│ │ Name │ Class    │Adm │ Req. │Curr│ Status   │             │
│ ├──────┼──────────┼────┼──────┼───┼──────────┤             │
│ │ ...  │ ...      │... │ ...  │... │ ██color██│             │
│ └──────┴──────────┴────┴──────┴───┴──────────┘             │
│ Course Assignments                                          │
│ ┌────┬──────┬────┬────┬──────────┐                          │
│ │Fac │Course│Year│Un.│ Schedule │                          │
│ └────┴──────┴────┴────┴──────────┘                          │
├─────────────────────────────────────────────────────────────┤
│ [Export to PDF] [Export to CSV]            [Clear All Data] │
└─────────────────────────────────────────────────────────────┘
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
5. Pick a **Schedule** slot from the preset list.
6. Click **Add Course**.

### Deleting Items
- **Faculty:** Select a row in the Faculty table, then click **Delete Selected** (or right-click).
- **Courses:** Select a row in the Course table, then click **Delete Selected** (or right-click).

### Viewing Load Status
The **Status** column in the Faculty table is colour-coded:
- 🟢 **Green** — Load is on target
- 🟡 **Amber** — Below required load
- 🔴 **Red** — Overload
- ⚫ **Grey** — Part-time (no required load)

### Exporting
- **PDF:** Produces a two-section report (faculty workloads + course assignments).
- **CSV:** Writes a structured CSV file readable by Excel, Google Sheets, etc.

### Clearing All Data
Click **Clear All Data** (bottom-right). This requires two confirmations, then permanently wipes the database.

---

## How It Works

### Architecture (single-file, ~530 lines)

```
main.py
  ├── setup_logging()           — File + stream logging
  ├── get_temp_dir()            — Temp directory (PyInstaller-aware)
  ├── Course class              — Data model: name, year, units, schedule
  ├── Faculty class             — Data model + load calculations
  ├── Database class            — SQLite CRUD (targeted INSERT/UPDATE/DELETE)
  └── FacultyWorkloadApp class  — PyQt5 GUI (QMainWindow)
        ├── UI construction
        ├── Table refresh helpers
        ├── Faculty add / delete
        ├── Course add / delete with conflict detection
        ├── PDF / CSV export
        └── Clear all / close events
```

### Data Flow

```
[User input] → [FacultyWorkloadApp] → [Database (SQLite)]
                     ↓
          [Table refresh + summary]
```

### Key Design Decisions

- **Targeted DB operations** — Each add/delete issues a single INSERT or DELETE instead of wiping and reloading all data. This is significantly faster than the previous approach.
- **Single JOIN query for loading** — Faculty and their courses are loaded together in one query instead of N+1 separate queries.
- **Sortable tables** — `setSortingEnabled(True)` on both tables; sorting is temporarily disabled during rebuilds to avoid visual flicker.
- **Right-click context menus** — Quick access to delete operations without hunting for buttons.
- **Colour-coded status** — Brushes applied to the Status column cells for instant visual parsing.
- **WAL journal mode** — Enables concurrent reads during writes without locking.
- **Class slots** — `__slots__` reduces memory overhead for Course and Faculty objects.

---

## Comparison: Before vs. After

| Aspect | Before | After |
|---|---|---|
| **DB save strategy** | Full DELETE + re-INSERT every change | Targeted INSERT / DELETE |
| **DB load strategy** | N+1 queries (1 per faculty + extra per faculty) | Single JOIN query |
| **Delete items** | ❌ Not possible | ✅ Per-item delete (button + right-click) |
| **Edit items** | ❌ Not possible | ✅ In development |
| **Table sorting** | ❌ Fixed order | ✅ Click-to-sort on any column |
| **Visual load status** | ❌ Plain text | ✅ Colour-coded cells |
| **Summary bar** | ❌ None | ✅ Live faculty/course/status counts |
| **Admin selector** | Dropdown (Not Admin / Admin) | Checkbox (clearer UX) |
| **Context menus** | ❌ None | ✅ Right-click delete on both tables |
| **Conflict details** | Vague warning | Shows conflicting course name |
| **Logging** | Raw file writes | Python `logging` module with levels |
| **PDF table style** | Duplicated code | Shared `_pdf_table_style()` helper |
| **PyInstaller awareness** | Manual temp logic | Cleaned up |
| **README accuracy** | Wrong filenames, fake OpenAI references | Accurate, reflects actual app |
| **Code size** | ~500 lines (monolithic) | ~530 lines (better organised) |

---

## Schema

### `faculty` table
| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK, AUTO) | Row ID |
| name | TEXT (UNIQUE) | Faculty member's name |
| classification | TEXT | Full-time PhD / Full-time MA / Part-time |
| is_admin | INTEGER (0/1) | Administrative role flag |

### `courses` table
| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK, AUTO) | Row ID |
| faculty_id | INTEGER (FK → faculty) | Owning faculty member |
| name | TEXT | Course name |
| year_level | TEXT | e.g. BA 1, MA 2 |
| units | INTEGER | 3 or 6 |
| schedule | TEXT | Timeslot string (e.g. "MW 09:20am-10:50am") |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **"No module named PyQt5"** | Run `pip install PyQt5` (in your virtual environment) |
| **"No module named reportlab"** | Run `pip install reportlab` |
| **Cannot add faculty** | Check that the name field is non-empty and not a duplicate |
| **Cannot add course** | Ensure at least one faculty exists, and the course name is non-empty |
| **Schedule conflict warning** | The timeslot or year-level/day combination already exists for that faculty |
| **Export fails** | Ensure you have write permissions for the target directory |
| **App won't start / crashes** | Check `~/faculty_app_debug.log` for stack traces |

---

## Contributing

This is an educational/admin tool. Suggestions, bug reports, and pull requests are welcome via [GitHub Issues](https://github.com/uscabayaosj/faculty-loading-scheduling/issues).

---

## Future Roadmap

- [ ] Edit faculty/course in place (double-click table cells)
- [ ] Bulk import from CSV
- [ ] Semester/term management
- [ ] Printable weekly schedule view per faculty
- [ ] Room/location tracking
- [ ] Dark/Light theme toggle
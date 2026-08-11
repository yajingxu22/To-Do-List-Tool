# 📋 To-Do List Tool

A lightweight, client-side to-do list tool that extracts readings, assignments, and exams from course syllabi (PDF format) and displays them in an editable, urgency-ranked dashboard.

Built for UCLA Anderson MBA students, but works with any syllabus that follows a standard course outline table format.

---

## Features

- **PDF Upload** — Drag-and-drop or click to upload syllabus PDFs
- **Smart Table Extraction** — Uses `pdfplumber` to accurately read course outline tables, mapping items from "Pre-Class Reading/Media" and "Assignments Due" columns
- **Multi-Page Table Support** — Handles outline tables that span multiple pages, with automatic date carryover for continuation rows
- **Exam Detection** — Scans all table columns for Final Exam, Midterm, Quiz, and Assessment entries
- **Urgency Ranking** — Items ranked by `weight × (1 / hours until due)`, with visual color coding:
  - 🔴 Overdue — red highlight, pinned to top
  - 🟠 Due today — orange accent
  - 🟡 Due tomorrow — yellow accent
  - 🔵 Due in 2–4 days — blue accent
  - ⚪ Due in 5+ days — neutral
- **Editable Dashboard** — Check off completed items, edit titles/dates/types, delete, or add custom items
- **📌 Pin & 🔥 Boost** — Manually prioritize items; boost stacks up to +3
- **Recurring Items** — Set daily, weekly, bi-weekly, or monthly recurrence with auto-numbered titles
- **Configurable Lookahead** — Default 7 days, adjustable from 1–30
- **Course & Type Filters** — Toggle visibility by course name or item type
- **Persistent Storage** — All data saved in browser `localStorage`; survives page refreshes
- **JSON Export/Import** — Backup and restore your to-do list
- **Multi-Course Support** — Upload multiple syllabi with different course names; filter by course on the dashboard

---

## Quick Start

### Prerequisites

- Python 3.8+ (tested with 3.11)
- `pdfplumber` and `flask` packages

### Setup

```bash
# Create a conda environment (recommended)
conda create -n todo python=3.11 -y
conda activate todo

# Install dependencies
pip install pdfplumber flask

# Run the app
python app.py
```

The browser opens automatically to `http://127.0.0.1:5050`. Upload a syllabus PDF and the extracted items appear in a review table for confirmation.

### Standalone Mode

You can also open `index.html` directly in a browser without running the server. In this mode, PDF parsing falls back to browser-based `pdf.js` (less accurate for tables). The status bar indicates which mode is active:

- 🟢 **Server connected** — accurate `pdfplumber` extraction
- 🟡 **Standalone mode** — browser-based fallback

---

## How It Works

### Parsing Pipeline

```
Upload PDF
    ↓
pdfplumber extracts all tables from every page
    ↓
Find the "Course Outline" table by matching header keywords
("Pre-Class Reading/Media" + "Assignments Due")
    ↓
Detect continuation tables on subsequent pages
(same column structure or matching header)
    ↓
For each row with a date:
  • Reading column content → 📖 Reading items
  • Assignment column content → 📄 Assignment items
  • Exam/Quiz/Final in any column → ❓ Quiz/Exam items
    ↓
Deduplicate (same type + same date + ≥50% word overlap)
    ↓
Return structured JSON → review table → dashboard
```

### Item Types & Urgency Weights

| Type | Weight | Icon |
|---|---|---|
| Quiz / Exam | 5.0 | ❓ |
| Assignment / Project | 3.5 | 📄 |
| Reading | 1.5 | 📖 |
| Other (user-defined) | 1.0–5.0 | 🔧 |

### Urgency Formula

```
urgencyScore = effectiveWeight × (1 / max(hoursUntilDue, 1))

where effectiveWeight = baseWeight + manualUrgencyBoost
```

---

## File Structure

```
To-Do-List-Tool/
├── app.py          ← Flask server + pdfplumber parsing engine
├── index.html      ← Complete web UI (single file, no build tools)
└── README.md       ← This file
```

---

## Tested Syllabi

| Syllabus | Items Extracted | Status |
|---|---|---|
| Tech Immersion (Summer 2026) | 16 | ✅ |
| Foundations of Inclusive Leadership (Summer 2026) | 10 | ✅ |
| Marketing Management (Summer 2026) | 37 | ✅ |

The parser is designed for Anderson-style syllabi with a "Course Outline" table containing Date, Pre-Class Reading/Media, and Assignments Due columns. Other syllabus formats may require manual item entry via the dashboard.

---

## Privacy

All data stays on your machine:

- **To-do items** are stored in your browser's `localStorage` — not on any server
- **Uploaded PDFs** are processed in memory and never saved to disk
- **No accounts, no cloud, no tracking**

Each user gets their own independent dashboard, even when sharing the same `app.py` and `index.html` files.

---

## GitHub Pages (Optional)

To host the standalone version (without server-side parsing):

1. Go to **Settings → Pages** in your repo
2. Source: **Deploy from a branch** → `main` / `/ (root)`
3. Your app will be live at `https://<username>.github.io/To-Do-List-Tool/`

Note: GitHub Pages serves `index.html` only (standalone mode). For accurate PDF table extraction, run `python app.py` locally.

---

## License

MIT

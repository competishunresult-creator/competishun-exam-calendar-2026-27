# Competishun — Engineering Entrance Exam Calendar 2026-27

Data source for https://competishun.com/engineering-entrance-exam-calendar/

The website reads `exams.csv` from this repository on every page visit.
Any change saved here shows on the website within a few minutes.

## Columns in exams.csv
| Column | What to write |
|---|---|
| registration / last_date / exam_dates | Text shown on the page. Use ` \| ` for a new line (e.g. `S1: Jan 20 \| S2: Apr 2`) |
| date_type | `Official`, `Partly Official` or `Expected` |
| s1_* / s2_* | Official dates only, format `YYYY-MM-DD`. Leave blank if not announced. These drive the automatic status, countdown and timeline |
| s1_label / s2_label | e.g. `Session 1`, `Phase 1`, `Attempt 1` (blank for single-session exams) |
| status_override | Leave blank. Fill only to force a status (e.g. `Postponed`) |
| verified_on | Date the row was last checked, `YYYY-MM-DD` |

## Rules for the daily update
1. Mark a date Official only if it is on the exam's official website, or confirmed by at least two reliable education news sites.
2. Never delete an exam row; only update it.
3. Never put commas inside a text field (use spaces, `;` or `|`).
4. If sources conflict, do not change the row — report it instead.
5. Log every change in `CHANGELOG.md`.

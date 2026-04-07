# Weekly Trends Section

## Goal

Add a "Weekly Trends" section to the terminal report that aggregates daily metrics into ISO weeks and shows week-over-week deltas, making it easy to spot behavioral changes at a glance.

## Design

### Placement

Between the Health Dashboard and Before/After sections in the report output.

### Aggregation

- Group daily data by ISO week number (Monday–Sunday)
- For each week, compute:
  - Total sessions
  - Total tool calls
  - Reads-before-edits average (weighted by count, not by day)
  - Write ratio % (total writes / total edits+writes)
  - Thinking redaction % (total redacted / total thinking blocks)

### Table Format

```
  WEEKLY TRENDS
  ──────────────────────────────────────────────────────────────────────
  Week          Sess  Tools  Rd/Ed          W%             Redct%
  ──────────────────────────────────────────────────────────────────────
  W11 Mar 10       3     75   0.6          14%             100%
  W12 Mar 17       6    300   0.5 ↓0.1     18% ↑4          100%   →
  W13 Mar 24       5    452   0.7 ↑0.2     15% ↓3          100%   →
  W14 Mar 31      23    544   0.3 ↓0.4     52% ↑37          98% ↓2
  W15 Apr 07       8    159   0.1 ↓0.2     55% ↑3          100% ↑2
```

### Delta Formatting

- Deltas shown as colored arrows: `↑`/`↓` + absolute change
- Color: green for improvement, red for degradation, dim `→` for no change
- "Improvement" direction per metric:
  - Reads-before-edits: higher is better (↑ green, ↓ red)
  - Write ratio: lower is better (↓ green, ↑ red)
  - Thinking redaction: informational only, no color (just dim arrows)
- Sessions and Tools: informational, no deltas
- First week: no delta (no previous week to compare)
- Threshold for "no change": abs(delta) < 0.05 for Rd/Ed, < 1 for percentages

### Week Label

Format: `W{iso_week} {Mon_date}` where Mon_date is the Monday of that ISO week, formatted as `Mon DD` (e.g., `Mar 10`).

## Implementation

### Changes

1. **`render_terminal.py`**: Add `format_weekly_trends(data) -> str` function. Call it in `render()` between `format_health_dashboard` and `format_before_after`.

2. **`test_analyze.py`**: Add tests for weekly aggregation logic and delta formatting.

3. **No changes to `analyze_sessions.py`** — weekly aggregation is a presentation concern computed from existing daily data.

## Out of Scope

- Configurable week boundaries
- Weekly data in JSON output
- Changes to the skill prompt (SKILL.md)

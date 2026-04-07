# Report Redesign: Rich Terminal Output

## Goal

Redesign the lazy-claude-analysis report output to be more visually telling — glanceable health verdicts, sparkline trends, color-coded thresholds — while splitting data collection from presentation for future extensibility.

## Architecture

Three files:

| File | Responsibility |
|------|---------------|
| `analyze_sessions.py` | Pure data collection. `analyze_all_sessions()` returns a dict. Main entry point calls renderer. No print statements except `Found N session files`. |
| `render_terminal.py` | All presentation logic. Takes data dict, produces ANSI-colored terminal output. |
| `test_analyze.py` | Existing data tests + new tests for renderer helpers (sparkline, thresholds, color). |

Invocation unchanged: `python3 analyze_sessions.py [cutoff_date]`

## Report Sections (in order)

### 1. Header

Box-drawn header with session count, date range, and cutoff context.

```
╔══════════════════════════════════════════════════════════════════╗
║  CLAUDE CODE BEHAVIORAL ANALYSIS                               ║
║  63 sessions · 19 active days · 2026-03-10 → 2026-04-07       ║
║  Cutoff: 2026-03-08 (thinking redaction deployment)            ║
╚══════════════════════════════════════════════════════════════════╝
```

### 2. Health Dashboard

Four key metrics, each on one line:
- Colored status dot (ANSI: green/yellow/red)
- Metric name and value
- Sparkline from daily data (Unicode block chars: ▁▂▃▄▅▆▇█)

```
  ● Thinking Redaction    96.7%          ▁▁▁▁▁▁▁▁▁▁▅▃▁▁
  ● Reads Before Edits    0.32 avg       ▁▃▃▅▂▂▇▅▂▂▁▄▃▁
  ● Write Ratio           27.8%          ▃▁▇▁▂▅▅▁▇▇▆▃▇
  ● Edit vs Write         325 / 125
```

#### Thresholds (hardcoded)

| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| Reads before edits | >= 1.0 | >= 0.5 | < 0.5 |
| Write ratio | <= 20% | <= 40% | > 40% |
| Thinking redaction | >= 90% | >= 50% | < 50% |
| Edit vs Write | informational only, no threshold |

### 3. Before/After Comparison

Side-by-side of pre/post cutoff periods with color-coded deltas.

When JSONL data is missing for the "before" period, show stats-cache aggregate data (sessions/day, messages/day) with a note about the different data source. Per-tool metrics (reads-before-edits, write ratio) are unavailable from stats-cache and should show "n/a (no JSONL data)". Deltas shown as colored arrows: green for improvement, red for degradation, gray for neutral/incomparable.

Metrics compared (when data available):
- Sessions per day
- Tool calls per day
- Thinking blocks per day (with/without content)
- Edits vs writes count and ratio
- Reads-before-edits average

### 4. Daily Timeline

Table with columns: Date, Sess, Tools, Think, Redact%, Reads/Ed, Edit, Write, W%

Enhancements over current:
- Sparkline summary row above the table for key metrics (Reads/Ed and W%)
- ANSI color on cells crossing thresholds (red for bad W%, red for low Reads/Ed)
- Cutoff date row gets a visual separator marker

### 5. Supplemental Stats

Same content as current section 7: total sessions from stats-cache, model usage, date range. Compact formatting, no changes.

## Rendering Details

### ANSI Colors

| Purpose | Code |
|---------|------|
| Green (healthy) | `\033[32m` |
| Yellow (warning) | `\033[33m` |
| Red (degraded) | `\033[31m` |
| Bold | `\033[1m` |
| Dim/gray | `\033[2m` |
| Reset | `\033[0m` |

Detect `NO_COLOR` env var and disable colors when set (standard convention).

### Sparklines

Map daily values to 8-level Unicode blocks: `▁▂▃▄▅▆▇█`

- Normalize to min/max of the series
- Days with no data (n/a) render as space
- Sparkline width = number of active days in the data

### Bar Charts

Not used (tool breakdown section removed).

## Data Pipeline Changes

`analyze_sessions.py` changes:
- Remove all `print()` calls from `print_report()` and the function itself
- Keep `print(f"Found {len(files)} session files")` in `analyze_all_sessions()` as progress indicator
- `main()` calls `analyze_all_sessions()` then passes result to `render_terminal.render(data)`
- Data dict shape stays the same — no changes to keys or structure

`render_terminal.py` exports:
- `render(data: dict) -> None` — prints the full report to stdout

Helper functions (all in `render_terminal.py`):
- `sparkline(values: list[float], width: int = None) -> str`
- `classify(value: float, thresholds: dict) -> str` — returns "green"/"yellow"/"red"
- `color(text: str, level: str) -> str` — wraps text in ANSI codes
- `format_header(data: dict) -> str`
- `format_health_dashboard(data: dict) -> str`
- `format_before_after(data: dict) -> str`
- `format_timeline(data: dict) -> str`
- `format_supplemental(data: dict) -> str`

## Testing

New tests added to `test_analyze.py`:
- `test_sparkline_basic` — known input produces expected block chars
- `test_sparkline_empty` — empty list returns empty string
- `test_sparkline_single_value` — single value produces one block
- `test_classify_thresholds` — each metric's green/yellow/red boundaries
- `test_color_no_color_env` — respects NO_COLOR env var
- `test_render_no_crash` — full render with sample data dict doesn't raise

Existing tests unchanged.

## Out of Scope

- HTML output (future, architecture supports it)
- Configurable thresholds file
- New behavioral metrics
- Tool breakdown / categorization section

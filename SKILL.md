---
name: lazy-claude-analysis
description: Use when the user asks to analyze Claude Code session data, check behavioral metrics, measure thinking redaction, reads-before-edits ratio, edit vs write frequency, or compare behavior before/after a date. Also use when user says "lazy claude", "session metrics", "analyze my sessions", "how is Claude behaving", "laziness metrics".
---

# Lazy Claude Analysis

Analyze Claude Code session JSONL logs to measure behavioral metrics like thinking redaction, reads-before-edits, and write-vs-edit ratios.

## When to Use

- User asks to analyze their Claude Code usage or session data
- User wants to check for behavioral regressions (laziness, shallow thinking)
- User wants before/after comparison around a specific date
- User says "session metrics", "analyze sessions", "check Claude behavior"

## How to Run

Run the analysis script located alongside this skill:

```bash
# Default cutoff (March 8, 2026 — thinking redaction deployment)
python3 ~/.claude/skills/lazy-claude-analysis/analyze_sessions.py

# Custom cutoff date
python3 ~/.claude/skills/lazy-claude-analysis/analyze_sessions.py 2026-04-01
```

Run tests:
```bash
cd ~/.claude/skills/lazy-claude-analysis && python3 test_analyze.py
```

## Metrics Produced

| Metric | What it measures |
|--------|-----------------|
| Total sessions/tools/thinking blocks | Raw volume from JSONL logs |
| Thinking redaction % | Thinking blocks with empty content (redacted by API) |
| Reads before edits | Avg Read calls preceding each Edit/Write (higher = more careful) |
| Write vs Edit ratio | % of file modifications that are full rewrites vs targeted edits |
| Daily timeline | Per-day breakdown of all metrics |
| Before/after comparison | Split metrics around the cutoff date |
| Supplemental stats | Aggregate data from stats-cache.json (older sessions) |

## Interpreting Results

- **Reads before edits dropping** suggests Claude is editing without reading first (less careful)
- **Write ratio increasing** suggests Claude is rewriting entire files instead of targeted edits
- **High thinking redaction %** confirms thinking content is stripped from API responses
- JSONL logs may not go back far enough for a full before/after comparison — stats-cache.json has older aggregate data but without per-tool-call detail

## Data Sources

- `~/.claude/projects/*/*.jsonl` — session conversation logs (detailed tool calls)
- `~/.claude/stats-cache.json` — aggregate daily stats (sessions, messages, tool calls, tokens)

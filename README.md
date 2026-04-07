# lazy-claude-analysis

Analyze your own Claude Code session logs for behavioral regressions — thinking redaction, reads-before-edits ratio, write-vs-edit frequency, and daily trends.

## Background

On April 6, 2026, [AMD's AI director Stella Laurenzo filed a GitHub issue](https://www.theregister.com/2026/04/06/anthropic_claude_code_dumber_lazier_amd_ai_director/) alleging that Claude Code had become "dumber and lazier" since early March. Her team analyzed 6,852 sessions (234,760 tool calls, 17,871 thinking blocks) and found:

- **Stop-hook violations** (ownership dodging, premature thinking cessation, permission-seeking) went from **0 to ~10/day** after March 8
- **Reads before edits** dropped from **6.6 to 2.0** on average — Claude stopped reading code before changing it
- **Full file rewrites** increased significantly — Claude began using `Write` instead of targeted `Edit` calls
- **Thinking blocks** became shallow, coinciding with the deployment of **thinking content redaction** in Claude Code v2.1.69

This tool lets you run the same analysis on your own session data to see if the trends hold.

## What It Measures

| Metric | What it tells you |
|--------|-------------------|
| Thinking redaction % | How many thinking blocks have empty (redacted) content |
| Reads before edits | Avg `Read` calls preceding each `Edit`/`Write` — higher means more careful |
| Write vs Edit ratio | % of file modifications that are full rewrites vs targeted edits |
| Daily timeline | Per-day breakdown of all metrics with trend visibility |
| Before/after split | Metrics split around a cutoff date (default: March 8, 2026) |
| Tool call breakdown | Which tools Claude uses most, with percentages |

## Installation as Claude Code Skill

Copy `SKILL.md` and `analyze_sessions.py` into your personal skills directory:

```bash
mkdir -p ~/.claude/skills/lazy-claude-analysis
cp SKILL.md analyze_sessions.py test_analyze.py ~/.claude/skills/lazy-claude-analysis/
```

Then in any Claude Code session, just say "lazy claude analysis" or "session metrics" and it will trigger automatically.

## Standalone Usage

```bash
# Default cutoff (March 8, 2026 — thinking redaction deployment)
python3 analyze_sessions.py

# Custom cutoff date
python3 analyze_sessions.py 2026-04-01
```

## Run Tests

```bash
python3 test_analyze.py
```

## Data Sources

The script reads from your local Claude Code data:

- `~/.claude/projects/*/*.jsonl` — session conversation logs with detailed tool calls, thinking blocks, and timestamps
- `~/.claude/stats-cache.json` — aggregate daily stats (sessions, messages, tool calls, tokens) covering older sessions

**Note:** Claude Code does not retain JSONL session logs indefinitely. Your detailed per-tool-call data may only go back a few weeks. The `stats-cache.json` has aggregate data going further back but without tool-level detail.

## Example Output

```
======================================================================
CLAUDE CODE SESSION ANALYSIS REPORT
  Cutoff date: 2026-03-08
======================================================================

1. OVERALL TOTALS
  Sessions analyzed (from JSONL):  61
  Total tool calls:                2976
  Thinking redacted (empty):       440 (96.7%)

3. EDIT vs WRITE
  Edit calls:  321
  Write calls: 120
  Write ratio: 27.2% full rewrites

4. READS BEFORE EDITS/WRITES
  After 2026-03-08: avg 0.32 reads before edit/write (n=441)

6. DAILY TIMELINE
  Date          Sess  Tools  Think  Redact Reads/Ed  Edit Write    W%
  2026-03-17       2     54      8       8      0.1     8     3    27
  2026-03-19       3    215     10      10      1.1    18     2    10
  ...
  2026-04-05       6    189     31      17      0.3     9    13    59
  2026-04-07       2     41     12      12      0.2     0     5   100
```

## Requirements

- Python 3.8+
- Claude Code session data in `~/.claude/`

## License

MIT

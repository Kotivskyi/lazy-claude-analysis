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
╔══════════════════════════════════════════════════════════════════╗
║  CLAUDE CODE BEHAVIORAL ANALYSIS                                 ║
║  67 sessions · 19 active days · 2026-03-10 → 2026-04-07          ║
║  Cutoff: 2026-03-08 (thinking redaction deployment)              ║
╚══════════════════════════════════════════════════════════════════╝

  HEALTH DASHBOARD
  ──────────────────────────────────────────────────────────
  ●  Thinking Redaction    96.9%                 ███████████████▁▇█
  ●  Reads Before Edits    0.31 avg            ▁▅▂▂█▂▃▁▁▁▃ ▂▄▂▁▁
  ●  Write Ratio           27.4%                  ▃▁▆▂▁▂▁▁▅▄▁ ██▆▃▄
  ●  Edit vs Write        339 / 128
  ──────────────────────────────────────────────────────────

  WEEKLY TRENDS
  ────────────────────────────────────────────────────────────────────────
  Reads/Edit = avg Read calls before each Edit/Write (higher = more careful)
  Week            Sess  Tools   Reads/Edit       Write%           Redact%
  ────────────────────────────────────────────────────────────────────────
  W11 Mar 09         1      0   —              —              —
  W12 Mar 16         8    321   0.7            21%            100%
  W13 Mar 23         9   1458   0.3 ↓0.4       16% ↓5%        100% →
  W14 Mar 30        35   1050   0.3 →          52% ↑36%       91% ↓9%
  W15 Apr 06        14    297   0.2 ↓0.1       36% ↓16%       98% ↑7%
  ────────────────────────────────────────────────────────────────────────

  DAILY TIMELINE
  ────────────────────────────────────────────────────────────────────────────────
  Reads/Edit    ▁▅▂▂█▂▃▁▁▁▃ ▂▄▂▁▁
  Write %       ▃▁▆▂▁▂▁▁▅▄▁ ██▆▃▄
  ────────────────────────────────────────────────────────────────────────────────
  Date          Sess  Tools  Think Redct%  Rd/Ed  Edit Write    W%
  ────────────────────────────────────────────────────────────────────────────────
  2026-03-17       2     54      8    100    0.1     8     3    27
  2026-03-19       3    215     10    100    1.1    18     2    10
  ...
  2026-04-06       6    106     19     95    0.3    14     5    26
  2026-04-07       8    191     34    100    0.1    18    13    42
```

## Requirements

- Python 3.8+
- Claude Code session data in `~/.claude/`

## License

MIT

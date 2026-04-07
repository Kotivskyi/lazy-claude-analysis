#!/usr/bin/env python3
"""
Analyze Claude Code session data to compute behavioral metrics.

Metrics computed:
1. Total sessions, messages, tool calls, thinking blocks
2. Tool call breakdown by type
3. Reads-before-edits ratio (avg reads preceding an edit/write)
4. Write vs Edit ratio (full rewrites vs targeted edits)
5. Daily trends
6. Before/after comparison around a configurable cutoff date
"""

import json
import os
import sys
import subprocess
from collections import defaultdict, Counter
from datetime import datetime, date
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
STATS_CACHE = CLAUDE_DIR / "stats-cache.json"

# Default cutoff: thinking redaction deployment (Claude Code 2.1.69)
DEFAULT_CUTOFF = date(2026, 3, 8)


def find_session_files():
    """Find all main session JSONL files (not subagent files)."""
    result = subprocess.run(
        ["find", str(PROJECTS_DIR), "-maxdepth", "2", "-name", "*.jsonl", "-type", "f"],
        capture_output=True, text=True
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def parse_session(filepath):
    """Parse a single session JSONL file into structured records."""
    records = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def extract_session_date(records):
    """Extract session date from the first timestamped record."""
    for r in records:
        ts = r.get("timestamp")
        if ts:
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
                except ValueError:
                    pass
            elif isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts / 1000).date()
    return None


def extract_tool_sequence(records):
    """Extract ordered sequence of tool calls from a session."""
    tools = []
    for r in records:
        if r.get("type") != "assistant":
            continue
        msg = r.get("message", {})
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tools.append(block.get("name", "unknown"))
    return tools


def extract_thinking_blocks(records):
    """Count thinking blocks and their content status."""
    total = 0
    with_content = 0
    for r in records:
        if r.get("type") != "assistant":
            continue
        msg = r.get("message", {})
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "thinking":
                total += 1
                if block.get("thinking", "").strip():
                    with_content += 1
    return total, with_content


def compute_reads_before_edits(tool_sequence):
    """
    For each Edit or Write in the sequence, count how many consecutive
    Read calls preceded it (looking backward, stopping at non-Read tools).
    Returns list of read counts.
    """
    read_counts = []
    for i, tool in enumerate(tool_sequence):
        if tool in ("Edit", "Write"):
            count = 0
            for j in range(i - 1, -1, -1):
                if tool_sequence[j] == "Read":
                    count += 1
                elif tool_sequence[j] in ("Edit", "Write", "Bash", "Grep", "Glob", "Agent"):
                    break
            read_counts.append(count)
    return read_counts


def extract_version(records):
    """Extract Claude Code version from session records."""
    for r in records:
        v = r.get("version")
        if v:
            return v
    return None


def analyze_all_sessions(cutoff_date=None):
    """Main analysis across all sessions."""
    cutoff = cutoff_date or DEFAULT_CUTOFF
    files = find_session_files()
    print(f"Found {len(files)} session files\n")

    daily = defaultdict(lambda: {
        "sessions": 0,
        "messages": 0,
        "tool_calls": 0,
        "thinking_blocks": 0,
        "thinking_with_content": 0,
        "tool_counts": Counter(),
        "reads_before_edits": [],
        "edits": 0,
        "writes": 0,
    })

    total_sessions = 0
    total_tool_calls = 0
    total_thinking = 0
    total_thinking_with_content = 0
    all_tool_counts = Counter()
    reads_before_edits_pre = []
    reads_before_edits_post = []
    versions_seen = set()

    for filepath in files:
        records = parse_session(filepath)
        if not records:
            continue

        session_date = extract_session_date(records)
        if not session_date:
            continue

        total_sessions += 1
        day_key = session_date.isoformat()
        daily[day_key]["sessions"] += 1

        msg_count = sum(1 for r in records if r.get("type") in ("user", "assistant"))
        daily[day_key]["messages"] += msg_count

        tools = extract_tool_sequence(records)
        daily[day_key]["tool_calls"] += len(tools)
        total_tool_calls += len(tools)

        for t in tools:
            daily[day_key]["tool_counts"][t] += 1
            all_tool_counts[t] += 1

        daily[day_key]["edits"] += tools.count("Edit")
        daily[day_key]["writes"] += tools.count("Write")

        thinking, thinking_content = extract_thinking_blocks(records)
        daily[day_key]["thinking_blocks"] += thinking
        daily[day_key]["thinking_with_content"] += thinking_content
        total_thinking += thinking
        total_thinking_with_content += thinking_content

        rbe = compute_reads_before_edits(tools)
        daily[day_key]["reads_before_edits"].extend(rbe)
        if session_date < cutoff:
            reads_before_edits_pre.extend(rbe)
        else:
            reads_before_edits_post.extend(rbe)

        v = extract_version(records)
        if v:
            versions_seen.add(v)

    return {
        "cutoff_date": cutoff,
        "total_sessions": total_sessions,
        "total_tool_calls": total_tool_calls,
        "total_thinking_blocks": total_thinking,
        "total_thinking_with_content": total_thinking_with_content,
        "all_tool_counts": all_tool_counts,
        "daily": daily,
        "reads_before_edits_pre": reads_before_edits_pre,
        "reads_before_edits_post": reads_before_edits_post,
        "versions_seen": versions_seen,
    }


def print_report(data):
    """Print formatted analysis report."""
    cutoff = data["cutoff_date"]

    print("=" * 70)
    print("CLAUDE CODE SESSION ANALYSIS REPORT")
    print(f"  Cutoff date: {cutoff}")
    print("=" * 70)

    # 1. Totals
    print(f"\n{'─' * 40}")
    print("1. OVERALL TOTALS")
    print(f"{'─' * 40}")
    print(f"  Sessions analyzed (from JSONL):  {data['total_sessions']}")
    print(f"  Total tool calls:                {data['total_tool_calls']}")
    print(f"  Total thinking blocks:           {data['total_thinking_blocks']}")
    print(f"  Thinking with content:           {data['total_thinking_with_content']}")
    print(f"  Thinking redacted (empty):       {data['total_thinking_blocks'] - data['total_thinking_with_content']}")
    print(f"  Versions seen:                   {sorted(data['versions_seen'])}")

    # 2. Tool breakdown
    print(f"\n{'─' * 40}")
    print("2. TOOL CALL BREAKDOWN")
    print(f"{'─' * 40}")
    for tool, count in data["all_tool_counts"].most_common(25):
        pct = count / data["total_tool_calls"] * 100 if data["total_tool_calls"] else 0
        print(f"  {tool:45s} {count:>6}  ({pct:4.1f}%)")

    # 3. Edit vs Write
    total_edits = data["all_tool_counts"].get("Edit", 0)
    total_writes = data["all_tool_counts"].get("Write", 0)
    print(f"\n{'─' * 40}")
    print("3. EDIT vs WRITE (targeted edits vs full file rewrites)")
    print(f"{'─' * 40}")
    print(f"  Edit calls:  {total_edits}")
    print(f"  Write calls: {total_writes}")
    if total_edits + total_writes > 0:
        print(f"  Write ratio: {total_writes / (total_edits + total_writes) * 100:.1f}% full rewrites")

    # 4. Reads before edits
    print(f"\n{'─' * 40}")
    print(f"4. READS BEFORE EDITS/WRITES (cutoff: {cutoff})")
    print(f"{'─' * 40}")
    pre = data["reads_before_edits_pre"]
    post = data["reads_before_edits_post"]
    if pre:
        print(f"  Before {cutoff}: avg {sum(pre)/len(pre):.2f} reads before edit/write (n={len(pre)})")
    else:
        print(f"  Before {cutoff}: no data")
    if post:
        print(f"  After  {cutoff}: avg {sum(post)/len(post):.2f} reads before edit/write (n={len(post)})")
    else:
        print(f"  After  {cutoff}: no data")

    # 5. Before/after comparison
    print(f"\n{'─' * 40}")
    print(f"5. BEFORE vs AFTER {cutoff}")
    print(f"{'─' * 40}")
    pre_days = {k: v for k, v in data["daily"].items() if date.fromisoformat(k) < cutoff}
    post_days = {k: v for k, v in data["daily"].items() if date.fromisoformat(k) >= cutoff}

    def summarize_period(days, label):
        if not days:
            print(f"  {label}: no session data")
            return
        n_days = len(days)
        n_sessions = sum(d["sessions"] for d in days.values())
        n_tools = sum(d["tool_calls"] for d in days.values())
        n_thinking = sum(d["thinking_blocks"] for d in days.values())
        n_thinking_content = sum(d["thinking_with_content"] for d in days.values())
        n_edits = sum(d["edits"] for d in days.values())
        n_writes = sum(d["writes"] for d in days.values())

        print(f"  {label}:")
        print(f"    Active days:        {n_days}")
        print(f"    Sessions:           {n_sessions} ({n_sessions/n_days:.1f}/day)")
        print(f"    Tool calls:         {n_tools} ({n_tools/n_days:.1f}/day)")
        print(f"    Thinking blocks:    {n_thinking} ({n_thinking/n_days:.1f}/day)")
        print(f"    - with content:     {n_thinking_content}")
        print(f"    - redacted (empty): {n_thinking - n_thinking_content}")
        print(f"    Edits:              {n_edits}")
        print(f"    Writes:             {n_writes}")
        if n_edits + n_writes > 0:
            print(f"    Write ratio:        {n_writes/(n_edits+n_writes)*100:.1f}%")

    summarize_period(pre_days, f"BEFORE {cutoff}")
    summarize_period(post_days, f"AFTER  {cutoff}")

    # 6. Daily timeline
    print(f"\n{'─' * 40}")
    print("6. DAILY TIMELINE")
    print(f"{'─' * 40}")
    print(f"  {'Date':12s} {'Sess':>5s} {'Tools':>6s} {'Think':>6s} {'Redact':>7s} {'Reads/Ed':>8s} {'Edit':>5s} {'Write':>5s} {'W%':>5s}")
    for day_key in sorted(data["daily"].keys()):
        d = data["daily"][day_key]
        rbe = d["reads_before_edits"]
        rbe_avg = f"{sum(rbe)/len(rbe):.1f}" if rbe else "n/a"
        edits = d["edits"]
        writes = d["writes"]
        w_pct = f"{writes/(edits+writes)*100:.0f}" if edits + writes > 0 else "n/a"
        marker = " <<" if date.fromisoformat(day_key) == cutoff else ""
        print(f"  {day_key:12s} {d['sessions']:5d} {d['tool_calls']:6d} {d['thinking_blocks']:6d} "
              f"{d['thinking_blocks']-d['thinking_with_content']:7d} {rbe_avg:>8s} {edits:5d} {writes:5d} {w_pct:>5s}{marker}")

    # 7. Supplemental stats
    if STATS_CACHE.exists():
        print(f"\n{'─' * 40}")
        print("7. SUPPLEMENTAL (stats-cache.json)")
        print(f"{'─' * 40}")
        with open(STATS_CACHE) as f:
            stats = json.load(f)
        print(f"  Total sessions (all time): {stats.get('totalSessions', 'N/A')}")
        print(f"  Total messages (all time): {stats.get('totalMessages', 'N/A')}")
        print(f"  First session:             {stats.get('firstSessionDate', 'N/A')}")
        print(f"  Stats cached through:      {stats.get('lastComputedDate', 'N/A')}")
        model_usage = stats.get("modelUsage", {})
        print(f"\n  Model usage:")
        for model, usage in model_usage.items():
            print(f"    {model}:")
            print(f"      Output tokens:         {usage.get('outputTokens', 0):>12,}")
            print(f"      Cache read tokens:     {usage.get('cacheReadInputTokens', 0):>12,}")


def main():
    cutoff = DEFAULT_CUTOFF
    if len(sys.argv) > 1:
        try:
            cutoff = date.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"Invalid date: {sys.argv[1]} (use YYYY-MM-DD format)")
            sys.exit(1)

    data = analyze_all_sessions(cutoff)
    print_report(data)


if __name__ == "__main__":
    main()

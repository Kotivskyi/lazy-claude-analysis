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


def load_stats_cache():
    """Load supplemental stats from stats-cache.json if available."""
    if STATS_CACHE.exists():
        with open(STATS_CACHE) as f:
            return json.load(f)
    return None


def main():
    cutoff = DEFAULT_CUTOFF
    if len(sys.argv) > 1:
        try:
            cutoff = date.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"Invalid date: {sys.argv[1]} (use YYYY-MM-DD format)")
            sys.exit(1)

    data = analyze_all_sessions(cutoff)
    data["stats_cache"] = load_stats_cache()

    from render_terminal import render
    render(data)


if __name__ == "__main__":
    main()

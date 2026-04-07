#!/usr/bin/env python3
"""Tests for session analysis functions."""

import json
import os
import tempfile
from datetime import date

# Import from same directory
import sys
sys.path.insert(0, os.path.dirname(__file__))
import analyze_sessions as a


def make_assistant_record(content_blocks, timestamp="2026-03-01T10:00:00Z", version="2.1.85"):
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": content_blocks},
        "timestamp": timestamp,
        "version": version,
    }


def make_tool_use(name):
    return {"type": "tool_use", "name": name, "id": "toolu_123"}


def make_thinking(content=""):
    return {"type": "thinking", "thinking": content, "signature": "sig"}


def make_user_record(text="do something", timestamp="2026-03-01T09:59:00Z"):
    return {"type": "user", "message": {"role": "user", "content": text}, "timestamp": timestamp}


# --- Tests ---

def test_extract_session_date_iso():
    assert a.extract_session_date([{"timestamp": "2026-03-15T10:00:00Z"}]) == date(2026, 3, 15)

def test_extract_session_date_epoch_ms():
    result = a.extract_session_date([{"timestamp": 1768694400000}])
    assert result is not None and result.year == 2026

def test_extract_session_date_no_timestamp():
    assert a.extract_session_date([{"type": "system"}]) is None

def test_extract_tool_sequence():
    records = [
        make_assistant_record([make_tool_use("Read")]),
        make_assistant_record([make_tool_use("Read"), make_tool_use("Edit")]),
        make_assistant_record([make_tool_use("Bash")]),
    ]
    assert a.extract_tool_sequence(records) == ["Read", "Read", "Edit", "Bash"]

def test_extract_tool_sequence_ignores_non_assistant():
    records = [make_user_record(), make_assistant_record([make_tool_use("Read")])]
    assert a.extract_tool_sequence(records) == ["Read"]

def test_extract_thinking_blocks():
    records = [
        make_assistant_record([make_thinking("thought"), make_tool_use("Read")]),
        make_assistant_record([make_thinking(""), make_thinking("another")]),
    ]
    total, with_content = a.extract_thinking_blocks(records)
    assert total == 3 and with_content == 2

def test_extract_thinking_blocks_all_redacted():
    records = [make_assistant_record([make_thinking("")]), make_assistant_record([make_thinking("")])]
    total, with_content = a.extract_thinking_blocks(records)
    assert total == 2 and with_content == 0

def test_reads_before_edits_simple():
    assert a.compute_reads_before_edits(["Read", "Read", "Edit"]) == [2]

def test_reads_before_edits_multiple():
    assert a.compute_reads_before_edits(["Read", "Edit", "Read", "Read", "Read", "Write"]) == [1, 3]

def test_reads_before_edits_no_reads():
    assert a.compute_reads_before_edits(["Bash", "Edit", "Grep", "Write"]) == [0, 0]

def test_reads_before_edits_interrupted():
    assert a.compute_reads_before_edits(["Read", "Bash", "Read", "Edit"]) == [1]

def test_reads_before_edits_empty():
    assert a.compute_reads_before_edits([]) == []
    assert a.compute_reads_before_edits(["Read", "Read"]) == []

def test_extract_version():
    assert a.extract_version([{"type": "system", "version": "2.1.85"}]) == "2.1.85"
    assert a.extract_version([{"type": "assistant", "message": {}}]) is None

def test_parse_session_roundtrip():
    records = [make_user_record(), make_assistant_record([make_tool_use("Read")])]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
        path = f.name
    try:
        parsed = a.parse_session(path)
        assert len(parsed) == 2
    finally:
        os.unlink(path)

def test_parse_session_skips_malformed():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(make_user_record()) + "\n")
        f.write("not json\n")
        f.write(json.dumps(make_assistant_record([make_tool_use("Read")])) + "\n")
        path = f.name
    try:
        assert len(a.parse_session(path)) == 2
    finally:
        os.unlink(path)


# --- Renderer tests ---

import render_terminal as rt


def test_sparkline_basic():
    result = rt.sparkline([0, 0.5, 1.0])
    assert len(result) == 3
    assert result[0] == "▁"
    assert result[2] == "█"


def test_sparkline_empty():
    assert rt.sparkline([]) == ""


def test_sparkline_single_value():
    result = rt.sparkline([5.0])
    assert len(result) == 1


def test_sparkline_with_none():
    result = rt.sparkline([1.0, None, 3.0])
    assert len(result) == 3
    assert result[1] == " "


def test_classify_reads_before_edits():
    assert rt.classify("reads_before_edits", 1.5) == "green"
    assert rt.classify("reads_before_edits", 0.7) == "yellow"
    assert rt.classify("reads_before_edits", 0.3) == "red"


def test_classify_write_ratio():
    assert rt.classify("write_ratio", 15.0) == "green"
    assert rt.classify("write_ratio", 30.0) == "yellow"
    assert rt.classify("write_ratio", 50.0) == "red"


def test_classify_thinking_redaction():
    assert rt.classify("thinking_redaction", 95.0) == "green"
    assert rt.classify("thinking_redaction", 60.0) == "yellow"
    assert rt.classify("thinking_redaction", 40.0) == "red"


def test_classify_unknown_metric():
    assert rt.classify("unknown_thing", 42) == "dim"


def test_color_no_color_env():
    original = rt.NO_COLOR
    try:
        rt.NO_COLOR = True
        assert rt.color("hello", "red") == "hello"
        assert rt.color("hello", "green") == "hello"
    finally:
        rt.NO_COLOR = original


def test_render_no_crash():
    """Full render with sample data dict should not raise."""
    from collections import Counter
    from datetime import date
    sample_data = {
        "cutoff_date": date(2026, 3, 8),
        "total_sessions": 5,
        "total_tool_calls": 50,
        "total_thinking_blocks": 10,
        "total_thinking_with_content": 2,
        "all_tool_counts": Counter({"Bash": 20, "Read": 15, "Edit": 10, "Write": 5}),
        "daily": {
            "2026-03-10": {
                "sessions": 2, "messages": 10, "tool_calls": 25,
                "thinking_blocks": 5, "thinking_with_content": 1,
                "tool_counts": Counter({"Bash": 10, "Read": 8, "Edit": 5, "Write": 2}),
                "reads_before_edits": [1, 0, 2], "edits": 5, "writes": 2,
            },
            "2026-03-12": {
                "sessions": 3, "messages": 20, "tool_calls": 25,
                "thinking_blocks": 5, "thinking_with_content": 1,
                "tool_counts": Counter({"Bash": 10, "Read": 7, "Edit": 5, "Write": 3}),
                "reads_before_edits": [0, 1], "edits": 5, "writes": 3,
            },
        },
        "reads_before_edits_pre": [],
        "reads_before_edits_post": [1, 0, 2, 0, 1],
        "versions_seen": {"2.1.85"},
        "stats_cache": None,
    }
    # Should not raise
    rt.render(sample_data)


def test_weekly_trends_multi_week():
    """Weekly trends correctly aggregates across weeks and shows deltas."""
    from collections import Counter
    sample_data = {
        "cutoff_date": date(2026, 3, 8),
        "total_sessions": 10,
        "total_tool_calls": 100,
        "total_thinking_blocks": 20,
        "total_thinking_with_content": 2,
        "all_tool_counts": Counter({"Read": 30, "Edit": 15, "Write": 5}),
        "daily": {
            # Week 11 (Mon Mar 9)
            "2026-03-10": {
                "sessions": 2, "messages": 10, "tool_calls": 30,
                "thinking_blocks": 5, "thinking_with_content": 0,
                "tool_counts": Counter({"Read": 10, "Edit": 5, "Write": 1}),
                "reads_before_edits": [2, 1, 1], "edits": 5, "writes": 1,
            },
            # Week 12 (Mon Mar 16)
            "2026-03-17": {
                "sessions": 3, "messages": 15, "tool_calls": 40,
                "thinking_blocks": 8, "thinking_with_content": 1,
                "tool_counts": Counter({"Read": 12, "Edit": 6, "Write": 3}),
                "reads_before_edits": [0, 0, 1], "edits": 6, "writes": 3,
            },
            "2026-03-19": {
                "sessions": 2, "messages": 8, "tool_calls": 20,
                "thinking_blocks": 4, "thinking_with_content": 1,
                "tool_counts": Counter({"Read": 5, "Edit": 3, "Write": 1}),
                "reads_before_edits": [1, 0], "edits": 3, "writes": 1,
            },
        },
        "reads_before_edits_pre": [],
        "reads_before_edits_post": [2, 1, 1, 0, 0, 1, 1, 0],
        "versions_seen": {"2.1.85"},
        "stats_cache": None,
    }
    # Disable colors for easy assertion
    original = rt.NO_COLOR
    rt.NO_COLOR = True
    try:
        result = rt.format_weekly_trends(sample_data)
        assert "WEEKLY TRENDS" in result
        # Week 11 should have no delta (first week)
        assert "W11" in result
        # Week 12 should have deltas
        assert "W12" in result
        # Reads-before-edits: W11=1.3, W12=0.4 -> ↓ (red, but NO_COLOR)
        assert "↓" in result
        # Write ratio: W11=17%, W12=31% -> ↑ (worse)
        assert "↑" in result
    finally:
        rt.NO_COLOR = original


def test_weekly_trends_empty():
    """Weekly trends with no daily data returns empty string."""
    from collections import Counter
    sample_data = {
        "cutoff_date": date(2026, 3, 8),
        "total_sessions": 0,
        "total_tool_calls": 0,
        "total_thinking_blocks": 0,
        "total_thinking_with_content": 0,
        "all_tool_counts": Counter(),
        "daily": {},
        "reads_before_edits_pre": [],
        "reads_before_edits_post": [],
        "versions_seen": set(),
        "stats_cache": None,
    }
    assert rt.format_weekly_trends(sample_data) == ""


def test_weekly_trends_single_week():
    """Single week should render with no deltas."""
    from collections import Counter
    sample_data = {
        "cutoff_date": date(2026, 3, 8),
        "total_sessions": 2,
        "total_tool_calls": 30,
        "total_thinking_blocks": 5,
        "total_thinking_with_content": 0,
        "all_tool_counts": Counter({"Read": 10, "Edit": 5, "Write": 1}),
        "daily": {
            "2026-03-10": {
                "sessions": 2, "messages": 10, "tool_calls": 30,
                "thinking_blocks": 5, "thinking_with_content": 0,
                "tool_counts": Counter({"Read": 10, "Edit": 5, "Write": 1}),
                "reads_before_edits": [2, 1], "edits": 5, "writes": 1,
            },
        },
        "reads_before_edits_pre": [],
        "reads_before_edits_post": [2, 1],
        "versions_seen": {"2.1.85"},
        "stats_cache": None,
    }
    original = rt.NO_COLOR
    rt.NO_COLOR = True
    try:
        result = rt.format_weekly_trends(sample_data)
        assert "W11" in result
        # No deltas for single week
        assert "↑" not in result
        assert "↓" not in result
        assert "→" not in result
    finally:
        rt.NO_COLOR = original


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    exit(1 if failed else 0)

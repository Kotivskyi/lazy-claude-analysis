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

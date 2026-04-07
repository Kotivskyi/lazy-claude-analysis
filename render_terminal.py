#!/usr/bin/env python3
"""Rich terminal renderer for Claude Code session analysis."""

import os
from datetime import date, timedelta

# ── ANSI helpers ──────────────────────────────────────────────────

NO_COLOR = os.environ.get("NO_COLOR") is not None

COLORS = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}


def color(text, level):
    """Wrap text in ANSI color codes. Respects NO_COLOR."""
    if NO_COLOR or level not in COLORS:
        return str(text)
    return f"{COLORS[level]}{text}{COLORS['reset']}"


def bold(text):
    return color(text, "bold")


def dim(text):
    return color(text, "dim")


# ── Sparklines ────────────────────────────────────────────────────

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values):
    """Generate a sparkline string from a list of numeric values.

    None values render as a space (missing data).
    """
    nums = [v for v in values if v is not None]
    if not nums:
        return ""
    lo, hi = min(nums), max(nums)
    span = hi - lo if hi != lo else 1
    result = []
    for v in values:
        if v is None:
            result.append(" ")
        else:
            idx = int((v - lo) / span * (len(SPARK_CHARS) - 1))
            result.append(SPARK_CHARS[idx])
    return "".join(result)


# ── Thresholds ────────────────────────────────────────────────────

THRESHOLDS = {
    "reads_before_edits": {"green": 1.0, "yellow": 0.5},   # >= green, >= yellow, else red
    "write_ratio":        {"green": 20.0, "yellow": 40.0},  # <= green, <= yellow, else red
    "thinking_redaction": {"green": 90.0, "yellow": 50.0},  # >= green, >= yellow, else red
}


def classify(metric, value):
    """Classify a metric value as green/yellow/red."""
    t = THRESHOLDS.get(metric)
    if not t:
        return "dim"
    if metric == "write_ratio":
        # Lower is better
        if value <= t["green"]:
            return "green"
        elif value <= t["yellow"]:
            return "yellow"
        else:
            return "red"
    else:
        # Higher is better
        if value >= t["green"]:
            return "green"
        elif value >= t["yellow"]:
            return "yellow"
        else:
            return "red"


def status_dot(level):
    """Colored status dot."""
    return color("●", level)


# ── Section renderers ─────────────────────────────────────────────

def format_header(data):
    daily = data["daily"]
    days_sorted = sorted(daily.keys())
    first_day = days_sorted[0] if days_sorted else "?"
    last_day = days_sorted[-1] if days_sorted else "?"
    n_days = len(days_sorted)
    n_sessions = data["total_sessions"]
    cutoff = data["cutoff_date"]

    w = 66
    title = "CLAUDE CODE BEHAVIORAL ANALYSIS"
    summary = f"{n_sessions} sessions · {n_days} active days · {first_day} → {last_day}"
    cutoff_line = f"Cutoff: {cutoff} (thinking redaction deployment)"

    lines = []
    lines.append(f"╔{'═' * w}╗")
    lines.append(f"║  {bold(title)}{' ' * (w - 2 - len(title))}║")
    lines.append(f"║  {summary:<{w - 2}}║")
    lines.append(f"║  {cutoff_line:<{w - 2}}║")
    lines.append(f"╚{'═' * w}╝")
    return "\n".join(lines)


def format_health_dashboard(data):
    daily = data["daily"]
    days_sorted = sorted(daily.keys())

    total_edits = data["all_tool_counts"].get("Edit", 0)
    total_writes = data["all_tool_counts"].get("Write", 0)
    total_mods = total_edits + total_writes

    # Compute metric values
    thinking_total = data["total_thinking_blocks"]
    thinking_redacted = thinking_total - data["total_thinking_with_content"]
    redaction_pct = (thinking_redacted / thinking_total * 100) if thinking_total > 0 else 0

    post = data["reads_before_edits_post"]
    pre = data["reads_before_edits_pre"]
    all_rbe = pre + post
    rbe_avg = sum(all_rbe) / len(all_rbe) if all_rbe else 0

    write_ratio = (total_writes / total_mods * 100) if total_mods > 0 else 0

    # Daily sparkline data
    rbe_daily = []
    wr_daily = []
    redact_daily = []
    for dk in days_sorted:
        d = daily[dk]
        rbe_vals = d["reads_before_edits"]
        rbe_daily.append(sum(rbe_vals) / len(rbe_vals) if rbe_vals else None)
        e, w = d["edits"], d["writes"]
        wr_daily.append(w / (e + w) * 100 if e + w > 0 else None)
        tb = d["thinking_blocks"]
        tc = d["thinking_with_content"]
        redact_daily.append((tb - tc) / tb * 100 if tb > 0 else None)

    lines = []
    lines.append(f"\n  {bold('HEALTH DASHBOARD')}")
    lines.append(f"  {'─' * 58}")

    # Thinking redaction
    lvl = classify("thinking_redaction", redaction_pct)
    lines.append(f"  {status_dot(lvl)}  Thinking Redaction   {color(f'{redaction_pct:5.1f}%', lvl):<20s}  {dim(sparkline(redact_daily))}")

    # Reads before edits
    lvl = classify("reads_before_edits", rbe_avg)
    lines.append(f"  {status_dot(lvl)}  Reads Before Edits   {color(f'{rbe_avg:.2f}', lvl):>5s} avg          {dim(sparkline(rbe_daily))}")

    # Write ratio
    lvl = classify("write_ratio", write_ratio)
    lines.append(f"  {status_dot(lvl)}  Write Ratio          {color(f'{write_ratio:5.1f}%', lvl):<20s}  {dim(sparkline(wr_daily))}")

    # Edit vs Write (informational)
    lines.append(f"  {status_dot('dim')}  Edit vs Write        {dim(f'{total_edits} / {total_writes}')}")

    lines.append(f"  {'─' * 58}")
    return "\n".join(lines)


def format_weekly_trends(data):
    daily = data["daily"]
    days_sorted = sorted(daily.keys())
    if not days_sorted:
        return ""

    # Group days into ISO weeks
    weeks = {}  # iso_week_key -> {dates, ...aggregated data}
    for dk in days_sorted:
        d = daily[dk]
        dt = date.fromisoformat(dk)
        iso_year, iso_week, _ = dt.isocalendar()
        week_key = (iso_year, iso_week)
        if week_key not in weeks:
            # Monday of this ISO week
            monday = dt - timedelta(days=dt.weekday())
            weeks[week_key] = {
                "monday": monday,
                "iso_week": iso_week,
                "sessions": 0,
                "tool_calls": 0,
                "edits": 0,
                "writes": 0,
                "thinking_blocks": 0,
                "thinking_with_content": 0,
                "reads_before_edits": [],
            }
        w = weeks[week_key]
        w["sessions"] += d["sessions"]
        w["tool_calls"] += d["tool_calls"]
        w["edits"] += d["edits"]
        w["writes"] += d["writes"]
        w["thinking_blocks"] += d["thinking_blocks"]
        w["thinking_with_content"] += d["thinking_with_content"]
        w["reads_before_edits"].extend(d["reads_before_edits"])

    sorted_weeks = sorted(weeks.values(), key=lambda w: w["monday"])

    def _fmt_delta(value, prev_value, fmt, threshold, lower_is_better=False, colored=True):
        """Format a value with a colored delta from previous value."""
        if value is None:
            return dim("—")
        val_str = fmt(value)
        if prev_value is None:
            return val_str
        d = value - prev_value
        if abs(d) < threshold:
            return f"{val_str} {dim('→')}"
        arrow = "↑" if d > 0 else "↓"
        if not colored:
            return f"{val_str} {dim(f'{arrow}{fmt(abs(d))}')}"
        improved = (d < 0) if lower_is_better else (d > 0)
        lvl = "green" if improved else "red"
        return f"{val_str} {color(f'{arrow}{fmt(abs(d))}', lvl)}"

    # Compute per-week metrics
    week_data = []
    for w in sorted_weeks:
        rbe_list = w["reads_before_edits"]
        rbe = sum(rbe_list) / len(rbe_list) if rbe_list else None
        total_mods = w["edits"] + w["writes"]
        wr = w["writes"] / total_mods * 100 if total_mods > 0 else None
        tb = w["thinking_blocks"]
        tc = w["thinking_with_content"]
        redact = (tb - tc) / tb * 100 if tb > 0 else None
        week_data.append({"w": w, "rbe": rbe, "wr": wr, "redact": redact})

    lines = []
    lines.append(f"\n  {bold('WEEKLY TRENDS')}")
    lines.append(f"  {'─' * 72}")
    lines.append(f"  {dim('Reads/Edit = avg Read calls before each Edit/Write (higher = more careful)')}")
    lines.append(f"  {'Week':14s} {'Sess':>5s} {'Tools':>6s}   {'Reads/Edit':<16s} {'Write%':<16s} {'Redact%':<10s}")
    lines.append(f"  {'─' * 72}")

    for i, wd in enumerate(week_data):
        w = wd["w"]
        mon = w["monday"]
        label = f"W{w['iso_week']:02d} {mon.strftime('%b %d')}"
        prev_rbe = week_data[i - 1]["rbe"] if i > 0 else None
        prev_wr = week_data[i - 1]["wr"] if i > 0 else None
        prev_redact = week_data[i - 1]["redact"] if i > 0 else None

        rbe_str = _fmt_delta(wd["rbe"], prev_rbe, lambda v: f"{v:.1f}", 0.05)
        wr_str = _fmt_delta(wd["wr"], prev_wr, lambda v: f"{v:.0f}%", 1, lower_is_better=True)
        redact_str = _fmt_delta(wd["redact"], prev_redact, lambda v: f"{v:.0f}%", 1, colored=False)

        lines.append(
            f"  {label:14s} {w['sessions']:5d} {w['tool_calls']:6d}   {rbe_str}  {wr_str}  {redact_str}"
        )

    lines.append(f"  {'─' * 72}")
    return "\n".join(lines)


def format_before_after(data):
    cutoff = data["cutoff_date"]
    daily = data["daily"]
    pre_days = {k: v for k, v in daily.items() if date.fromisoformat(k) < cutoff}
    post_days = {k: v for k, v in daily.items() if date.fromisoformat(k) >= cutoff}

    lines = []
    lines.append(f"\n  {bold('BEFORE / AFTER')}  {dim(str(cutoff))}")
    lines.append(f"  {'─' * 58}")

    def period_stats(days):
        if not days:
            return None
        n_days = len(days)
        n_sessions = sum(d["sessions"] for d in days.values())
        n_tools = sum(d["tool_calls"] for d in days.values())
        n_thinking = sum(d["thinking_blocks"] for d in days.values())
        n_content = sum(d["thinking_with_content"] for d in days.values())
        n_edits = sum(d["edits"] for d in days.values())
        n_writes = sum(d["writes"] for d in days.values())
        all_rbe = []
        for d in days.values():
            all_rbe.extend(d["reads_before_edits"])
        return {
            "days": n_days,
            "sessions_day": n_sessions / n_days,
            "tools_day": n_tools / n_days,
            "thinking_day": n_thinking / n_days,
            "redacted_pct": (n_thinking - n_content) / n_thinking * 100 if n_thinking else 0,
            "edits": n_edits,
            "writes": n_writes,
            "write_ratio": n_writes / (n_edits + n_writes) * 100 if n_edits + n_writes else 0,
            "rbe_avg": sum(all_rbe) / len(all_rbe) if all_rbe else None,
        }

    pre = period_stats(pre_days)
    post = period_stats(post_days)

    # Header row
    lines.append(f"  {'':30s} {'BEFORE':>10s}  {'AFTER':>10s}  {'DELTA':>10s}")
    lines.append(f"  {'':30s} {'──────':>10s}  {'─────':>10s}  {'─────':>10s}")

    def fmt_row(label, pre_val, post_val, fmt=".1f", lower_is_better=False):
        pre_str = f"{pre_val:{fmt}}" if pre_val is not None else dim("n/a")
        post_str = f"{post_val:{fmt}}" if post_val is not None else dim("n/a")
        if pre_val is not None and post_val is not None:
            delta = post_val - pre_val
            if abs(delta) < 0.05:
                delta_str = dim("  →")
            else:
                improved = (delta < 0) if lower_is_better else (delta > 0)
                arrow = "↑" if delta > 0 else "↓"
                lvl = "green" if improved else "red"
                delta_str = color(f"{arrow}{abs(delta):{fmt}}", lvl)
        else:
            delta_str = dim("  —")
        lines.append(f"  {label:<30s} {pre_str:>10s}  {post_str:>10s}  {delta_str:>10s}")

    pre_v = lambda key: pre[key] if pre else None
    post_v = lambda key: post[key] if post else None

    fmt_row("Sessions/day", pre_v("sessions_day"), post_v("sessions_day"))
    fmt_row("Tool calls/day", pre_v("tools_day"), post_v("tools_day"))
    fmt_row("Thinking blocks/day", pre_v("thinking_day"), post_v("thinking_day"))
    fmt_row("Thinking redacted %", pre_v("redacted_pct"), post_v("redacted_pct"), ".1f")
    fmt_row("Reads before edits", pre_v("rbe_avg"), post_v("rbe_avg"), ".2f")
    fmt_row("Write ratio %", pre_v("write_ratio"), post_v("write_ratio"), ".1f", lower_is_better=True)
    fmt_row("Edits", pre_v("edits") and float(pre_v("edits")), post_v("edits") and float(post_v("edits")), ".0f")
    fmt_row("Writes", pre_v("writes") and float(pre_v("writes")), post_v("writes") and float(post_v("writes")), ".0f")

    # Stats-cache note if no pre data
    if not pre:
        stats = data.get("stats_cache")
        if stats:
            lines.append("")
            lines.append(f"  {dim('No JSONL data before cutoff. stats-cache.json summary:')}")
            ts = stats.get('totalSessions', 'N/A')
            tm = stats.get('totalMessages', 'N/A')
            fs = stats.get('firstSessionDate', 'N/A')
            ct = stats.get('lastComputedDate', 'N/A')
            lines.append(f"  {dim(f'  Total sessions (all time): {ts}')}")
            lines.append(f"  {dim(f'  Total messages (all time): {tm}')}")
            lines.append(f"  {dim(f'  First session: {fs}')}")
            lines.append(f"  {dim(f'  Cached through: {ct}')}")

    return "\n".join(lines)


def format_timeline(data):
    daily = data["daily"]
    cutoff = data["cutoff_date"]
    days_sorted = sorted(daily.keys())

    # Sparkline summaries
    rbe_vals = []
    wr_vals = []
    for dk in days_sorted:
        d = daily[dk]
        rbe = d["reads_before_edits"]
        rbe_vals.append(sum(rbe) / len(rbe) if rbe else None)
        e, w = d["edits"], d["writes"]
        wr_vals.append(w / (e + w) * 100 if e + w > 0 else None)

    lines = []
    lines.append(f"\n  {bold('DAILY TIMELINE')}")
    lines.append(f"  {'─' * 80}")
    lines.append(f"  Reads/Edit  {dim(sparkline(rbe_vals))}")
    lines.append(f"  Write %     {dim(sparkline(wr_vals))}")
    lines.append(f"  {'─' * 80}")

    # Table header
    hdr = f"  {'Date':12s} {'Sess':>5s} {'Tools':>6s} {'Think':>6s} {'Redct%':>6s} {'Rd/Ed':>6s} {'Edit':>5s} {'Write':>5s} {'W%':>5s}"
    lines.append(hdr)
    lines.append(f"  {'─' * 80}")

    for dk in days_sorted:
        d = daily[dk]
        rbe = d["reads_before_edits"]
        rbe_avg = sum(rbe) / len(rbe) if rbe else None
        edits = d["edits"]
        writes = d["writes"]
        total_mods = edits + writes

        # Format values
        rbe_str = f"{rbe_avg:.1f}" if rbe_avg is not None else dim("—")
        w_pct = writes / total_mods * 100 if total_mods > 0 else None
        w_pct_str = f"{w_pct:.0f}" if w_pct is not None else dim("—")

        tb = d["thinking_blocks"]
        tc = d["thinking_with_content"]
        redact_pct = (tb - tc) / tb * 100 if tb > 0 else None
        redact_str = f"{redact_pct:.0f}" if redact_pct is not None else dim("—")

        # Color code problem values
        if rbe_avg is not None:
            rbe_str = color(rbe_str, classify("reads_before_edits", rbe_avg))
        if w_pct is not None:
            w_pct_str = color(w_pct_str, classify("write_ratio", w_pct))

        # Cutoff marker
        is_cutoff = date.fromisoformat(dk) == cutoff
        marker = f" {color('◄ cutoff', 'yellow')}" if is_cutoff else ""

        lines.append(
            f"  {dk:12s} {d['sessions']:5d} {d['tool_calls']:6d} {tb:6d} "
            f"{redact_str:>6s} {rbe_str:>6s} {edits:5d} {writes:5d} {w_pct_str:>5s}{marker}"
        )

    return "\n".join(lines)


def format_supplemental(data):
    stats = data.get("stats_cache")
    if not stats:
        return ""

    lines = []
    lines.append(f"\n  {bold('SUPPLEMENTAL')}  {dim('(stats-cache.json)')}")
    lines.append(f"  {'─' * 58}")
    lines.append(f"  Total sessions (all time): {stats.get('totalSessions', 'N/A')}")
    lines.append(f"  Total messages (all time): {stats.get('totalMessages', 'N/A')}")
    lines.append(f"  First session:             {stats.get('firstSessionDate', 'N/A')}")
    lines.append(f"  Stats cached through:      {stats.get('lastComputedDate', 'N/A')}")

    model_usage = stats.get("modelUsage", {})
    if model_usage:
        lines.append(f"\n  Model usage:")
        for model, usage in model_usage.items():
            lines.append(f"    {model}:")
            lines.append(f"      Output tokens:       {usage.get('outputTokens', 0):>12,}")
            lines.append(f"      Cache read tokens:   {usage.get('cacheReadInputTokens', 0):>12,}")

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────

def render(data):
    """Render the full analysis report to stdout."""
    print()
    print(format_header(data))
    print(format_health_dashboard(data))
    print(format_weekly_trends(data))
    print(format_before_after(data))
    print(format_timeline(data))
    supplemental = format_supplemental(data)
    if supplemental:
        print(supplemental)
    print()

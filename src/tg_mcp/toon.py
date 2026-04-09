"""TOON format serializer — Token-Optimized Object Notation.

Produces compact list responses: ~30-60% smaller than JSON.

Format:
    type[count]{field1,field2,...}:
    value1,value2,...
    value1,value2,...

    summary: ...
    -> next step hint

Rules:
    - Commas within values escaped as \\,
    - Newlines within values replaced with " | "
    - Dates: ISO 8601 truncated (2026-04-09T14:32)
    - Numbers: no thousand separators
    - None/null rendered as empty string
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence


def _escape_value(value: Any) -> str:
    """Escape a single value for TOON output."""
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, datetime):
        return format_date(value)

    if isinstance(value, (int, float)):
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        return str(value)

    text = str(value)
    text = text.replace(",", "\\,")
    text = text.replace("\r\n", " | ").replace("\n", " | ").replace("\r", " | ")
    return text


def format_date(dt: datetime | str | None) -> str:
    """Format a datetime as truncated ISO 8601 (minute precision)."""
    if dt is None:
        return ""

    if isinstance(dt, str):
        if len(dt) >= 16 and dt[10:11] == "T":
            return dt[:16]
        return dt

    return dt.strftime("%Y-%m-%dT%H:%M")


def header(type_name: str, count: int, fields: Sequence[str]) -> str:
    """Generate the TOON header line.

    Returns: "feed[15]{date,channel,text,views}:"
    """
    if not type_name:
        raise ValueError("TOON header requires a non-empty type_name")
    if not fields:
        raise ValueError("TOON header requires at least one field")
    if count < 0:
        raise ValueError(f"TOON count must be non-negative, got {count}")

    field_list = ",".join(fields)
    return f"{type_name}[{count}]{{{field_list}}}:"


def row(values: Sequence[Any]) -> str:
    """Serialize one TOON row."""
    return ",".join(_escape_value(v) for v in values)


def format_rows(
    type_name: str,
    fields: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> str:
    """Format a complete TOON block (header + rows)."""
    lines = [header(type_name, len(rows), fields)]
    for r in rows:
        if len(r) != len(fields):
            raise ValueError(
                f"Row has {len(r)} values but header declares {len(fields)} fields: "
                f"fields={list(fields)}, row={list(r)}"
            )
        lines.append(row(r))
    return "\n".join(lines)


def summary_line(parts: Sequence[str]) -> str:
    """Build a summary line: "summary: 15 messages | 8 channels | 24h window" """
    if not parts:
        return ""
    return f"summary: {' | '.join(parts)}"


def hint(text: str) -> str:
    """Format a next-step hint line."""
    return f"\u2192 {text}"


def hints(texts: Sequence[str]) -> str:
    """Format multiple next-step hints, one per line."""
    return "\n".join(hint(t) for t in texts)


def empty_state(
    type_name: str,
    query_description: str,
    suggestions: Sequence[str],
) -> str:
    """Produce a definitive empty-state response."""
    lines = [f"0 {type_name} {query_description}."]
    if suggestions:
        lines.append(f"Try: {', '.join(suggestions)}")
    return "\n".join(lines)


def format_response(
    type_name: str,
    fields: Sequence[str],
    rows: Sequence[Sequence[Any]],
    summary_parts: Sequence[str] | None = None,
    next_hints: Sequence[str] | None = None,
) -> str:
    """Build a complete TOON response: header, rows, summary, hints."""
    parts = [format_rows(type_name, fields, rows)]

    if summary_parts:
        parts.append("")
        parts.append(summary_line(summary_parts))

    if next_hints:
        parts.append(hints(next_hints))

    return "\n".join(parts)

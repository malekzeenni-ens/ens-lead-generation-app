"""CSV cells a spreadsheet would run as formulas are made inert.

Spreadsheet apps treat a cell starting with `=`, `+`, `-`, `@`, a tab or a carriage return as a
formula, which can run commands or leak data (CSV injection). Prefixing an apostrophe keeps the text
visible and stops it running. Applied to every CSV the app writes: lead exports and files the local
assistant generates, whose content can echo text from scraped websites.
"""

from __future__ import annotations

import csv
import io
from typing import Any

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_csv_cell(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip(" ").startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def safe_csv_text(content: str) -> str:
    """Re-write CSV text with every cell made inert. Rows and quoting are preserved."""
    rows = csv.reader(io.StringIO(content))
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    for row in rows:
        writer.writerow([safe_csv_cell(cell) for cell in row])
    return output.getvalue()

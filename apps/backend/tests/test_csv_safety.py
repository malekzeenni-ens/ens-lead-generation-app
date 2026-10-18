"""No CSV the app writes can carry a cell that runs as a spreadsheet formula (H3)."""

from __future__ import annotations

import csv
import io

import pytest

from app.core.config import Settings
from app.core.csv_safety import safe_csv_cell, safe_csv_text
from app.domains.assistant.files import AssistantFileStore


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('=HYPERLINK("https://evil.test")', '\'=HYPERLINK("https://evil.test")'),
        ("+44 1582", "'+44 1582"),
        ("-1+1", "'-1+1"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tcmd", "'\tcmd"),
        ("  =1+1", "'  =1+1"),
        ("Plain text", "Plain text"),
        ("a=b", "a=b"),
        (42, 42),
        (None, None),
    ],
)
def test_safe_csv_cell(value: object, expected: object) -> None:
    assert safe_csv_cell(value) == expected


def test_safe_csv_text_keeps_rows_and_quoted_commas() -> None:
    cleaned = safe_csv_text('name,note\n"Crown, Leeds",=2+2\nHarbour,fine\n')
    assert list(csv.reader(io.StringIO(cleaned))) == [
        ["name", "note"],
        ["Crown, Leeds", "'=2+2"],
        ["Harbour", "fine"],
    ]


def test_a_generated_csv_attachment_is_made_inert(settings: Settings) -> None:
    store = AssistantFileStore(settings)
    attachment = store.generated(
        conversation_id="conversation",
        message_id="message",
        requested_format="csv",
        suggested_filename="leads",
        content="business,website\nCrown,=cmd|' /C calc'!A0\n",
    )
    stored = store.path(attachment).read_bytes().decode("utf-8-sig")
    assert list(csv.reader(io.StringIO(stored)))[1] == ["Crown", "'=cmd|' /C calc'!A0"]

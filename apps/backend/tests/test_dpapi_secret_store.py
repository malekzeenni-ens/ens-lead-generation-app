"""The Windows DPAPI vault round-trips secrets and reports real error codes (H2)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.secrets import DpapiSecretStore

pytestmark = pytest.mark.skipif(os.name != "nt", reason="DPAPI is only available on Windows")


def test_a_secret_round_trips_and_is_not_stored_in_clear(tmp_path: Path) -> None:
    store = DpapiSecretStore(tmp_path)
    store.set_json("provider", {"api_key": "sk-test-value"})

    assert store.get_json("provider") == {"api_key": "sk-test-value"}
    vault = next(tmp_path.glob("*.vault"))
    assert b"sk-test-value" not in vault.read_bytes()
    store.delete("provider")
    assert store.get_json("provider") is None


def test_a_damaged_vault_raises_with_the_windows_error_code(tmp_path: Path) -> None:
    store = DpapiSecretStore(tmp_path)
    store.set_json("provider", {"api_key": "sk-test-value"})
    vault = next(tmp_path.glob("*.vault"))
    vault.write_bytes(b"\x01\x02 not a protected blob")

    with pytest.raises(OSError) as raised:
        store.get_json("provider")
    assert raised.value.errno not in (None, 0)

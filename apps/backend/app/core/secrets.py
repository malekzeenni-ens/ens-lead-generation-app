from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
from typing import Protocol


class SecretStore(Protocol):
    def get_json(self, key: str) -> dict[str, object] | None: ...

    def set_json(self, key: str, value: dict[str, object]) -> None: ...

    def delete(self, key: str) -> None: ...


class MemorySecretStore:
    """Non-persistent store used by tests and unsupported development platforms."""

    def __init__(self) -> None:
        self._values: dict[str, dict[str, object]] = {}

    def get_json(self, key: str) -> dict[str, object] | None:
        value = self._values.get(key)
        return dict(value) if value is not None else None

    def set_json(self, key: str, value: dict[str, object]) -> None:
        self._values[key] = dict(value)

    def delete(self, key: str) -> None:
        self._values.pop(key, None)


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class DpapiSecretStore:
    """Small Windows user-scoped DPAPI vault; SQLite stores no provider secrets."""

    _ENTROPY = b"EtchNShine.LeadGeneration.v1"

    def __init__(self, directory: Path) -> None:
        if os.name != "nt":
            raise RuntimeError("DPAPI secret storage is only available on Windows")
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.vault"

    @staticmethod
    def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
        buffer = ctypes.create_string_buffer(data)
        pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        return _DataBlob(len(data), pointer), buffer

    @classmethod
    def _protect(cls, plaintext: bytes) -> bytes:
        source, source_buffer = cls._blob(plaintext)
        entropy, entropy_buffer = cls._blob(cls._ENTROPY)
        output = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        result = crypt32.CryptProtectData(
            ctypes.byref(source),
            "Etch N Shine provider credentials",
            ctypes.byref(entropy),
            None,
            None,
            0,
            ctypes.byref(output),
        )
        del source_buffer, entropy_buffer
        if not result:
            raise OSError(ctypes.get_last_error(), "Windows could not protect provider credentials")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)

    @classmethod
    def _unprotect(cls, ciphertext: bytes) -> bytes:
        source, source_buffer = cls._blob(ciphertext)
        entropy, entropy_buffer = cls._blob(cls._ENTROPY)
        output = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        result = crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            ctypes.byref(entropy),
            None,
            None,
            0,
            ctypes.byref(output),
        )
        del source_buffer, entropy_buffer
        if not result:
            raise OSError(ctypes.get_last_error(), "Windows could not unlock provider credentials")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)

    def get_json(self, key: str) -> dict[str, object] | None:
        path = self._path(key)
        if not path.exists():
            return None
        decoded = json.loads(self._unprotect(path.read_bytes()).decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("The protected credential record is invalid")
        return decoded

    def set_json(self, key: str, value: dict[str, object]) -> None:
        path = self._path(key)
        protected = self._protect(json.dumps(value, separators=(",", ":")).encode("utf-8"))
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(protected)
        os.replace(temporary, path)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def build_secret_store(data_directory: Path) -> SecretStore:
    if os.name == "nt":
        return DpapiSecretStore(data_directory / "secrets")
    return MemorySecretStore()

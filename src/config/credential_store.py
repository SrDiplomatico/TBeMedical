"""Windows-only encrypted storage for eMedical credentials."""

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path
from typing import Optional


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


_CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _credentials_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise OSError("LOCALAPPDATA is not available")
    return Path(local_app_data) / "PDF Form Data Extractor" / "credentials.dat"


def _to_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _protect(data: bytes) -> bytes:
    input_blob, input_buffer = _to_blob(data)
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "eMedical credentials",
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def _unprotect(data: bytes) -> bytes:
    input_blob, input_buffer = _to_blob(data)
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def save_credentials(username: str, password: str) -> None:
    """Encrypt credentials for the current Windows user and save them locally."""
    payload = json.dumps(
        {"username": username, "password": password},
        separators=(",", ":"),
    ).encode("utf-8")
    encrypted = _protect(payload)
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_bytes(encrypted)
    temporary_path.replace(path)


def load_credentials() -> Optional[tuple[str, str]]:
    """Load credentials encrypted for the current Windows user, if present."""
    path = _credentials_path()
    if not path.exists():
        return None

    try:
        payload = json.loads(_unprotect(path.read_bytes()).decode("utf-8"))
        username = payload.get("username")
        password = payload.get("password")
        if isinstance(username, str) and isinstance(password, str) and username and password:
            return username, password
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return None
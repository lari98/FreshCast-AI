"""Attack phase 1: hostile uploads against the CSV intake.

Every case is something an attacker (or a careless export) could send. The
expected outcome is always the same: refuse or neutralise, never crash, never
pass the payload on to the dashboard.
"""

from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pandas as pd
import pytest

from freshcast.byod.analyze import analyze
from freshcast.byod.ingest import IngestError, read_csv_bytes
from freshcast.security.upload_guard import (
    UploadRejected,
    check_filename,
    clean_text,
    guard_upload,
    is_safe_id,
)


@pytest.fixture(scope="module")
def one_store(sales: pd.DataFrame) -> pd.DataFrame:
    s = sales[sales["store_id"] == "DE-MUC-001"]
    s = s[s["sku"].isin(["MILK-1L", "BREAD-WHEAT-750G"]) & s["is_open"]]
    return s[["store_id", "sku", "business_date", "units_sold"]]


GOOD = b"store_id,sku,business_date,units_sold\nDE-MUC-001,MILK-1L,2026-01-02,5\n"
# The standard antivirus test string, assembled at run time so that this file
# itself is not flagged by an antivirus scanner on a developer machine.
EICAR = (
    "X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
).encode()


@pytest.mark.parametrize(
    ("payload", "label"),
    [
        (b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64, "Windows executable"),
        (b"\x7fELF\x02\x01\x01" + b"\x00" * 64, "Linux executable"),
        (b"PK\x03\x04\x14\x00\x00\x00", "ZIP"),
        (b"%PDF-1.7\n%\xe2\xe3\xcf\xd3", "PDF"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32, "Office"),
        (b"\x1f\x8b\x08\x00" + b"\x00" * 16, "gzip"),
        (b"#!/bin/sh\nrm -rf /\n", "shell script"),
        (b"\x89PNG\r\n\x1a\n", "image"),
        (b"\xef\xbb\xbfMZ\x90\x00", "executable behind a BOM"),
    ],
)
def test_disguised_binaries_are_refused(payload: bytes, label: str) -> None:
    with pytest.raises(IngestError) as err:
        read_csv_bytes(payload, "sales.csv")
    assert label.split()[0].lower() in str(err.value).lower() or "binary" in str(
        err.value
    )


HEAD = b"store_id,sku,business_date,units_sold\n"


def _row(store: bytes = b"A", sku: bytes = b"B", tail: bytes = b"") -> bytes:
    return HEAD + store + b"," + sku + b",2026-01-02,5" + tail + b"\n"


@pytest.mark.parametrize(
    "payload",
    [
        _row(sku=b"B<script>alert(1)</script>"),
        _row(store=b"<?php system($_GET[1]); ?>"),
        _row(sku=b"javascript:alert(1)"),
        _row(sku=b"<img src=x onerror=alert(1)>"),
        _row(sku=b"<iframe src=//evil></iframe>"),
        _row(tail=b"\x00"),
        HEAD + _row(tail=b"\x07\x07\x07").split(b"\n", 1)[1] * 50,
    ],
)
def test_script_markup_and_control_characters_are_refused(payload: bytes) -> None:
    with pytest.raises(IngestError):
        read_csv_bytes(payload, "sales.csv")


def test_absurd_shapes_are_refused() -> None:
    long_line = b"store_id,sku,business_date,units_sold\n" + b"A" * 150_000 + b"\n"
    with pytest.raises(IngestError, match="unusually long"):
        read_csv_bytes(long_line, "sales.csv")
    wide = (",".join(f"c{i}" for i in range(150)) + "\n1\n").encode()
    with pytest.raises(IngestError, match="columns"):
        read_csv_bytes(wide, "sales.csv")


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd.csv",
        "..\\..\\windows\\system32\\x.csv",
        "C:\\temp\\sales.csv",
        "sales.csv.exe",
        "sales.exe",
        "macro.xlsm",
        "report.ps1",
        "x.csv\x00.exe",
        "",
        "sales.js.csv.sh",
    ],
)
def test_dangerous_file_names_are_refused(name: str) -> None:
    with pytest.raises(UploadRejected):
        check_filename(name)


def test_normal_file_names_pass() -> None:
    assert check_filename("Absatz 2026.CSV") == "Absatz 2026.CSV"
    assert check_filename("bestand.txt") == "bestand.txt"


def test_legitimate_german_export_is_not_a_false_positive() -> None:
    latin1 = (
        "Filiale;Artikel;Datum;Menge\nDE-MUC-001;Käse-Müsli ß;22.12.2025;5\n".encode(
            "latin-1"
        )
    )
    df = read_csv_bytes(latin1, "export.csv")
    assert df.shape[0] == 1
    assert guard_upload(GOOD, "sales.csv") == "sales.csv"


def test_formula_injection_is_neutralised_in_text_columns(
    one_store: pd.DataFrame,
) -> None:
    rows = one_store.copy()
    rows["product_name"] = "=cmd|' /C calc'!A0"
    rows["category"] = "@SUM(1+1)"
    rows["Handelskette"] = '+HYPERLINK("http://evil")'
    payload = analyze(rows.to_csv(index=False).encode())
    for item in payload["items"]:
        for text in (item["name"]["de"], item["category"], item["chain"]):
            assert not text.startswith(("=", "+", "-", "@")), text
    assert clean_text("-2+3") == "2+3"
    assert clean_text("=1+1\t") == "1+1"


@pytest.mark.parametrize(
    "bad", ["x;DROP TABLE", "<b>", "../x", "a" * 80, "", " ", "\x07"]
)
def test_unsafe_identifiers_are_dropped_not_stored(
    one_store: pd.DataFrame, bad: str
) -> None:
    rows = pd.concat(
        [one_store, one_store.iloc[:1].assign(store_id=bad)], ignore_index=True
    )
    payload = analyze(rows.to_csv(index=False).encode())
    assert all(is_safe_id(i["store_id"]) for i in payload["items"])
    assert any(
        "unreadable rows were dropped" in w for w in payload["quality"]["warnings"]
    )


def test_many_bad_identifiers_reject_the_whole_file(one_store: pd.DataFrame) -> None:
    rows = one_store.assign(store_id="<script>")
    with pytest.raises(IngestError):
        analyze(rows.to_csv(index=False).encode())


@contextmanager
def _fake_clamd() -> Iterator[int]:
    """Minimal ClamAV INSTREAM server: flags any stream that holds the test string."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def serve() -> None:
        conn, _ = server.accept()
        with conn:
            assert conn.recv(10) == b"zINSTREAM\x00"
            body = b""
            while True:
                size = struct.unpack("!I", conn.recv(4))[0]
                if size == 0:
                    break
                remaining = size
                while remaining:
                    part = conn.recv(remaining)
                    body += part
                    remaining -= len(part)
            verdict = b"Eicar-Test-Signature FOUND" if b"EICAR" in body else b"OK"
            conn.sendall(b"stream: " + verdict + b"\x00")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield server.getsockname()[1]
    finally:
        server.close()
        thread.join(timeout=2)


def test_scanner_blocks_the_antivirus_test_string() -> None:
    with _fake_clamd() as port, pytest.raises(UploadRejected, match="flagged"):
        guard_upload(GOOD + EICAR, "sales.csv", ("127.0.0.1", port))


def test_scanner_lets_a_clean_file_through() -> None:
    with _fake_clamd() as port:
        assert guard_upload(GOOD, "sales.csv", ("127.0.0.1", port)) == "sales.csv"


def test_unreachable_scanner_fails_closed() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(UploadRejected, match="not reachable"):
        guard_upload(GOOD, "sales.csv", ("127.0.0.1", port))


def test_rejections_are_logged_without_file_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = b"MZ\x90\x00" + b"TOPSECRET-CONTENT"
    with (
        caplog.at_level("WARNING", logger="freshcast.security"),
        pytest.raises(IngestError),
    ):
        read_csv_bytes(secret, "x.csv")
    assert "upload rejected" in caplog.text
    assert "TOPSECRET" not in caplog.text and "sha256=" in caplog.text


def test_header_only_and_empty_files_give_a_clean_error() -> None:
    for body in (b"store_id,sku,business_date,units_sold\n", b"", b"\n\n"):
        with pytest.raises(IngestError):
            analyze(body)

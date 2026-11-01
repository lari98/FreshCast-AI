"""Reject uploads that are not plain CSV text before any parser sees them.

Threat model: a user (or an attacker using a user's session) uploads a file that
is not a sales export, for example an executable renamed to ``.csv``, an archive
that expands to gigabytes, an HTML/script payload, or a spreadsheet that runs a
formula when opened in Excel (CSV injection).

What this module does:

* checks the file name (no paths, no executable extensions, ``.csv``/``.txt`` only),
* checks the first bytes against known binary formats (magic numbers),
* rejects NUL bytes, many control characters, absurd line/column sizes,
* rejects markup and script payloads that never occur in a sales export,
* cleans text columns (control characters, leading formula characters),
* optionally asks a ClamAV daemon (``clamd``) for a signature scan.

What it does NOT do: it is not an antivirus engine. Signature scanning needs
ClamAV or a managed scanner; without it only the structural checks run. The
file is never written to disk or executed; it is parsed in memory as text, so
even an undetected payload has no way to run.
"""

from __future__ import annotations

import hashlib
import logging
import re
import socket
import struct

LOG = logging.getLogger("freshcast.security")

ALLOWED_EXTENSIONS = (".csv", ".txt", ".tsv")
MAX_LINE_CHARS = 100_000
MAX_COLUMNS = 100
MAX_TEXT_CHARS = 80
MAX_CONTROL_SHARE = 0.001

# (prefix, label). Checked after an optional UTF-8 BOM is removed.
BINARY_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "Windows executable"),
    (b"\x7fELF", "Linux executable"),
    (b"\xcf\xfa\xed\xfe", "macOS executable"),
    (b"\xce\xfa\xed\xfe", "macOS executable"),
    (b"\xca\xfe\xba\xbe", "Java class or universal binary"),
    (b"PK\x03\x04", "ZIP, Office or JAR archive"),
    (b"PK\x05\x06", "ZIP archive"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "legacy Office document (may hold macros)"),
    (b"%PDF", "PDF document"),
    (b"\x1f\x8b", "gzip archive"),
    (b"BZh", "bzip2 archive"),
    (b"\xfd7zXZ\x00", "xz archive"),
    (b"7z\xbc\xaf\x27\x1c", "7-Zip archive"),
    (b"Rar!\x1a\x07", "RAR archive"),
    (b"{\\rtf", "RTF document"),
    (b"\x89PNG", "image"),
    (b"\xff\xd8\xff", "image"),
    (b"GIF8", "image"),
    (b"#!", "shell script"),
)

# Text that never belongs in a sales or stock export.
PAYLOAD_PATTERNS = re.compile(
    r"<\s*(script|iframe|object|embed|svg|html|body|img|link|meta)\b"
    r"|<\?php|javascript\s*:|vbscript\s*:|data\s*:\s*text/html"
    r"|\bpowershell(\.exe)?\b.*-enc|\bcmd(\.exe)?\s*/c\b",
    re.IGNORECASE,
)
EXECUTABLE_EXT = re.compile(
    r"\.(exe|dll|bat|cmd|com|scr|msi|ps1|vbs|js|jse|wsf|jar|lnk|sh|py|php|hta|reg)"
    r"(\.|$)",
    re.IGNORECASE,
)
FORMULA_LEAD = "=+-@\t\r"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\- ]{0,63}$")


class UploadRejected(ValueError):
    """The upload failed a security check; ``reason`` is safe to show the user."""

    def __init__(self, reason: str) -> None:
        """Keep the reason for the response and the audit log."""
        super().__init__(reason)
        self.reason = reason


def _audit(reason: str, data: bytes, name: str) -> None:
    """Log a rejected upload without its content (hash prefix only)."""
    LOG.warning(
        "upload rejected: %s (file=%r, bytes=%d, sha256=%s)",
        reason,
        name[:80],
        len(data),
        hashlib.sha256(data).hexdigest()[:16],
    )


def check_filename(name: str) -> str:
    """Return a safe display name or raise :class:`UploadRejected`."""
    if not name or "\x00" in name:
        raise UploadRejected("missing or invalid file name")
    if any(sep in name for sep in ("/", "\\", "..")) or ":" in name:
        raise UploadRejected("file name must not contain a path")
    if EXECUTABLE_EXT.search(name):
        raise UploadRejected("executable file types are not accepted")
    if not name.lower().endswith(ALLOWED_EXTENSIONS):
        raise UploadRejected("only .csv, .tsv and .txt files are accepted")
    return name[:120]


def inspect_bytes(data: bytes, name: str = "file") -> None:
    """Run the structural checks on raw bytes; raise :class:`UploadRejected`."""
    try:
        _inspect(data)
    except UploadRejected as exc:
        _audit(exc.reason, data, name)
        raise


def _inspect(data: bytes) -> None:
    body = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    head = body[:16]
    for prefix, label in BINARY_SIGNATURES:
        if head.startswith(prefix):
            raise UploadRejected(f"this is a {label}, not a CSV text file")
    if b"\x00" in body:
        raise UploadRejected("binary content (NUL byte) found")
    # Control characters other than tab, CR and LF do not occur in exports.
    controls = sum(1 for b in body if b < 32 and b not in (9, 10, 13))
    if body and controls / len(body) > MAX_CONTROL_SHARE:
        raise UploadRejected("too many control characters for a text file")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")  # older German exports
    lines = text.splitlines()
    if lines and max(len(line) for line in lines) > MAX_LINE_CHARS:
        raise UploadRejected("a line is unusually long; this is not a sales export")
    if lines and max(lines[0].count(s) for s in (";", ",", "\t")) >= MAX_COLUMNS:
        raise UploadRejected(f"more than {MAX_COLUMNS} columns")
    if PAYLOAD_PATTERNS.search(text):
        raise UploadRejected("script or markup content found in the file")


def clean_text(value: str) -> str:
    """Make a free-text cell safe: no control chars, no leading formula chars."""
    cleaned = "".join(ch for ch in value if ch.isprintable()).strip()
    return cleaned.lstrip(FORMULA_LEAD + " ")[:MAX_TEXT_CHARS]


def is_safe_id(value: str) -> bool:
    """Return True for ids made of letters, digits, dash, dot and underscore."""
    return bool(SAFE_ID.match(value))


def scan_with_clamd(
    data: bytes, host: str, port: int = 3310, timeout: float = 20.0
) -> str | None:
    """Scan ``data`` with a ClamAV daemon (INSTREAM); return the signature or None.

    Raises :class:`OSError` when the daemon cannot be reached, so the caller can
    fail closed instead of treating "unreachable" as "clean".
    """
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(b"zINSTREAM\x00")
        for start in range(0, len(data), 64 * 1024):
            chunk = data[start : start + 64 * 1024]
            sock.sendall(struct.pack("!I", len(chunk)) + chunk)
        sock.sendall(struct.pack("!I", 0))
        reply = b""
        while not reply.endswith(b"\x00") and (part := sock.recv(4096)):
            reply += part
    text = reply.rstrip(b"\x00").decode("ascii", "replace").strip()
    if text.endswith("FOUND"):
        return text.removeprefix("stream:").removesuffix("FOUND").strip()
    if text.endswith("OK"):
        return None
    raise OSError(f"unexpected clamd reply: {text[:80]}")


def guard_upload(
    data: bytes,
    name: str,
    clamd: tuple[str, int] | None = None,
) -> str:
    """Full check for one uploaded file; return the safe file name.

    ``clamd`` is ``(host, port)`` when a scanner is configured. If it is set and
    cannot be reached the upload is rejected (fail closed).
    """
    try:
        safe = check_filename(name)
    except UploadRejected as exc:
        _audit(exc.reason, data, name)
        raise
    inspect_bytes(data, safe)
    if clamd is not None:
        try:
            found = scan_with_clamd(data, *clamd)
        except OSError as exc:
            _audit("malware scanner unavailable (fail closed)", data, safe)
            raise UploadRejected(
                "the malware scanner is not reachable; upload refused"
            ) from exc
        if found:
            _audit(f"malware signature {found}", data, safe)
            raise UploadRejected("the malware scanner flagged this file")
    return safe

#!/usr/bin/env python3
"""PSE-only one-file FTPS write/read/delete permission test.

Must never run against any other account/domain or overwrite an existing file.
Uploads at most 100 bytes under a random hidden name in PSE frontend public_html,
verifies the exact bytes by RETR, then deletes only that file in finally.
"""
import ftplib
import hashlib
import io
import os
import secrets
import ssl
from urllib.parse import urlsplit

TARGET = "/domains/pse.webnvn.com/public_html"
HOST = "vt108159.server.idn.vn"

raw = os.environ.get("FTP_SERVER", "").strip()
if "://" not in raw:
    raw = "ftp://" + raw
parsed = urlsplit(raw)
if (
    parsed.hostname != HOST or parsed.scheme not in ("ftp", "ftps")
    or parsed.username or parsed.password or parsed.path.strip("/")
    or not os.environ.get("FTP_USERNAME")
    or not os.environ.get("FTP_PASSWORD")
):
    raise SystemExit("FTP_PROBE=FAIL invalid PSE FTPS configuration")

filename = ".pse-ftps-write-probe-" + secrets.token_hex(16) + ".txt"
payload = b"PSE_FTPS_WRITE_PERMISSION_TEST_V1\n" + secrets.token_hex(10).encode("ascii") + b"\n"
assert len(payload) < 100
uploaded = False
deleted = False
ftp = ftplib.FTP_TLS(context=ssl.create_default_context(), timeout=15)

try:
    ftp.connect(parsed.hostname, parsed.port or 21, timeout=15)
    ftp.auth()
    ftp.login(os.environ["FTP_USERNAME"], os.environ["FTP_PASSWORD"])
    ftp.prot_p()
    print("FTP_PROBE tls_login=PASS")

    ftp.cwd(TARGET)
    remote_dir = ftp.pwd().rstrip("/")
    # Required even if FTP server has alternate CWD aliases/chroot mapping:
    # abort rather than write to an unverified destination.
    if remote_dir != TARGET:
        raise RuntimeError("PWD did not match the exact PSE frontend directory")
    print("FTP_PROBE target_directory=PASS")

    try:
        ftp.size(filename)
    except ftplib.error_perm as exc:
        if not str(exc).startswith("550"):
            raise RuntimeError("Could not verify target probe filename is absent")
    else:
        raise RuntimeError("Random probe filename already exists: refusing overwrite")

    ftp.storbinary("STOR " + filename, io.BytesIO(payload), blocksize=4096)
    uploaded = True
    print("FTP_PROBE write=PASS")

    back = io.BytesIO()
    ftp.retrbinary("RETR " + filename, back.write, blocksize=4096)
    if hashlib.sha256(back.getvalue()).digest() != hashlib.sha256(payload).digest():
        raise RuntimeError("Read-back SHA256 mismatch")
    print("FTP_PROBE read_back_sha256=PASS")
finally:
    # Delete only our cryptographically random probe path, never a website file.
    if uploaded:
        try:
            ftp.cwd(TARGET)
            if ftp.pwd().rstrip("/") == TARGET:
                ftp.delete(filename)
                deleted = True
                print("FTP_PROBE cleanup_delete=PASS")
            else:
                print("FTP_PROBE cleanup_delete=FAIL_directory_changed")
        except Exception as exc:
            print("FTP_PROBE cleanup_delete=FAIL_" + type(exc).__name__)
    try:
        ftp.quit()
    except Exception:
        ftp.close()

if not uploaded or not deleted:
    raise SystemExit("FTP_PROBE=FAIL")
print("FTP_PROBE=PASS write_read_delete_verified")

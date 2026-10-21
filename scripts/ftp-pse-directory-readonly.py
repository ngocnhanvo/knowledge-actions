#!/usr/bin/env python3
"""Strict TLS read-only FTP destination-boundary check. No RETR/STOR/DELE.

Checks directory visibility with CWD/PWD only. A denied CWD alone is not proof of
access-control isolation or of the correct FTP deployment directory.
"""
import ftplib
import os
import ssl
from urllib.parse import urlsplit

raw = os.getenv("FTP_SERVER", "").strip()
if "://" not in raw:
    raw = "ftp://" + raw
u = urlsplit(raw)
if (u.scheme not in ("ftp", "ftps") or u.hostname != "vt108159.server.idn.vn"
    or not os.getenv("FTP_USERNAME") or not os.getenv("FTP_PASSWORD")
    or u.username or u.password or u.path.strip("/")):
    print("FTPS_SCOPE config_or_hostname_invalid")
    raise SystemExit(1)

ftp = ftplib.FTP_TLS(context=ssl.create_default_context(),timeout=8)
try:
    ftp.connect(u.hostname,u.port or 21,timeout=8)
    ftp.auth()
    ftp.login(os.environ["FTP_USERNAME"],os.environ["FTP_PASSWORD"])
    ftp.prot_p()
    home=ftp.pwd()
    print("FTPS_SCOPE strict_tls_login=PASS")
    print("FTPS_SCOPE home_is_root=" + ("yes" if home=="/" else "no"))
    # Read-only probes are limited to the specified project frontend and the
    # neighbouring source-project roots. No directory creation/deletion.
    targets=[
        ("cwd_dot", "."),
        ("cwd_public_html", "public_html"),
        ("cwd_pse_absolute", "/domains/pse.webnvn.com/public_html"),
        ("cwd_pse_relative", "domains/pse.webnvn.com/public_html"),
        ("cwd_pse_parent", "../domains/pse.webnvn.com/public_html"),
        ("cwd_admin_pse_absolute", "/domains/admin-pse.webnvn.com/public_html"),
        ("cwd_eduresearch_absolute", "/domains/nghiencuukhoahoc.webnvn.com/public_html"),
        ("cwd_eduresearch_relative", "domains/nghiencuukhoahoc.webnvn.com/public_html"),
    ]
    for label,path in targets:
        try:
            ftp.cwd(home)
            ftp.cwd(path)
            print("FTPS_SCOPE "+label+"=YES")
        except ftplib.error_perm:
            print("FTPS_SCOPE "+label+"=DENIED_OR_NOT_FOUND")
        except (TimeoutError,ConnectionError,OSError,ftplib.Error) as e:
            print("FTPS_SCOPE "+label+"=UNVERIFIED_NETWORK_"+type(e).__name__)
            break
    print("FTPS_SCOPE remote_changes=NONE")
except (TimeoutError,ConnectionError,OSError,ftplib.Error) as e:
    print("FTPS_SCOPE strict_login_or_connection_failed="+type(e).__name__)
    raise SystemExit(1)
finally:
    try:
        ftp.close()
    except Exception:
        pass

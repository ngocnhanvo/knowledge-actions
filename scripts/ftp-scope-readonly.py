#!/usr/bin/env python3
"""Read-only FTPS scope audit.

Only AUTH TLS, USER/PASS, PWD, NLST, CWD, QUIT. Never uploads, edits,
downloads a file, prints credentials, arbitrary filenames, or remote contents.
"""
import ftplib
import hmac
import hashlib
import os
import re
import ssl
from urllib.parse import urlsplit

who = os.environ.get("PROJECT_NAME", "")
assert who in ("PSE", "EDURESEARCH"), "Unexpected project label"
server = os.environ.get("FTP_SERVER", "").strip()
username = os.environ.get("FTP_USERNAME", "")
password = os.environ.get("FTP_PASSWORD", "")
shared_key = os.environ.get("SOURCE_REPO_PAT", "")
if not (server and username and password):
    print("FTPS_AUDIT login=missing_credentials")
    raise SystemExit(1)
if "://" not in server:
    server = "ftp://" + server
u = urlsplit(server)
assert u.scheme in ("ftp", "ftps") and u.hostname, "Invalid FTPS server format"
assert not u.username and not u.password and not u.path.strip("/"), "FTP_SERVER must contain only a host/port"
port = u.port or 21

def account_id(text):
    if not shared_key:
        return "not_available"
    return hmac.new(shared_key.encode(), text.encode(), hashlib.sha256).hexdigest()[:24]

ftp = ftplib.FTP_TLS(context=ssl.create_default_context(), timeout=12)
try:
    ftp.connect(u.hostname, port, timeout=12)
    ftp.login(username, password)
    ftp.prot_p()
    root = ftp.pwd()
    print("FTPS_AUDIT login=PASS")
    print("FTPS_AUDIT tls=certificate_verified_data_protected")
    print("FTPS_AUDIT pwd_kind=" + ("root_or_chroot" if root == "/" else "nested_chroot_or_account_home"))
    print("FTPS_AUDIT hmac_key_present=" + ("yes" if shared_key else "no"))
    # HMAC keyed using existing shared SOURCE_REPO_PAT. Never output raw FTP identity or secret.
    print("FTPS_AUDIT endpoint_ref=" + account_id(u.hostname.lower() + ":" + str(port)))
    print("FTPS_AUDIT account_ref=" + account_id(u.hostname.lower() + ":" + str(port) + "|" + username))
    names = []
    try:
        names = ftp.nlst()
        entries = [v.rstrip("/").split("/")[-1] for v in names]
        known = ("domains", "public_html", "private_html", "wp-admin", "wp-content",
                 "wp-includes", "index.php", "index.html", "cgi-bin", "assets",
                 "pse.webnvn.com", "admin-pse.webnvn.com",
                 "nghiencuukhoahoc.webnvn.com", "api-nghiencuukhoahoc.webnvn.com")
        print("FTPS_AUDIT root_list=PASS")
        print("FTPS_AUDIT root_item_count=" + str(len(entries)))
        for item in known:
            label = re.sub(r"[^A-Za-z0-9]+", "_", item).strip("_")
            print("FTPS_ROOT " + label + "=" + ("present" if item in entries else "absent"))
    except Exception:
        print("FTPS_AUDIT root_list=failed_or_blocked")
    # Read-only directory traversal; never assume failed CWD establishes ACL isolation
    test_dirs = (
      ("ftp_public_html", "public_html"),
      ("ftp_domains", "domains"),
      ("wp_admin", "wp-admin"),
      ("wp_content", "wp-content"),
      ("pse_web", "/domains/pse.webnvn.com/public_html"),
      ("pse_admin", "/domains/admin-pse.webnvn.com/public_html"),
      ("nckh_web", "/domains/nghiencuukhoahoc.webnvn.com/public_html"),
      ("nckh_api", "/domains/api-nghiencuukhoahoc.webnvn.com/public_html"),
      ("relative_pse_web", "domains/pse.webnvn.com/public_html"),
      ("relative_pse_admin", "domains/admin-pse.webnvn.com/public_html"),
      ("relative_nckh_web", "domains/nghiencuukhoahoc.webnvn.com/public_html"),
      ("relative_nckh_api", "domains/api-nghiencuukhoahoc.webnvn.com/public_html"),
      ("parent_pse_web", "../domains/pse.webnvn.com/public_html"),
      ("parent_pse_admin", "../domains/admin-pse.webnvn.com/public_html"),
      ("parent_nckh_web", "../domains/nghiencuukhoahoc.webnvn.com/public_html"),
      ("parent_nckh_api", "../domains/api-nghiencuukhoahoc.webnvn.com/public_html"),
    )
    for label,path in test_dirs:
        try:
            ftp.cwd(root)
            ftp.cwd(path)
            print("FTPS_CWD " + label + "=yes")
        except Exception:
            print("FTPS_CWD " + label + "=no_or_unverified")
    print("FTPS_AUDIT remote_changes=NONE")
except Exception as exc:
    # Do not print sensitive connection string/server banners in exceptions.
    print("FTPS_AUDIT connection=FAILED class=" + type(exc).__name__)
    raise SystemExit(1)
finally:
    try: ftp.quit()
    except Exception: ftp.close()

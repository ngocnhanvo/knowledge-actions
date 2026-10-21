#!/usr/bin/env python3
"""Read-only FTPS scope audit via lftp with enforced TLS certificate verification.

Allowed network actions: AUTH TLS, USER, PASS, PWD, NLST, CWD, QUIT.
No RETR, STOR, DELE, MKD, RMD, RNFR/RNTO or file data sent to logs.
"""
import hashlib
import hmac
import os
import re
import subprocess
from urllib.parse import urlsplit

project = os.getenv("PROJECT_NAME", "")
assert project in ("PSE", "EDURESEARCH")
server = os.getenv("FTP_SERVER", "").strip()
username = os.getenv("FTP_USERNAME", "")
password = os.getenv("FTP_PASSWORD", "")
key = os.getenv("SOURCE_REPO_PAT", "")
assert server and username and password, "FTPS credentials missing"
if "://" not in server:
    server = "ftp://" + server
url = urlsplit(server)
assert url.scheme == "ftp" and url.hostname and not url.path.strip("/"), "Invalid FTP_SERVER"
assert not url.username and not url.password, "FTP_SERVER must only contain a host/port"
port = url.port or 21
endpoint = f"ftp://{url.hostname}:{port}"

def ref(identity):
    if not key:
        return "not_available"
    return hmac.new(key.encode(), identity.encode(), hashlib.sha256).hexdigest()[:24]

def lftp(action):
    # The shell never logs the assembled command or the credentials.
    # When calling lftp, keep TLS certificate and data-channel verification enabled.
    commands = (
      "set cmd:fail-exit yes; "
      "set net:max-retries 1; set net:timeout 8; "
      "set ftp:passive-mode yes; set ftp:ssl-force yes; "
      "set ftp:ssl-protect-data yes; set ssl:verify-certificate yes; "
      + action + "; bye"
    )
    proc = subprocess.run(
        ["lftp", "-u", username + "," + password, endpoint, "-e", commands],
        text=True, capture_output=True, timeout=23, check=False
    )
    # Only allow predictable outputs back to the workflow, not remote banners/errors.
    return proc.returncode == 0, proc.stdout.strip()

ok,pwd = lftp("pwd")
if not ok:
    print("FTPS_AUDIT login_or_pwd=FAILED_TLS_ENFORCED")
    raise SystemExit(1)
print("FTPS_AUDIT login=PASS")
print("FTPS_AUDIT tls=certificate_verification_required")
print("FTPS_AUDIT pwd_kind=" + ("root_or_chroot" if pwd == "/" else "nested_or_account_home"))
# Classify only known website directories; never print the raw FTP PWD.
path_labels = [
 ("pse_frontend", "pse.webnvn.com"),
 ("pse_wordpress", "admin-pse.webnvn.com"),
 ("eduresearch_frontend", "nghiencuukhoahoc.webnvn.com"),
 ("eduresearch_wordpress", "api-nghiencuukhoahoc.webnvn.com")
]
matches = [label for label, domain in path_labels if domain in pwd.lower()]
pwd_class = matches[0] if len(matches) == 1 else (
  "root_or_chroot" if pwd == "/" else "unidentified_account_home"
)
print("FTPS_AUDIT login_directory_class=" + pwd_class)
print("FTPS_AUDIT login_directory_is_public_html=" + ("yes" if "public_html" in pwd.lower() else "no"))
print("FTPS_AUDIT hmac_key_present=" + ("yes" if key else "no"))
print("FTPS_AUDIT hmac_key_ref=" + ref("shared-key-equivalence-check-v1"))
print("FTPS_AUDIT endpoint_ref=" + ref(url.hostname.lower() + ":" + str(port)))
print("FTPS_AUDIT account_ref=" + ref(url.hostname.lower() + ":" + str(port) + "|" + username))

ok,listing = lftp("cls -1")
if not ok:
    print("FTPS_AUDIT root_list=failed_or_blocked")
else:
    entries = {v.rstrip("/").split("/")[-1] for v in listing.splitlines()}
    labels = ("domains", "public_html", "private_html", "wp-admin", "wp-content",
              "wp-includes", "index.php", "index.html", "cgi-bin", "assets",
              "pse.webnvn.com", "admin-pse.webnvn.com",
              "nghiencuukhoahoc.webnvn.com", "api-nghiencuukhoahoc.webnvn.com")
    print("FTPS_AUDIT root_list=PASS")
    print("FTPS_AUDIT root_item_count=" + str(len(entries)))
    for item in labels:
        label = re.sub(r"[^A-Za-z0-9]+", "_", item).strip("_")
        print("FTPS_ROOT " + label + "=" + ("present" if item in entries else "absent"))
# Read-only directory checks. A failed CWD can mean chroot/path remapping.
candidates = [
 ("dot", "."),
 ("parent", ".."),
 ("slash", "/"),
 ("public_html", "public_html"),
 ("domains", "domains"),
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
 ("parent_nckh_api", "../domains/api-nghiencuukhoahoc.webnvn.com/public_html")
]
for label,target in candidates:
    ok,_ = lftp("cd " + target + "; pwd")
    print("FTPS_CWD " + label + "=" + ("yes" if ok else "no_or_unverified"))
print("FTPS_AUDIT remote_changes=NONE")

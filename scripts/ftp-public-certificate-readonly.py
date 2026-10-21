#!/usr/bin/env python3
"""Inspect certificate metadata on FTPS server and verify a matching DNS name.

The first TLS inspection disables hostname *matching only*, retains CA chain
verification, and sends NO FTP credentials. An optional candidate authentication
is done in a brand new session with strict hostname+CA verification only when
the certificate DNS name resolves to the same IP as the configured endpoint.
No remote file data is read or modified.
"""
import ftplib
import os
import socket
import ssl
import re
import subprocess
from urllib.parse import urlsplit

value=os.getenv("FTP_SERVER","").strip()
if not value: raise SystemExit("FTPS_CERT server_secret_missing")
if "://" not in value: value="ftp://"+value
u=urlsplit(value)
if u.scheme!="ftp" or not u.hostname or u.username or u.password or u.path.strip("/"):
    raise SystemExit("FTPS_CERT invalid_endpoint_format")
host=u.hostname
port=u.port or 21

def ips(h):
    try:
        return {x[4][0] for x in socket.getaddrinfo(h,port,type=socket.SOCK_STREAM)}
    except (socket.gaierror,OSError): return set()

ctx=ssl.create_default_context()
ctx.check_hostname=False # only certificate metadata inspection; no credentials
f=ftplib.FTP_TLS(context=ctx,timeout=12)
try:
    f.connect(host,port,timeout=12)
    f.auth()
    cert=f.sock.getpeercert()
    names=[name.lower() for kind,name in cert.get("subjectAltName",[]) if kind=="DNS"]
    print("FTPS_CERT trusted_ca_chain=yes")
    print("FTPS_CERT dns_san_count="+str(len(names)))
    print("FTPS_CERT dns_san_public=" + (",".join(names[:8]) if names else "none"))
except ssl.SSLError as ex:
    print("FTPS_CERT trusted_ca_chain=no class="+type(ex).__name__)
    raise SystemExit(1)
except (OSError,ftplib.Error) as ex:
    print("FTPS_CERT python_inspection_failed_class="+type(ex).__name__)
    # OpenSSL certificate-only fallback: no FTP account or password is transmitted.
    try:
        p=subprocess.run(
            ["openssl","s_client","-starttls","ftp","-connect",host+":"+str(port),
             "-servername",host,"-showcerts"],
            input="\n",capture_output=True,text=True,timeout=17,check=False
        )
        pem=re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",p.stdout,re.S)
        if not pem:
            print("FTPS_CERT openssl_metadata=unavailable")
        else:
            cert_info=subprocess.run(
                ["openssl","x509","-noout","-ext","subjectAltName"],
                input=pem.group(0),capture_output=True,text=True,timeout=6
            )
            sans=re.findall(r"DNS:([^,\s]+)",cert_info.stdout)
            print("FTPS_CERT openssl_metadata=certificate_received")
            print("FTPS_CERT openssl_dns_san_public="+(",".join(sans[:6]) if sans else "none"))
            # This fallback is metadata only, not proof of identity or login.
            print("FTPS_CERT strict_login=NOT_ATTEMPTED")
    except (OSError,subprocess.TimeoutExpired):
        print("FTPS_CERT openssl_metadata=timeout_or_unavailable")
    raise SystemExit(1)
finally:
    try: f.close()
    except Exception: pass

source_ips=ips(host)
candidate=""
for domain in names:
    if domain.startswith("*."): continue
    resolved=ips(domain)
    if source_ips and resolved and source_ips.intersection(resolved):
        candidate=domain
        break
print("FTPS_CERT matching_dns_endpoint=" + ("found" if candidate else "none"))
if not candidate:
    print("FTPS_CERT strict_login=NOT_ATTEMPTED")
    raise SystemExit(0)

# Domain name is public certificate metadata. Do not print username or raw host secret.
print("FTPS_CERT matching_hostname="+candidate)
user=os.getenv("FTP_USERNAME","")
password=os.getenv("FTP_PASSWORD","")
if not user or not password:
    print("FTPS_CERT strict_login=credentials_missing")
    raise SystemExit(1)
secure=ftplib.FTP_TLS(context=ssl.create_default_context(),timeout=12)
try:
    secure.connect(candidate,port,timeout=12)
    secure.auth()
    secure.login(user,password)
    secure.prot_p()
    response=secure.sendcmd("PWD")
    print("FTPS_CERT strict_login=PASS")
    print("FTPS_CERT authenticated_pwd=" + ("yes" if response.startswith("257") else "no"))
    path=response.lower()
    label="unknown_account_home"
    for name,part in (("pse_frontend","pse.webnvn.com"),
                      ("pse_wordpress","admin-pse.webnvn.com"),
                      ("eduresearch_frontend","nghiencuukhoahoc.webnvn.com"),
                      ("eduresearch_wordpress","api-nghiencuukhoahoc.webnvn.com")):
        if part in path:
            label=name
            break
    print("FTPS_CERT logged_in_directory_class="+label)
    root=secure.pwd()
    parts=[part for part in root.split("/") if part]
    print("FTPS_SCOPE login_directory_depth="+str(len(parts)))
    print("FTPS_SCOPE login_directory_public_html=" + ("yes" if parts and parts[-1].lower()=="public_html" else "no"))
    # Read only: listing names are kept in the runner and never printed raw.
    try:
        names=secure.nlst()
        entries={v.rstrip("/").split("/")[-1] for v in names}
        print("FTPS_SCOPE root_list=PASS count="+str(len(entries)))
        for token in ("domains","public_html","wp-admin","wp-content","index.html","index.php",
                      "pse.webnvn.com","admin-pse.webnvn.com",
                      "nghiencuukhoahoc.webnvn.com","api-nghiencuukhoahoc.webnvn.com"):
            label_name=token.replace(".","_").replace("-","_")
            print("FTPS_SCOPE root_"+label_name+"="+("present" if token in entries else "absent"))
    except Exception as ex:
        print("FTPS_SCOPE root_list=blocked_or_unavailable class="+type(ex).__name__)
    paths=(
        ("pse_frontend_abs","/domains/pse.webnvn.com/public_html"),
        ("pse_wp_abs","/domains/admin-pse.webnvn.com/public_html"),
        ("eduresearch_frontend_abs","/domains/nghiencuukhoahoc.webnvn.com/public_html"),
        ("eduresearch_wp_abs","/domains/api-nghiencuukhoahoc.webnvn.com/public_html"),
        ("public_html_relative","public_html"),
        ("domains_relative","domains"),
        ("pse_frontend_relative","domains/pse.webnvn.com/public_html"),
        ("pse_wp_relative","domains/admin-pse.webnvn.com/public_html"),
        ("eduresearch_frontend_relative","domains/nghiencuukhoahoc.webnvn.com/public_html"),
        ("eduresearch_wp_relative","domains/api-nghiencuukhoahoc.webnvn.com/public_html")
    )
    for name,target in paths:
        try:
            secure.cwd(root)
            secure.cwd(target)
            print("FTPS_SCOPE cwd_"+name+"=yes")
        except Exception:
            print("FTPS_SCOPE cwd_"+name+"=no_or_unverified")
    print("FTPS_CERT remote_changes=NONE")
except Exception as ex:
    print("FTPS_CERT strict_login=FAILED class="+type(ex).__name__)
    raise SystemExit(1)
finally:
    try:secure.close()
    except Exception:pass

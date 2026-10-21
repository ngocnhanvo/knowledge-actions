#!/usr/bin/env python3
"""Safe FTPS server TLS diagnostics. No credentials are printed and no writes occur."""
import ftplib
import os
import ssl
from urllib.parse import urlsplit

raw=os.getenv("FTP_SERVER","").strip()
if not raw: raise SystemExit("FTPS_TLS_CHECK server_secret_missing")
if "://" not in raw: raw="ftp://"+raw
u=urlsplit(raw)
if u.scheme!="ftp" or not u.hostname or u.username or u.password or u.path.strip("/"):
    raise SystemExit("FTPS_TLS_CHECK invalid_ftp_server")
context=ssl.create_default_context()
ftp=ftplib.FTP_TLS(context=context,timeout=13)
try:
    ftp.connect(u.hostname,u.port or 21,timeout=13)
    print("FTPS_TLS_CHECK control_socket=connected")
    try:
        ftp.auth()
    except ssl.SSLCertVerificationError as e:
        msg=(getattr(e,"verify_message","") or "").lower()
        if "hostname" in msg or "ip address mismatch" in msg:
            reason="hostname_mismatch"
        elif "self-signed" in msg:
            reason="self_signed"
        elif "issuer" in msg or "local issuer" in msg or "unable to get" in msg:
            reason="unknown_ca"
        elif "expired" in msg:
            reason="expired_certificate"
        else: reason="other_untrusted_certificate"
        print("FTPS_TLS_CHECK verified=no reason="+reason)
        raise SystemExit(2)
    print("FTPS_TLS_CHECK verified=yes")
    ftp.login(os.environ.get("FTP_USERNAME",""),os.environ.get("FTP_PASSWORD",""))
    ftp.prot_p()
    print("FTPS_TLS_CHECK authenticated=yes")
    reply=ftp.sendcmd("PWD")
    print("FTPS_TLS_CHECK ftp_pwd_response_valid=" + ("yes" if reply.startswith("257") else "no"))
except (TimeoutError,ConnectionError,OSError,ftplib.Error) as e:
    print("FTPS_TLS_CHECK connection_or_login_failed_class="+type(e).__name__)
    raise SystemExit(1)
finally:
    try: ftp.quit()
    except Exception:
        try: ftp.close()
        except Exception: pass

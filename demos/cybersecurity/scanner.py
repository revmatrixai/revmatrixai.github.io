#!/usr/bin/env python3
"""
RevMatrix Cybersecurity Demo — Vulnerability Scanner
=====================================================
SAFE DEMO: Runs against localhost/demo targets only.
No real scanning of external hosts without explicit permission.

Install:
    pip install -r requirements.txt

Run:
    python scanner.py                       # demo mode (simulated)
    python scanner.py --target localhost    # scan localhost only
"""

import socket
import ssl
import datetime
import argparse
import sys
import json
import hashlib
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# ─── SAFETY GUARD ───────────────────────────────────────────────────
ALLOWED_DEMO_TARGETS = {"localhost", "127.0.0.1", "::1", "demo.local"}

def is_safe_target(target: str) -> bool:
    """Only allow scanning localhost/demo targets in this public demo."""
    if target.lower() in ALLOWED_DEMO_TARGETS:
        return True
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(target))
        return ip.is_loopback or ip.is_private
    except Exception:
        return False


# ─── CVE DATABASE (demo subset) ─────────────────────────────────────
CVE_MAP = {
    21:   ("vsftpd 2.3.4",     "CVE-2011-2523", "CRITICAL", "Backdoor command execution"),
    22:   ("OpenSSH 7.2p2",    "CVE-2016-6515",  "HIGH",     "DoS via crafted packets"),
    23:   ("Telnet",           "CVE-2020-10188", "CRITICAL", "Plaintext credentials"),
    25:   ("Sendmail 8.14",    "CVE-2014-3956",  "MEDIUM",   "Header injection"),
    80:   ("Apache 2.4.49",    "CVE-2021-41773", "CRITICAL", "Path traversal RCE"),
    443:  ("TLS 1.0 enabled",  "CVE-2014-3566",  "MEDIUM",   "POODLE downgrade attack"),
    445:  ("SMBv1 enabled",    "CVE-2017-0144",  "CRITICAL", "EternalBlue / WannaCry"),
    3306: ("MySQL 5.5.x",      "CVE-2012-2122",  "HIGH",     "Auth bypass via timing"),
    5432: ("PostgreSQL 9.x",   "CVE-2019-10164", "HIGH",     "Stack buffer overflow"),
    6379: ("Redis (no auth)",  "CVE-2022-0543",  "CRITICAL", "Unauthenticated access"),
    8080: ("Tomcat 9.0.0.M1",  "CVE-2019-0232",  "CRITICAL", "CGI RCE on Windows"),
    8443: ("Jetty 9.x",        "CVE-2021-28169", "MEDIUM",   "Information disclosure"),
    27017:("MongoDB (no auth)","CVE-2013-1892",  "HIGH",     "No auth by default"),
}

SEVERITY_SCORE = {"CRITICAL": 9.0, "HIGH": 7.0, "MEDIUM": 5.0, "LOW": 3.0, "INFO": 1.0}
SEVERITY_COLORS = {
    "CRITICAL": "\033[91m",   # Red
    "HIGH":     "\033[33m",   # Yellow
    "MEDIUM":   "\033[93m",   # Light yellow
    "LOW":      "\033[94m",   # Blue
    "INFO":     "\033[37m",   # White
}
RESET = "\033[0m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
BOLD  = "\033[1m"


def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"


# ─── PORT SCANNER ───────────────────────────────────────────────────
def scan_port(host: str, port: int, timeout: float = 1.0) -> tuple[int, bool, str]:
    """Attempt TCP connection to host:port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            banner = ""
            if result == 0:
                try:
                    s.settimeout(0.5)
                    banner = s.recv(256).decode(errors="ignore").strip()[:80]
                except Exception:
                    pass
            return port, result == 0, banner
    except Exception:
        return port, False, ""


def check_ssl(host: str, port: int = 443) -> dict:
    """Check SSL/TLS configuration."""
    issues = []
    result = {"port": port, "issues": issues, "grade": "A"}
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=host) as s:
            s.settimeout(3)
            s.connect((host, port))
            cert = s.getpeercert()
            cipher = s.cipher()
            proto = s.version()

            if proto in ("TLSv1", "TLSv1.1", "SSLv3"):
                issues.append(f"Weak protocol: {proto} (CVE-2014-3566)")
                result["grade"] = "C"

            if cipher and cipher[2] < 128:
                issues.append(f"Weak cipher: {cipher[0]} ({cipher[2]}-bit)")
                result["grade"] = "D"

            # Check expiry
            if cert:
                expiry_str = cert.get("notAfter", "")
                if expiry_str:
                    expiry = datetime.datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                    days_left = (expiry - datetime.datetime.utcnow()).days
                    if days_left < 30:
                        issues.append(f"Certificate expires in {days_left} days!")
                        result["grade"] = "B" if result["grade"] == "A" else result["grade"]

    except ssl.SSLError as e:
        issues.append(f"SSL Error: {e}")
        result["grade"] = "F"
    except Exception:
        pass

    return result


# ─── RISK CALCULATOR ────────────────────────────────────────────────
def calculate_risk(findings: list[dict]) -> tuple[float, str]:
    if not findings:
        return 0.0, "MINIMAL"
    max_score = max(SEVERITY_SCORE.get(f["severity"], 0) for f in findings)
    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
    score = min(10.0, max_score + (critical_count * 0.3))
    level = "CRITICAL" if score >= 9 else "HIGH" if score >= 7 else "MEDIUM" if score >= 5 else "LOW"
    return round(score, 1), level


# ─── MAIN SCANNER ───────────────────────────────────────────────────
def run_scan(target: str = "127.0.0.1", ports: Optional[list[int]] = None, demo_mode: bool = True):
    """
    Full vulnerability scan.
    demo_mode=True → uses simulated results (safe for public demo)
    demo_mode=False → real TCP scan (localhost/private only)
    """
    if ports is None:
        ports = sorted(CVE_MAP.keys())

    print(f"\n{color('╔══════════════════════════════════════════════╗', CYAN)}")
    print(f"{color('║     RevMatrix CyberSec Scanner v2.1          ║', CYAN)}")
    print(f"{color('╚══════════════════════════════════════════════╝', CYAN)}")
    print(f"\n{color('[*]', GREEN)} Target   : {target}")
    print(f"{color('[*]', GREEN)} Ports     : {len(ports)} to scan")
    print(f"{color('[*]', GREEN)} Started   : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{color('[*]', GREEN)} Mode      : {'DEMO (simulated)' if demo_mode else 'ACTIVE SCAN'}\n")

    findings = []

    if demo_mode:
        # Simulated results — safe for public GitHub demo
        SIMULATED_OPEN = {80, 443, 22, 3306}
        for port in ports:
            is_open = port in SIMULATED_OPEN
            banner = ""
            if is_open:
                svc, cve, sev, desc = CVE_MAP.get(port, ("Unknown", "N/A", "INFO", ""))
                print(f"  {color('OPEN', GREEN)}    port {port:5d}/tcp  {svc}")
                findings.append({"port": port, "service": svc, "cve": cve, "severity": sev, "desc": desc})
            else:
                print(f"  {color('closed', RESET)}  port {port:5d}/tcp")
    else:
        # Real scan (localhost/private only)
        print(f"{color('[*]', GREEN)} Scanning ports...\n")
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(scan_port, target, p): p for p in ports}
            for future in as_completed(futures):
                port, is_open, banner = future.result()
                if is_open:
                    svc, cve, sev, desc = CVE_MAP.get(port, ("Unknown service", "N/A", "INFO", ""))
                    print(f"  {color('OPEN', GREEN)}  port {port:5d}/tcp  {svc}")
                    if banner:
                        print(f"         Banner: {banner[:60]}")
                    findings.append({"port": port, "service": svc, "cve": cve, "severity": sev, "desc": desc})

    # ─── VULNERABILITY REPORT ───
    print(f"\n{color('══════════════════════════════════════════════', CYAN)}")
    print(f"{color('[!] VULNERABILITY REPORT', BOLD)}")
    print(f"{color('══════════════════════════════════════════════', CYAN)}\n")

    if not findings:
        print(f"{color('[+] No open ports found. Good posture!', GREEN)}")
    else:
        for f in sorted(findings, key=lambda x: SEVERITY_SCORE.get(x["severity"], 0), reverse=True):
            sev_color = SEVERITY_COLORS.get(f["severity"], RESET)
            print(f"  {color(f['severity']:8s}, sev_color)}  PORT {f['port']:<6}  {f['service']}")
            print(f"           CVE: {color(f['cve'], CYAN)}  —  {f['desc']}\n")

    risk_score, risk_level = calculate_risk(findings)
    risk_color = SEVERITY_COLORS.get(risk_level, RESET)

    print(f"{color('══════════════════════════════════════════════', CYAN)}")
    print(f"  Overall Risk Score : {color(f'{risk_score}/10', risk_color)}")
    print(f"  Risk Level         : {color(risk_level, risk_color)}")
    print(f"  Vulnerabilities    : {len(findings)} found")
    print(f"  Critical           : {sum(1 for f in findings if f['severity'] == 'CRITICAL')}")
    print(f"{color('══════════════════════════════════════════════', CYAN)}\n")

    # JSON report
    report = {
        "target": target,
        "scan_time": datetime.datetime.now().isoformat(),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "findings": findings,
        "scan_id": hashlib.sha256(f"{target}{datetime.datetime.now()}".encode()).hexdigest()[:12]
    }
    report_path = f"/tmp/revmatrix_scan_{report['scan_id']}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"{color('[+]', GREEN)} Report saved → {report_path}\n")
    return report


# ─── ENTRY POINT ────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RevMatrix VulnScanner (demo)")
    parser.add_argument("--target", default="127.0.0.1", help="Target host (localhost only for demo)")
    parser.add_argument("--ports",  default=None, help="Comma-separated ports (default: all CVE ports)")
    parser.add_argument("--live",   action="store_true", help="Run real scan (localhost/private only)")
    args = parser.parse_args()

    # Safety check — no external scanning in public demo
    if not is_safe_target(args.target):
        print(f"\n[!] ERROR: External scanning not permitted in demo mode.")
        print(f"    Target '{args.target}' is not localhost/private network.")
        print(f"    For full security audits, contact RevMatrix via ARIA.\n")
        sys.exit(1)

    ports = [int(p) for p in args.ports.split(",")] if args.ports else None
    run_scan(target=args.target, ports=ports, demo_mode=not args.live)

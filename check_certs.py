#!/usr/bin/env python3
"""
Scan a folder for X.509 certificates, detect duplicates, and report them
with ASCII-box summaries.

Supports:
- PEM files (multiple "BEGIN CERTIFICATE" blocks per file)
- Bare DER files (.der, .cer, .crt without PEM headers)

Duplicates are grouped by SHA-256 fingerprint across all files.

Usage:
    python cert_dupe_report.py /path/to/folder
"""

from __future__ import annotations

import argparse
import base64
import binascii
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import ExtensionOID, NameOID


PEM_BLOCK_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----\s+?(.+?)\s+?-----END CERTIFICATE-----",
    re.DOTALL,
)


@dataclass(frozen=True)
class Location:
    path: Path
    index_in_file: int  # 1-based index of the cert within that file


@dataclass
class CertInfo:
    der_bytes: bytes
    fingerprint_sha256: str
    subject_cn: Optional[str]
    subject_org: Optional[str]
    subject_ou: Optional[str]
    issuer_cn: Optional[str]
    serial_hex: str
    not_before: datetime
    not_after: datetime
    emails: List[str]
    sans_dns: List[str]
    locations: List[Location]


def draw_box(lines: List[str], max_width: int = 100) -> str:
    """
    Create a simple ASCII box around the list of lines.
    Lines are wrapped politely to max_width if needed.
    """
    wrapped: List[str] = []
    for line in lines:
        if len(line) <= max_width:
            wrapped.append(line)
            continue
        # naive wrap on spaces
        current = []
        for word in line.split(" "):
            if sum(len(w) for w in current) + len(current) + len(word) > max_width:
                wrapped.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            wrapped.append(" ".join(current))

    width = min(
        max((len(s) for s in wrapped), default=0),
        max_width,
    )
    top = "+" + "-" * (width + 2) + "+"
    body = "\n".join(f"| {s.ljust(width)} |" for s in wrapped)
    bottom = "+" + "-" * (width + 2) + "+"
    return f"{top}\n{body}\n{bottom}" if wrapped else f"{top}\n{bottom}"


def safe_get_attr(name: x509.Name, oid: x509.ObjectIdentifier) -> Optional[str]:
    try:
        attrs = name.get_attributes_for_oid(oid)
        return attrs[0].value if attrs else None
    except Exception:
        return None


def extract_san_emails_and_dns(
    cert: x509.Certificate,
) -> Tuple[List[str], List[str]]:
    emails: List[str] = []
    dns_names: List[str] = []
    try:
        san = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        ).value
        emails = san.get_values_for_type(x509.RFC822Name)
        dns_names = san.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        pass
    return emails, dns_names


def load_der_candidates_from_pem_text(text: str) -> List[bytes]:
    ders: List[bytes] = []
    for idx, match in enumerate(PEM_BLOCK_RE.finditer(text), start=1):
        b64 = match.group(1).strip()
        try:
            ders.append(base64.b64decode(b64))
        except binascii.Error:
            # Skip malformed block
            continue
    return ders


def try_load_single_der(blob: bytes) -> Optional[bytes]:
    """
    Try to parse a single DER certificate from bytes.
    Returns the same bytes if successfully parsed as DER, else None.
    """
    try:
        x509.load_der_x509_certificate(blob)
        return blob
    except Exception:
        return None


def parse_cert_from_der(
    der: bytes, loc: Location
) -> Optional[CertInfo]:
    try:
        cert = x509.load_der_x509_certificate(der)
    except Exception:
        return None

    fp = cert.fingerprint(hashes.SHA256()).hex().upper()
    subj = cert.subject
    issuer = cert.issuer

    subject_cn = safe_get_attr(subj, NameOID.COMMON_NAME)
    subject_org = safe_get_attr(subj, NameOID.ORGANIZATION_NAME)
    subject_ou = safe_get_attr(subj, NameOID.ORGANIZATIONAL_UNIT_NAME)
    issuer_cn = safe_get_attr(issuer, NameOID.COMMON_NAME)

    emails, sans_dns = extract_san_emails_and_dns(cert)

    info = CertInfo(
        der_bytes=der,
        fingerprint_sha256=fp,
        subject_cn=subject_cn,
        subject_org=subject_org,
        subject_ou=subject_ou,
        issuer_cn=issuer_cn,
        serial_hex=format(cert.serial_number, "x").upper(),
        not_before=cert.not_valid_before,
        not_after=cert.not_valid_after,
        emails=emails,
        sans_dns=sans_dns,
        locations=[loc],
    )
    return info


def gather_cert_infos(root: Path) -> Tuple[List[CertInfo], Dict[Path, int]]:
    """
    Walk the tree from root, parse certificates from files.
    Returns list of CertInfo and a per-file count of certs found.
    """
    certs: List[CertInfo] = []
    per_file_count: Dict[Path, int] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        # First, look for PEM blocks inside as text
        ders: List[bytes] = []
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""

        pem_ders = load_der_candidates_from_pem_text(text)
        if pem_ders:
            ders.extend(pem_ders)
        else:
            # If no PEM blocks, try entire file as DER
            try:
                blob = path.read_bytes()
            except Exception:
                continue
            der_one = try_load_single_der(blob)
            if der_one is not None:
                ders.append(der_one)

        if not ders:
            continue

        per_file_count[path] = len(ders)
        for i, der in enumerate(ders, start=1):
            loc = Location(path=path, index_in_file=i)
            info = parse_cert_from_der(der, loc)
            if info:
                certs.append(info)

    return certs, per_file_count


def merge_by_fingerprint(certs: Iterable[CertInfo]) -> Dict[str, CertInfo]:
    """
    Merge CertInfo entries that share the same SHA-256 fingerprint.
    Locations are concatenated.
    """
    merged: Dict[str, CertInfo] = {}
    for c in certs:
        key = c.fingerprint_sha256
        if key not in merged:
            merged[key] = c
        else:
            merged[key].locations.extend(c.locations)
    return merged


def human_identity_line(c: CertInfo) -> str:
    bits = []
    if c.subject_cn:
        bits.append(f"CN={c.subject_cn}")
    if c.subject_org:
        bits.append(f"O={c.subject_org}")
    if c.subject_ou:
        bits.append(f"OU={c.subject_ou}")
    if c.emails:
        bits.append("Emails=" + ", ".join(c.emails))
    if c.sans_dns:
        bits.append("DNS=" + ", ".join(c.sans_dns))
    return ", ".join(bits) if bits else "(no subject identity fields)"


def render_group_box(c: CertInfo) -> str:
    lines: List[str] = []
    lines.append(f"SHA256: {c.fingerprint_sha256}")
    lines.append(f"Serial: {c.serial_hex}")
    
    # Check if certificate is expired
    now = datetime.now()
    is_expired = c.not_after < now
    
    validity_line = (
        "Validity: "
        f"{c.not_before.isoformat()} to {c.not_after.isoformat()}"
    )
    
    if is_expired:
        validity_line += " *** EXPIRED ***"
        lines.append(validity_line)
        lines.append("⚠️  WARNING: This certificate has EXPIRED!")
    else:
        lines.append(validity_line)
    
    lines.append(f"Issuer CN: {c.issuer_cn or '(unknown)'}")
    lines.append(f"Subject: {human_identity_line(c)}")
    lines.append("Found in:")
    for loc in c.locations:
        lines.append(f"  - {loc.path} [index {loc.index_in_file}]")
    return draw_box(lines)


def print_report(
    merged: Dict[str, CertInfo],
    per_file_count: Dict[Path, int],
    show_unique: bool,
    list_files_with_multiple: bool,
) -> int:
    total_certs = sum(per_file_count.values())
    dupes = [c for c in merged.values() if len(c.locations) > 1]
    uniques = [c for c in merged.values() if len(c.locations) == 1]

    if dupes:
        print("\n=== Duplicate certificates (by SHA-256) ===\n")
        for c in sorted(
            dupes,
            key=lambda x: (len(x.locations), x.subject_cn or "", x.serial_hex),
            reverse=True,
        ):
            print(render_group_box(c))
            print()
    else:
        print("\nNo duplicates found.\n")

    if show_unique and uniques:
        print("=== Unique certificates ===\n")
        for c in sorted(uniques, key=lambda x: x.subject_cn or x.serial_hex):
            print(render_group_box(c))
            print()

    if list_files_with_multiple:
        multi_files = {
            p: n for p, n in per_file_count.items() if n > 1
        }
        if multi_files:
            print("=== Files containing multiple certificates ===\n")
            for p, n in sorted(multi_files.items()):
                box = draw_box(
                    [f"{p}", f"Certificates in file: {n}"],
                )
                print(box)
                print()

    print("=== Summary ===")
    print(f"Files scanned: {len(per_file_count)}")
    print(f"Certificates parsed: {total_certs}")
    print(f"Unique fingerprints: {len(merged)}")
    print(f"Duplicate groups: {len(dupes)}")

    # Exit status: 0 if no dupes, 1 if dupes found
    return 1 if dupes else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find duplicate X.509 certificates in a folder."
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Root folder to scan recursively.",
    )
    parser.add_argument(
        "--show-unique",
        action="store_true",
        help="Also print ASCII boxes for unique certificates.",
    )
    parser.add_argument(
        "--files-with-multiple",
        action="store_true",
        help="List files that contain more than one certificate.",
    )
    args = parser.parse_args()

    root = args.folder
    if not root.exists() or not root.is_dir():
        print(f"Error: folder does not exist or is not a directory: {root}")
        sys.exit(2)

    certs, per_file_count = gather_cert_infos(root)
    if not certs:
        print("No certificates found.")
        sys.exit(0)

    merged = merge_by_fingerprint(certs)
    exit_code = print_report(
        merged=merged,
        per_file_count=per_file_count,
        show_unique=args.show_unique,
        list_files_with_multiple=args.files_with_multiple,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

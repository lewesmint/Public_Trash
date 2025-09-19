#!/usr/bin/env python3
import argparse, sys, re, base64, textwrap, datetime
from typing import List, Tuple, Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, ec, dsa
from cryptography.hazmat.primitives.serialization import pkcs12
try:
    # Available in cryptography 36+
    from cryptography.hazmat.primitives.serialization import pkcs7
    HAVE_PKCS7 = True
except Exception:
    HAVE_PKCS7 = False

def b(s): return s if isinstance(s, bytes) else s.encode("utf-8")

PEM_BEGIN_RE = re.compile(rb"-----BEGIN ([A-Z0-9 ]+)-----")
PEM_END_RE   = re.compile(rb"-----END ([A-Z0-9 ]+)-----")

def is_pem(data: bytes) -> bool:
    return data.strip().startswith(b"-----BEGIN")

def split_pem_blocks(data: bytes) -> List[Tuple[str, bytes]]:
    """Return list of (label, block_bytes including BEGIN/END)."""
    blocks = []
    pos = 0
    while True:
        m = PEM_BEGIN_RE.search(data, pos)
        if not m:
            break
        label = m.group(1).decode("ascii", "replace")
        m_end = PEM_END_RE.search(data, m.end())
        if not m_end:
            break
        end_label = m_end.group(1).decode("ascii", "replace")
        if end_label != label:
            # mismatched labels, but still try to consume
            pass
        block = data[m.start():m_end.end()]
        blocks.append((label, block))
        pos = m_end.end()
    return blocks

def fmt_dt(dt: datetime.datetime) -> str:
    if not isinstance(dt, datetime.datetime):
        return str(dt)
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z") or dt.isoformat()

def print_header(title: str):
    print("\n" + title)
    print("=" * len(title))

def indent(s: str, n: int = 2) -> str:
    pad = " " * n
    return "\n".join(pad + line for line in s.splitlines())

def name_to_str(name: x509.Name) -> str:
    return ", ".join(f"{attr.oid._name}={attr.value}" for attr in name)

def sig_algo_str(cert: x509.Certificate) -> str:
    try:
        return cert.signature_hash_algorithm.name
    except Exception:
        return "unknown"

def san_to_str(cert: x509.Certificate) -> Optional[str]:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        names = []
        for gn in san:
            if isinstance(gn, x509.DNSName):
                names.append(f"DNS:{gn.value}")
            elif isinstance(gn, x509.IPAddress):
                names.append(f"IP:{gn.value}")
            elif isinstance(gn, x509.UniformResourceIdentifier):
                names.append(f"URI:{gn.value}")
            elif isinstance(gn, x509.RFC822Name):
                names.append(f"EMAIL:{gn.value}")
            else:
                names.append(str(gn))
        return ", ".join(names) if names else None
    except x509.ExtensionNotFound:
        return None

def key_usage_str(cert: x509.Certificate) -> Optional[str]:
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        bits = []
        for field in ("digital_signature","content_commitment","key_encipherment",
                      "data_encipherment","key_agreement","key_cert_sign","crl_sign",
                      "encipher_only","decipher_only"):
            val = getattr(ku, field)
            if val:
                bits.append(field)
        return ", ".join(bits) if bits else None
    except x509.ExtensionNotFound:
        return None

def ext_key_usage_str(cert: x509.Certificate) -> Optional[str]:
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        return ", ".join(oid._name or oid.dotted_string for oid in eku)
    except x509.ExtensionNotFound:
        return None

def print_cert(cert: x509.Certificate, label: str = "Certificate", path: Optional[str] = None, index: Optional[int] = None):
    title = f"{label}"
    if index is not None:
        title += f" #{index}"
    if path:
        title += f" from {path}"
    print_header(title)
    print(f"Subject       : {name_to_str(cert.subject)}")
    print(f"Issuer        : {name_to_str(cert.issuer)}")
    print(f"Serial        : {hex(cert.serial_number)}")
    print(f"Valid From    : {fmt_dt(cert.not_valid_before)}")
    print(f"Valid To      : {fmt_dt(cert.not_valid_after)}")
    now = datetime.datetime.utcnow()
    status = "EXPIRED" if cert.not_valid_after.replace(tzinfo=None) < now else "valid"
    print(f"Status        : {status}")
    print(f"Sig Algorithm : {sig_algo_str(cert)}")
    san = san_to_str(cert)
    if san:
        print(f"SANs          : {san}")
    ku = key_usage_str(cert)
    if ku:
        print(f"Key Usage     : {ku}")
    eku = ext_key_usage_str(cert)
    if eku:
        print(f"Ext Key Usage : {eku}")
    try:
        aki = cert.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value
        skid = cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
        if aki.key_identifier:
            print(f"AKI           : {aki.key_identifier.hex()}")
        if skid.digest:
            print(f"SKID          : {skid.digest.hex()}")
    except Exception:
        pass
    print(f"Public Key    : ", end="")
    pub = cert.public_key()
    if isinstance(pub, rsa.RSAPublicKey):
        print(f"RSA {pub.key_size} bits")
    elif isinstance(pub, ec.EllipticCurvePublicKey):
        print(f"EC curve {pub.curve.name}")
    elif isinstance(pub, dsa.DSAPublicKey):
        print(f"DSA {pub.key_size} bits")
    else:
        print(type(pub).__name__)

def print_key(key, label="Private Key"):
    print_header(label)
    if isinstance(key, rsa.RSAPrivateKey):
        print(f"Type          : RSA")
        print(f"Size          : {key.key_size} bits")
    elif isinstance(key, ec.EllipticCurvePrivateKey):
        print(f"Type          : EC")
        print(f"Curve         : {key.curve.name}")
    elif isinstance(key, dsa.DSAPrivateKey):
        print(f"Type          : DSA")
        print(f"Size          : {key.key_size} bits")
    else:
        print(f"Type          : {type(key).__name__}")

def try_load_der_objects(data: bytes, path: str):
    loaded_any = False
    # Try DER certificate
    try:
        cert = x509.load_der_x509_certificate(data)
        print_cert(cert, path=path)
        loaded_any = True
    except Exception:
        pass
    # Try DER CRL
    try:
        crl = x509.load_der_x509_crl(data)
        print_header(f"CRL from {path}")
        print(f"Issuer        : {name_to_str(crl.issuer)}")
        print(f"Last Update   : {fmt_dt(crl.last_update)}")
        print(f"Next Update   : {fmt_dt(crl.next_update)}")
        print(f"Revoked count : {0 if crl.revoked_certificates is None else len(crl.revoked_certificates)}")
        loaded_any = True
    except Exception:
        pass
    # Try PKCS7
    if HAVE_PKCS7:
        try:
            certs = pkcs7.load_der_pkcs7_certificates(data)
            if certs:
                for i, c in enumerate(certs, 1):
                    print_cert(c, label="PKCS7 Certificate", path=path, index=i)
                loaded_any = True
        except Exception:
            pass
    # Try PKCS12
    try:
        key, cert, addl = pkcs12.load_key_and_certificates(data, password=None)
        if key:
            print_key(key, label=f"PKCS12 Private Key from {path}")
        if cert:
            print_cert(cert, label="PKCS12 Main Certificate", path=path)
        if addl:
            for i, c in enumerate(addl, 1):
                print_cert(c, label="PKCS12 Additional Certificate", path=path, index=i)
        loaded_any = True
    except Exception:
        # Try prompting for password if PFX is encrypted
        try:
            # Non-interactive default: check common empty passwords
            for pwd in (b"",):
                key, cert, addl = pkcs12.load_key_and_certificates(data, password=pwd)
                if key or cert or addl:
                    if key:
                        print_key(key, label=f"PKCS12 Private Key from {path} (password='')")
                    if cert:
                        print_cert(cert, label="PKCS12 Main Certificate", path=path)
                    if addl:
                        for i, c in enumerate(addl, 1):
                            print_cert(c, label="PKCS12 Additional Certificate", path=path, index=i)
                    loaded_any = True
                    break
        except Exception:
            pass
    return loaded_any

def try_load_pem_objects(blocks: List[Tuple[str, bytes]], path: str):
    loaded_any = False
    for label, block in blocks:
        payload = b"".join(line for line in block.splitlines(True))
        text_label = label.upper()
        if "CERTIFICATE" in text_label and "REQUEST" not in text_label:
            try:
                cert = x509.load_pem_x509_certificate(payload)
                print_cert(cert, path=path)
                loaded_any = True
                continue
            except Exception:
                pass
        if "CRL" in text_label:
            try:
                crl = x509.load_pem_x509_crl(payload)
                print_header(f"CRL from {path}")
                print(f"Issuer        : {name_to_str(crl.issuer)}")
                print(f"Last Update   : {fmt_dt(crl.last_update)}")
                print(f"Next Update   : {fmt_dt(crl.next_update)}")
                print(f"Revoked count : {0 if crl.revoked_certificates is None else len(crl.revoked_certificates)}")
                loaded_any = True
                continue
            except Exception:
                pass
        if "PRIVATE KEY" in text_label:
            # Try various private key loaders
            key = None
            for loader in (
                serialization.load_pem_private_key,
            ):
                try:
                    key = loader(payload, password=None)
                    break
                except Exception:
                    pass
            if key:
                print_key(key, label=f"{label.title()} from {path}")
                loaded_any = True
                continue
        if HAVE_PKCS7 and "PKCS7" in text_label:
            try:
                certs = pkcs7.load_pem_pkcs7_certificates(payload)
                if certs:
                    for i, c in enumerate(certs, 1):
                        print_cert(c, label="PKCS7 Certificate", path=path, index=i)
                    loaded_any = True
                    continue
            except Exception:
                pass
    return loaded_any

def main():
    ap = argparse.ArgumentParser(
        description="Inspect an X.509-related file and list all contained objects."
    )
    ap.add_argument("path", help="Input file: .crt .pem .der .cer .p7b .p7c .p12 .pfx")
    args = ap.parse_args()

    try:
        with open(args.path, "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading {args.path}: {e}", file=sys.stderr)
        sys.exit(2)

    loaded_any = False
    if is_pem(data):
        blocks = split_pem_blocks(data)
        if not blocks:
            print("No PEM blocks found")
        else:
            loaded_any |= try_load_pem_objects(blocks, args.path)
    else:
        loaded_any |= try_load_der_objects(data, args.path)

    if not loaded_any:
        print("No recognizable certificates, keys, CRLs, PKCS7 or PKCS12 objects found.")
        print("Tip: If this is a PKCS12/PFX with a password, edit the script to provide it.")

if __name__ == "__main__":
    main()

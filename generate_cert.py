import os
import subprocess
import shutil

def generate_cert():
    # Check if mkcert is installed
    mkcert_path = shutil.which("mkcert")
    
    if mkcert_path:
        print("Using mkcert to generate trusted certificates...")
        try:
            # Generate the certificates
            subprocess.run([
                "mkcert", 
                "-key-file", "key.pem", 
                "-cert-file", "cert.pem", 
                "localhost", "127.0.0.1", "::1"
            ], check=True)
            
            print("\n" + "="*50)
            print("SUCCESS: Certificates generated using mkcert.")
            print("IMPORTANT: To remove browser warnings on YOUR computer, you must:")
            print("1. Install mkcert on your LOCAL machine.")
            print("2. Copy the Root CA from the server or run 'mkcert -install' locally.")
            print("="*50 + "\n")
            return
        except subprocess.CalledProcessError as e:
            print(f"Error running mkcert: {e}")
            print("Falling back to self-signed certificates...")

    # Fallback to cryptography-based self-signed certs (untrusted by default)
    print("Generating self-signed certificates (will show browser warnings)...")
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime

        # Generate private key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Write private key
        with open("key.pem", "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        # Generate certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"IN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Maharashtra"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"Mumbai"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Aerodrome Warning System"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])

        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
            critical=False,
        ).sign(key, hashes.SHA256())

        # Write certificate
        with open("cert.pem", "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print("Successfully generated self-signed key.pem and cert.pem")
        
    except ImportError:
        print("Error: 'cryptography' library not found.")
        print("Please install it: pip install cryptography")

if __name__ == "__main__":
    generate_cert()

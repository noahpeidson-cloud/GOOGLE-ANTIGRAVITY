import io
import sys
import json
import socket
import qrcode
from config import AUTH_TOKEN, SERVER_PORT


def get_local_ip() -> str:
    """Discover the local network IP address of the server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually send data, but selects the active network interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_pairing_payload(ip: str | None = None, port: int | None = None, token: str | None = None) -> dict:
    """Construct standard pairing payload for mobile client."""
    resolved_ip = ip or get_local_ip()
    resolved_port = port or SERVER_PORT
    resolved_token = token or AUTH_TOKEN
    base_url = f"http://{resolved_ip}:{resolved_port}"
    return {
        "server_ip": resolved_ip,
        "port": resolved_port,
        "server_url": base_url,
        "auth_token": resolved_token,
        "upload_endpoint": f"{base_url}/api/upload",
    }


def generate_qr_image_bytes(payload_data: dict | str) -> bytes:
    """Generate PNG image bytes for QR code containing the pairing data."""
    if isinstance(payload_data, dict):
        qr_text = json.dumps(payload_data)
    else:
        qr_text = str(payload_data)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def print_pairing_cli():
    """Print connection info and terminal QR code safely across all OS consoles."""
    # Ensure stdout handles UTF-8 on Windows
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    payload = get_pairing_payload()
    print("=" * 60)
    print("BRAIN LINK - FASTAPI SERVER PAIRING")
    print("=" * 60)
    print(f"Local Server IP : {payload['server_ip']}")
    print(f"Port            : {payload['port']}")
    print(f"Upload Endpoint : {payload['upload_endpoint']}")
    print(f"Auth Token      : {payload['auth_token']}")
    print("=" * 60)
    print("Scan QR code below or visit /api/qr on the server:")
    print("=" * 60)

    try:
        qr = qrcode.QRCode()
        qr.add_data(json.dumps(payload))
        qr.print_ascii(invert=True)
    except Exception:
        # Fallback text representation if console doesn't support unicode blocks
        qr = qrcode.QRCode()
        qr.add_data(json.dumps(payload))
        qr.print_tty()
    print("=" * 60)


if __name__ == "__main__":
    print_pairing_cli()

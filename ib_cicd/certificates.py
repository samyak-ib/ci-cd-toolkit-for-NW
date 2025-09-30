import base64
import os
from functools import lru_cache
from typing import Dict, Optional


CERTIFICATE_HEADER_NAME = "IB-Certificate"
CERTIFICATE_ENV_VAR = "IB_CLIENT_CERT_PATH"
_DEFAULT_CERTIFICATE_PATH = os.path.join(
    os.path.dirname(__file__), "assets", "instabase_client_cert.pem"
)


@lru_cache(maxsize=1)
def load_instabase_certificate() -> Optional[str]:
    """Return the base64 encoded certificate string if available."""

    cert_path = os.environ.get(CERTIFICATE_ENV_VAR, _DEFAULT_CERTIFICATE_PATH)
    try:
        with open(cert_path, "rb") as cert_file:
            raw_data = cert_file.read().strip()
    except OSError:
        return None

    if not raw_data:
        return None

    return base64.b64encode(raw_data).decode("ascii")


def with_instabase_certificate(headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return headers dict ensuring the Instabase certificate header is attached."""

    updated_headers: Dict[str, str] = dict(headers or {})
    cert_value = load_instabase_certificate()
    if cert_value:
        updated_headers.setdefault(CERTIFICATE_HEADER_NAME, cert_value)
    return updated_headers


def clear_certificate_cache() -> None:
    """Helper for tests to clear the cached certificate value."""

    load_instabase_certificate.cache_clear()


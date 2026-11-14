"""Plivo Programmable Voice telephony service integration.

Provides a reusable Plivo client, V3 webhook signature validation,
XML response generation for bidirectional WebSocket streams, connection health checks,
and graceful fallback when credentials are not configured.
"""

import base64
import hashlib
import hmac
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse
import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_UNSET = object()


class PlivoConfigurationError(Exception):
    """Raised when an operation requires Plivo credentials, but they are missing."""


class PlivoService:
    """Reusable Plivo telephony client service with V3 signature validation and XML generation."""

    def __init__(
        self,
        auth_id: Any = _UNSET,
        auth_token: Any = _UNSET,
        phone_number: Any = _UNSET,
        public_base_url: Any = _UNSET,
    ) -> None:
        """Initialize Plivo service using explicit parameters or application settings."""
        self.auth_id: str | None = (
            settings.PLIVO_AUTH_ID if auth_id is _UNSET else auth_id
        )
        self.auth_token: str | None = (
            settings.PLIVO_AUTH_TOKEN if auth_token is _UNSET else auth_token
        )
        self.phone_number: str | None = (
            settings.PLIVO_PHONE_NUMBER if phone_number is _UNSET else phone_number
        )
        self.public_base_url: str | None = (
            settings.PUBLIC_BASE_URL if public_base_url is _UNSET else public_base_url
        )

        if self.is_configured:
            logger.info(
                "Plivo Service initialized with Auth ID: %s, Phone Number: %s",
                self.mask_auth_id(self.auth_id),
                self.phone_number,
            )
        else:
            logger.info("Plivo service initialized in unconfigured state.")

    @property
    def is_configured(self) -> bool:
        """Return True if required credentials (Auth ID, Auth Token) are present."""
        return bool(
            self.auth_id
            and self.auth_token
            and self.auth_id.strip()
            and self.auth_token.strip()
        )

    @staticmethod
    def mask_auth_id(auth_id: str | None) -> str | None:
        """Partially mask Auth ID for privacy compliance."""
        if not auth_id:
            return None
        s = auth_id.strip()
        if len(s) >= 8:
            return f"{s[:4]}...{s[-4:]}"
        return "****"

    @staticmethod
    def construct_v3_base_url(uri: str, method: str = "POST", params: dict[str, Any] | None = None) -> str:
        """Construct base URL string for Plivo V3 signature verification per official specification.

        Rules:
        - Scheme, netloc, and path from URI.
        - If query params exist, sort alphabetically by key and format as '?k1=v1&k2=v2'.
        - If POST method and body parameters exist:
          - If query string exists, append '.' delimiter.
          - If query string does not exist, append '?' delimiter.
          - Append sorted POST parameters alphabetically formatted as '{key}{value}'.
        """
        parsed = urlparse(uri)
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        query_dict = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_keys = sorted(query_dict.keys())
        query_str = "&".join(f"{k}={query_dict[k]}" for k in query_keys)

        has_post_params = bool(method.upper() == "POST" and params)
        if query_str or has_post_params:
            base_url += f"?{query_str}"
        if query_str and has_post_params:
            base_url += "."

        if has_post_params and params:
            def _format_param_str(p_dict: dict[str, Any]) -> str:
                res = []
                for k in sorted(p_dict.keys()):
                    v = p_dict[k]
                    if isinstance(v, list):
                        res.append("".join(f"{k}{val}" for val in sorted(str(x) for x in v)))
                    elif isinstance(v, dict):
                        res.append(f"{k}{_format_param_str(v)}")
                    else:
                        res.append(f"{k}{str(v)}")
                return "".join(res)

            base_url += _format_param_str(params)

        return base_url

    @classmethod
    def compute_v3_signature(
        cls,
        auth_token: str,
        uri: str,
        nonce: str,
        method: str = "POST",
        params: dict[str, Any] | None = None,
    ) -> str:
        """Compute expected Plivo V3 HMAC-SHA256 Base64 signature per official specification."""
        base_url = cls.construct_v3_base_url(uri, method=method, params=params)
        message = f"{base_url}.{nonce}"
        mac = hmac.new(
            auth_token.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(mac).decode("utf-8")

    def validate_v3_signature(
        self,
        uri: str,
        nonce: str | None,
        signature: str | None,
        method: str = "POST",
        params: dict[str, Any] | None = None,
        fallback_uris: list[str] | None = None,
    ) -> bool:
        """Validate Plivo X-Plivo-Signature-V3 HMAC-SHA256 signature against official Plivo spec.

        Algorithm:
        1. Construct base URL (scheme + netloc + path + sorted query params + sorted POST params).
        2. Append '.' delimiter followed by nonce ({base_url}.{nonce}).
        3. Compute HMAC-SHA256 with auth_token and encode output in Base64.
        4. Constant-time comparison with incoming comma-separated signatures.
        """
        if not self.auth_token:
            # If server has no auth token configured, allow in development/testing
            if settings.ENVIRONMENT in ("development", "test"):
                return True
            return False

        if not signature or not nonce:
            return False

        candidate_uris = [uri]
        if fallback_uris:
            candidate_uris.extend([u for u in fallback_uris if u and u not in candidate_uris])

        incoming_signatures = [s.strip() for s in signature.split(",") if s.strip()]

        for test_uri in candidate_uris:
            try:
                computed_signature = self.compute_v3_signature(
                    auth_token=self.auth_token,
                    uri=test_uri,
                    nonce=str(nonce),
                    method=method,
                    params=params,
                )

                for inc_sig in incoming_signatures:
                    if hmac.compare_digest(computed_signature, inc_sig):
                        return True

            except Exception as exc:
                logger.warning("Error calculating Plivo V3 signature for URI %s: %s", test_uri, exc)

        return False

    @staticmethod
    def build_stream_xml(
        stream_url: str,
        bidirectional: bool = True,
        keep_call_alive: bool = True,
        content_type: str = "audio/x-mulaw;rate=8000",
        audio_track: str | None = None,
        status_callback_url: str | None = None,
    ) -> str:
        """Generate Plivo XML connecting active call to a bidirectional WebSocket stream.
        
        Example Output:
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">wss://example.com/api/v1/plivo/stream?...</Stream>
        </Response>
        """
        bi_str = "true" if bidirectional else "false"
        keep_str = "true" if keep_call_alive else "false"
        clean_url = stream_url.strip()
        escaped_url = (
            clean_url.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        attrs = [
            f'bidirectional="{bi_str}"',
            f'keepCallAlive="{keep_str}"',
            f'contentType="{content_type}"',
        ]
        # In Plivo Voice XML, audioTrack is only valid for unidirectional (listen-only) streams
        if not bidirectional and audio_track:
            attrs.append(f'audioTrack="{audio_track}"')
        if status_callback_url:
            attrs.append(f'statusCallbackUrl="{status_callback_url}"')
            attrs.append('statusCallbackMethod="POST"')

        attr_str = " ".join(attrs)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f"    <Stream {attr_str}>{escaped_url}</Stream>\n"
            "</Response>"
        )

    @staticmethod
    def build_speak_xml(
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> str:
        """Generate Plivo XML to speak text using Plivo TTS."""
        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
        voice_attr = f' voice="{voice}"' if voice else ""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Speak language="{language}"{voice_attr}>{escaped}</Speak>\n'
            "</Response>"
        )

    @staticmethod
    def build_hangup_xml(reason: str | None = None) -> str:
        """Generate Plivo XML to terminate the call."""
        reason_attr = f' reason="{reason}"' if reason else ""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f"<Response>\n    <Hangup{reason_attr}/>\n</Response>"
        )

    @staticmethod
    def build_unknown_number_xml() -> str:
        """Generate rejection XML when dialed number is not mapped to any active tenant."""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            '    <Speak language="en-IN">Thank you for calling. This number is not associated with an active business organization. Goodbye.</Speak>\n'
            "    <Hangup/>\n"
            "</Response>"
        )

    def check_connection(self) -> dict[str, Any]:
        """Perform a read-only probe against Plivo API to verify credentials."""
        if not self.is_configured:
            return {
                "status": "unconfigured",
                "configured": False,
                "auth_id_masked": self.mask_auth_id(self.auth_id),
                "account_name": None,
                "phone_number": self.phone_number,
                "message": "Plivo credentials are not configured.",
            }

        url = f"https://api.plivo.com/v1/Account/{self.auth_id}/"
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(url, auth=(self.auth_id, self.auth_token))
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "status": "connected",
                        "configured": True,
                        "auth_id_masked": self.mask_auth_id(self.auth_id),
                        "account_name": data.get("name") or "Plivo Account",
                        "account_status": data.get("state") or "active",
                        "phone_number": self.phone_number,
                        "message": "Successfully authenticated with Plivo API.",
                    }
                elif res.status_code == 401:
                    return {
                        "status": "failed",
                        "configured": True,
                        "auth_id_masked": self.mask_auth_id(self.auth_id),
                        "phone_number": self.phone_number,
                        "message": "Plivo authentication failed: Invalid Auth ID or Auth Token.",
                    }
                else:
                    return {
                        "status": "failed",
                        "configured": True,
                        "auth_id_masked": self.mask_auth_id(self.auth_id),
                        "phone_number": self.phone_number,
                        "message": f"Plivo API returned HTTP {res.status_code}: {res.text[:100]}",
                    }
        except Exception as exc:
            logger.warning("Error checking Plivo connection: %s", exc)
            return {
                "status": "failed",
                "configured": True,
                "auth_id_masked": self.mask_auth_id(self.auth_id),
                "phone_number": self.phone_number,
                "message": f"Connection to Plivo API timed out or failed: {str(exc)}",
            }

    def initiate_outbound_call(
        self,
        from_number: str,
        to_number: str,
        answer_url: str,
        answer_method: str = "POST",
    ) -> dict[str, Any]:
        """Trigger an outbound call through Plivo's REST API."""
        if not self.is_configured:
            raise PlivoConfigurationError("Plivo service is not configured.")

        url = f"https://api.plivo.com/v1/Account/{self.auth_id}/Call/"
        payload = {
            "from": from_number,
            "to": to_number,
            "answer_url": answer_url,
            "answer_method": answer_method,
        }
        with httpx.Client(timeout=10.0) as client:
            res = client.post(url, json=payload, auth=(self.auth_id, self.auth_token))
            res.raise_for_status()
            return res.json()


# Singleton instance
_plivo_service_instance: PlivoService | None = None


def get_plivo_service() -> PlivoService:
    """Dependency provider for PlivoService singleton."""
    global _plivo_service_instance
    if _plivo_service_instance is None:
        _plivo_service_instance = PlivoService()
    return _plivo_service_instance

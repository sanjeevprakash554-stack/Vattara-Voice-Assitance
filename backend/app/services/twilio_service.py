"""Twilio telephony service integration.

Provides a reusable Twilio client, credentials verification, connectivity
health-checks, and graceful fallback when credentials are unconfigured.
"""

from typing import Any
from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


_UNSET = object()


class TwilioConfigurationError(Exception):
    """Raised when an operation requires Twilio client, but credentials are missing."""


class TwilioService:
    """Reusable Twilio telephony client service with safe connection verification."""

    def __init__(
        self,
        account_sid: Any = _UNSET,
        auth_token: Any = _UNSET,
        phone_number: Any = _UNSET,
        public_base_url: Any = _UNSET,
    ) -> None:
        """Initialize Twilio service using explicit parameters or application settings."""
        self.account_sid: str | None = settings.TWILIO_ACCOUNT_SID if account_sid is _UNSET else account_sid
        self.auth_token: str | None = settings.TWILIO_AUTH_TOKEN if auth_token is _UNSET else auth_token
        self.phone_number: str | None = settings.TWILIO_PHONE_NUMBER if phone_number is _UNSET else phone_number
        self.public_base_url: str | None = settings.PUBLIC_BASE_URL if public_base_url is _UNSET else public_base_url

        self._client: Client | None = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the Twilio Client instance if valid credentials are provided."""
        if self.is_configured:
            try:
                self._client = Client(self.account_sid, self.auth_token)
                logger.info(
                    "Twilio Client initialized with Account SID: %s, Phone Number: %s",
                    self.mask_sid(self.account_sid),
                    self.phone_number,
                )
            except Exception as exc:
                logger.error("Failed to initialize Twilio client: %s", exc)
                self._client = None
        else:
            logger.info("Twilio service initialized in unconfigured state (missing or empty credentials).")

    @property
    def is_configured(self) -> bool:
        """Return True if all required credentials (Account SID, Auth Token, Phone Number) are present."""
        return bool(
            self.account_sid
            and self.auth_token
            and self.phone_number
            and self.account_sid.strip()
            and self.auth_token.strip()
            and self.phone_number.strip()
        )

    @property
    def client(self) -> Client:
        """Return active Twilio Client instance or raise TwilioConfigurationError."""
        if not self.is_configured or self._client is None:
            raise TwilioConfigurationError(
                "Twilio service is not configured. Please set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER."
            )
        return self._client

    @staticmethod
    def mask_sid(sid: str | None) -> str | None:
        """Return partially masked Account SID to prevent full credential exposure."""
        if not sid:
            return None
        sid = sid.strip()
        if len(sid) >= 8:
            return f"{sid[:4]}...{sid[-4:]}"
        return "****"

    def check_connection(self) -> dict[str, Any]:
        """Perform a read-only probe against Twilio API to verify credentials and connectivity."""
        if not self.is_configured:
            return {
                "status": "unconfigured",
                "configured": False,
                "account_sid_masked": self.mask_sid(self.account_sid),
                "account_name": None,
                "account_status": None,
                "phone_number": self.phone_number,
                "public_base_url": self.public_base_url,
                "details": "Twilio credentials are not configured in environment variables.",
                "error": None,
            }

        try:
            # Query Twilio account details to verify SID and Auth Token authenticity
            account = self.client.api.v2010.accounts(self.account_sid).fetch()
            return {
                "status": "connected",
                "configured": True,
                "account_sid_masked": self.mask_sid(self.account_sid),
                "account_name": getattr(account, "friendly_name", None),
                "account_status": getattr(account, "status", "active"),
                "phone_number": self.phone_number,
                "public_base_url": self.public_base_url,
                "details": "Successfully authenticated and connected to Twilio API.",
                "error": None,
            }
        except (TwilioRestException, TwilioException) as exc:
            logger.warning("Twilio API probe failed: %s", exc)
            return {
                "status": "error",
                "configured": True,
                "account_sid_masked": self.mask_sid(self.account_sid),
                "account_name": None,
                "account_status": None,
                "phone_number": self.phone_number,
                "public_base_url": self.public_base_url,
                "details": f"Twilio API authentication failed: {getattr(exc, 'msg', str(exc))}",
                "error": str(exc),
            }
        except Exception as exc:
            logger.error("Unexpected error connecting to Twilio API: %s", exc, exc_info=True)
            return {
                "status": "error",
                "configured": True,
                "account_sid_masked": self.mask_sid(self.account_sid),
                "account_name": None,
                "account_status": None,
                "phone_number": self.phone_number,
                "public_base_url": self.public_base_url,
                "details": "Unexpected error while reaching Twilio API endpoint.",
                "error": str(exc),
            }

    def validate_request_signature(
        self,
        uri: str,
        params: dict[str, Any],
        signature: str | None,
        fallback_uris: list[str] | None = None,
    ) -> bool:
        """Validate Twilio request signature against expected URI(s) and POST parameters."""
        if not signature or not self.auth_token:
            return False

        try:
            validator = RequestValidator(self.auth_token)

            # Check primary URI
            if validator.validate(uri, params, signature):
                return True

            # Check fallback URIs (e.g. public base URL if incoming URI was internal proxy host)
            if fallback_uris:
                for fb_uri in fallback_uris:
                    if fb_uri and validator.validate(fb_uri, params, signature):
                        return True

            return False
        except Exception as exc:
            logger.error("Error validating Twilio signature: %s", exc)
            return False

    @staticmethod
    def build_welcome_twiml(
        business_name: str,
        custom_greeting: str | None = None,
        action_url: str | None = None,
        language: str = "en-IN",
    ) -> str:
        """Generate valid TwiML greeting for incoming calls with optional speech gather."""
        response = VoiceResponse()
        greeting = custom_greeting or f"Thank you for calling {business_name}. How can we assist you today?"
        selected_voice = "Polly.Valluvar" if language.startswith("ta") else "Polly.Amy"

        if action_url:
            gather = response.gather(
                input="speech",
                action=action_url,
                method="POST",
                language=language,
                speech_timeout="auto",
            )
            gather.say(greeting, voice=selected_voice)
            response.pause(length=1)
            response.say("We did not receive any input. Goodbye.", voice=selected_voice)
            response.hangup()
        else:
            response.say(greeting, voice=selected_voice)
            response.pause(length=1)

        return str(response)

    @staticmethod
    def build_gather_speech_twiml(
        prompt: str,
        action_url: str,
        language: str = "en-IN",
        speech_timeout: str = "auto",
        voice: str | None = None,
        no_input_message: str | None = None,
    ) -> str:
        """Generate TwiML with <Gather input="speech"> for voice conversation."""
        response = VoiceResponse()
        selected_voice = voice or ("Polly.Valluvar" if language.startswith("ta") else "Polly.Amy")
        gather = response.gather(
            input="speech",
            action=action_url,
            method="POST",
            language=language,
            speech_timeout=speech_timeout,
        )
        gather.say(prompt, voice=selected_voice)
        response.pause(length=1)
        fallback = no_input_message or (
            "நாங்கள் எந்த பதிலும் பெறவில்லை. நன்றி, வணக்கம்."
            if language.startswith("ta")
            else "We did not receive any input. Thank you for calling. Goodbye."
        )
        response.say(fallback, voice=selected_voice)
        response.hangup()
        return str(response)

    @staticmethod
    def build_speech_confirmation_twiml(
        message: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> str:
        """Generate final TwiML speaking confirmation and hanging up."""
        response = VoiceResponse()
        selected_voice = voice or ("Polly.Valluvar" if language.startswith("ta") else "Polly.Amy")
        response.say(message, voice=selected_voice)
        response.pause(length=1)
        response.hangup()
        return str(response)

    @staticmethod
    def build_unknown_number_twiml() -> str:
        """Generate rejection TwiML when dialed number does not belong to any tenant."""
        response = VoiceResponse()
        response.say(
            "Thank you for calling. This number is not associated with an active business organization. Goodbye.",
            voice="Polly.Amy",
        )
        response.hangup()
        return str(response)

    @staticmethod
    def build_media_stream_twiml(
        stream_url: str,
        custom_parameters: dict[str, str] | None = None,
    ) -> str:
        """Generate TwiML connecting an active call to a bidirectional WebSocket Media Stream."""
        response = VoiceResponse()
        connect = response.connect()
        stream = connect.stream(url=stream_url)
        if custom_parameters:
            for k, v in custom_parameters.items():
                stream.parameter(name=k, value=str(v))
        return str(response)


# Singleton service instance
_twilio_service_instance: TwilioService | None = None


def get_twilio_service() -> TwilioService:
    """Dependency provider for TwilioService singleton."""
    global _twilio_service_instance
    if _twilio_service_instance is None:
        _twilio_service_instance = TwilioService()
    return _twilio_service_instance

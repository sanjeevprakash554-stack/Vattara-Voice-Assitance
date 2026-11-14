"""Centralized Real-Time Dashboard Event Manager for Vattara Voice Assistance.

Provides multi-tenant WebSocket event broadcasting for live dashboard telemetry:
- Call Lifecycle: CALL_STARTED, CALL_UPDATED, CALL_COMPLETED, CALL_FAILED
- Live Conversation: TRANSCRIPT_RECEIVED, AI_RESPONSE_GENERATED, LANGUAGE_DETECTED
- Business Operations: APPOINTMENT_CREATED, APPOINTMENT_UPDATED, CUSTOMER_CREATED, REMINDER_CREATED

Strict multi-tenant security:
- Connections are grouped strictly by business_id.
- Broadcasts are strictly dispatched only to active subscribers of that business tenant.
- Audio streaming WebSockets (Plivo/Twilio) are completely isolated and unaffected.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any
from fastapi import WebSocket
from app.core.logging import get_logger

logger = get_logger(__name__)


class DashboardEventManager:
    """Multi-tenant event broadcaster for real-time frontend dashboard WebSockets."""

    def __init__(self) -> None:
        # Maps business_id -> set of active WebSockets
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def register(self, business_id: str, websocket: WebSocket) -> None:
        """Register an authenticated client WebSocket connection for a business tenant."""
        async with self._lock:
            if business_id not in self._connections:
                self._connections[business_id] = set()
            self._connections[business_id].add(websocket)
            client_count = len(self._connections[business_id])

        logger.info(
            "Registered dashboard WebSocket for business %s (Active clients for tenant: %d)",
            business_id,
            client_count,
        )

    async def unregister(self, business_id: str, websocket: WebSocket) -> None:
        """Unregister a client WebSocket connection."""
        async with self._lock:
            if business_id in self._connections:
                self._connections[business_id].discard(websocket)
                if not self._connections[business_id]:
                    del self._connections[business_id]

        logger.info("Unregistered dashboard WebSocket for business %s", business_id)

    def get_subscriber_count(self, business_id: str) -> int:
        """Return number of active dashboard WebSocket subscribers for a tenant."""
        return len(self._connections.get(business_id, set()))

    async def broadcast_event(
        self,
        business_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """Broadcast an event payload to all connected dashboard WebSockets for a business tenant.

        Returns:
            int: Number of subscribers that received the event.
        """
        subscribers = self._connections.get(business_id, set()).copy()
        if not subscribers:
            logger.debug(
                "No dashboard subscribers for business %s to receive event %s",
                business_id,
                event_type,
            )
            return 0

        payload = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "business_id": business_id,
            "data": data,
        }
        raw_message = json.dumps(payload)

        delivered = 0
        dead_connections: list[WebSocket] = []

        for ws in subscribers:
            try:
                await ws.send_text(raw_message)
                delivered += 1
            except Exception as exc:
                logger.warning(
                    "Failed to deliver %s event to dashboard client of business %s: %s",
                    event_type,
                    business_id,
                    exc,
                )
                dead_connections.append(ws)

        # Clean up any dead connections detected during broadcast
        if dead_connections:
            async with self._lock:
                if business_id in self._connections:
                    for dead_ws in dead_connections:
                        self._connections[business_id].discard(dead_ws)
                    if not self._connections[business_id]:
                        del self._connections[business_id]

        logger.debug(
            "Broadcasted %s event to %d/%d subscribers for business %s",
            event_type,
            delivered,
            len(subscribers),
            business_id,
        )
        return delivered

    def dispatch(
        self,
        business_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Threadsafe and event-loop agnostic dispatch helper.

        Can be safely called from synchronous routes, asynchronous handlers,
        background tasks, or worker threads.
        """
        if not business_id:
            return

        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self.broadcast_event(business_id, event_type, data))
            else:
                asyncio.run(self.broadcast_event(business_id, event_type, data))
        except RuntimeError:
            # No running event loop in current thread
            try:
                asyncio.run(self.broadcast_event(business_id, event_type, data))
            except Exception as exc:
                logger.debug("Deferred dashboard event dispatch: %s", exc)


# Global singleton instance
dashboard_event_manager = DashboardEventManager()

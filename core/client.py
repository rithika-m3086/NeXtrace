"""Band client facade.

Selects between two transports that share one interface
(``publish`` / ``subscribe``):

* ``MockBandClient`` — a faithful in-process pub/sub simulator used for local
  development, CI, and offline demos. It mirrors Band's channel semantics so the
  exact same pipeline code runs in both modes.
* ``LiveBandClient`` (see :mod:`core.live_band`) — routes the pipeline through a
  real Band chat room where four separately-registered agents collaborate by
  @mentioning each other over Band's WebSocket transport.

Mode is chosen automatically: if a Band room + the four agent credentials are
present in the environment, the client runs **live**; otherwise it falls back to
the mock simulator. An explicit ``api_key`` argument also forces live mode
(legacy/explicit path).
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional

from core.message_types import BandMessage
from core.live_band import (
    BandAgentCreds,
    BandClientError,
    LiveBandClient,
    is_live_configured,
    load_creds_from_env,
)
from utils.logger import get_logger

import os

__all__ = ["BandClient", "BandClientError", "MockBandClient", "LiveBandClient"]


class MockBandClient:
    """In-memory pub/sub client mirroring Band channel semantics for offline use."""

    def __init__(self, logger):
        self.logger = logger
        self.subscribers: Dict[str, List[Callable]] = {}

    def publish(self, channel: str, message: BandMessage) -> bool:
        self.logger.info(
            f"[MOCK BAND] Publishing message {message.message_id} to channel '{channel}'",
            extra={"pipeline_run_id": message.pipeline_run_id},
        )
        for cb in self.subscribers.get(channel, []):
            try:
                if inspect.iscoroutinefunction(cb):
                    asyncio.create_task(cb(message))
                else:
                    cb(message)
            except Exception as e:  # noqa: BLE001
                self.logger.error(
                    f"[MOCK BAND] Callback error on channel '{channel}': {e}",
                    extra={"pipeline_run_id": message.pipeline_run_id},
                )
        return True

    def subscribe(self, channel: str, callback: Callable):
        self.subscribers.setdefault(channel, []).append(callback)
        self.logger.info(f"[MOCK BAND] Subscribed callback {callback.__name__} to '{channel}'")


class BandClient:
    """Top-level client wrapping the Mock or Live transport based on config."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        agent_id: Optional[str] = None,
        logger=None,
    ):
        self.logger = logger or get_logger("band_client")

        explicit_live = bool(
            api_key and "your_key" not in api_key.lower() and "your_api" not in api_key.lower()
        )

        if explicit_live or is_live_configured():
            self.mode = "live"
            room_id = os.getenv("BAND_ROOM_ID", "")
            creds = load_creds_from_env()
            if not creds and explicit_live:
                # Legacy/explicit single-identity path: use the provided key for
                # every role so the live client is constructible. Real multi-
                # agent routing still prefers per-agent env credentials.
                single = BandAgentCreds(name="orchestrator", api_key=api_key or "", agent_id=agent_id or "")
                creds = {
                    role: BandAgentCreds(name=role, api_key=api_key or "", agent_id=agent_id or "")
                    for role in [
                        "orchestrator", "agent1_forensic", "agent2_attribution",
                        "agent3_impact", "agent4_postmortem",
                    ]
                }
            self.logger.info(
                f"Band running in LIVE mode (room={room_id or 'unset'}, "
                f"{len(creds)} agent identities)."
            )
            self.client: Any = LiveBandClient(room_id=room_id, creds=creds, logger=self.logger)
        else:
            self.mode = "mock"
            self.logger.info("Band running in MOCK offline mode (no live credentials configured).")
            self.client = MockBandClient(self.logger)

    # -- delegation --------------------------------------------------------
    def publish(self, channel: str, message: BandMessage) -> bool:
        try:
            return self.client.publish(channel, message)
        except BandClientError:
            raise
        except Exception as e:  # noqa: BLE001
            raise BandClientError(f"Unexpected error in publish: {e}", e)

    def subscribe(self, channel: str, callback: Callable):
        try:
            self.client.subscribe(channel, callback)
        except BandClientError:
            raise
        except Exception as e:  # noqa: BLE001
            raise BandClientError(f"Unexpected error in subscribe: {e}", e)

    async def start(self) -> None:
        """Open live Band connections (no-op in mock mode)."""
        if self.mode == "live" and hasattr(self.client, "connect"):
            await self.client.connect()

    # -- context manager ---------------------------------------------------
    def __enter__(self):
        self.logger.info("Entering BandClient context.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("Exiting BandClient context.")
        if exc_type:
            self.logger.error(f"BandClient context exited with error: {exc_val}")
        return False

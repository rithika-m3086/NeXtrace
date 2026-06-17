"""Live Band coordination transport.

Makes Band the *actual* coordination layer between NeXtrace's four agents — not
a wrapper around a local queue. Each agent is registered separately in Band (its
own API key + UUID), all four join ONE shared chat room, and they hand work off
by **@mentioning** the next agent. Band delivers each mention to the recipient,
who runs its deterministic stage and mentions the agent after it.

Implementation uses the **installed `thenvoi-sdk` REST client** (`thenvoi_rest`),
verified against the package surface:

* **Send**  — ``agent_api_messages.create_agent_chat_message(chat_id, message)``
  with ``ChatMessageRequest(content=…, mentions=[ChatMessageRequestMentionsItem(id=…)])``.
* **Receive** — a per-agent poll/ack loop:
  ``get_agent_next_message(chat_id)`` → ``mark_agent_message_processing`` →
  dispatch → ``mark_agent_message_processed`` (or ``mark_agent_message_failed``).
  Band's visibility model means each agent only polls messages where it was
  mentioned, so the per-agent loop naturally receives exactly that agent's
  hand-offs.

Our pipeline speaks in *logical channels* (``forensic_timeline`` …); Band speaks
in *rooms + mentions*. This module bridges the two by embedding a small JSON
envelope (``NEXTRACE::{channel, message}``) in each room message and mentioning
the agent that subscribes to that channel.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.channels import BandChannel
from core.message_types import BandMessage


class BandClientError(Exception):
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


@dataclass
class BandAgentCreds:
    """Credentials + identity for one registered Band agent."""

    name: str          # internal logical name, e.g. "agent1_forensic"
    api_key: str
    agent_id: str      # Band agent UUID, used as the @mention target


# Which registered Band agent is the *subscriber* (recipient) of each logical
# channel. Publishing to a channel mentions this agent in the room.
CHANNEL_SUBSCRIBER = {
    BandChannel.RAW_EVIDENCE_INPUT.value: "agent1_forensic",
    BandChannel.FORENSIC_TIMELINE.value: "agent2_attribution",
    BandChannel.ATTACK_ATTRIBUTION.value: "agent3_impact",
    BandChannel.IMPACT_ASSESSMENT.value: "agent4_postmortem",
    BandChannel.POSTMORTEM_COMPLETE.value: "orchestrator",
    BandChannel.PIPELINE_STATUS.value: "orchestrator",
    BandChannel.PIPELINE_ERRORS.value: "orchestrator",
}

# Map an internal BandMessage.agent_id (the *publisher*) to a registered Band
# agent so we send with the right identity/auth.
PUBLISHER_ALIASES = {
    "orchestrator": "orchestrator",
    "agent1_forensic": "agent1_forensic",
    "agent2_attribution": "agent2_attribution",
    "agent3_impact": "agent3_impact",
    "agent4_postmortem": "agent4_postmortem",
}

_ENVELOPE_PREFIX = "NEXTRACE::"


def load_creds_from_env() -> Dict[str, BandAgentCreds]:
    """Read per-agent Band credentials from the environment."""
    spec = {
        "agent1_forensic": ("BAND_AGENT1_API_KEY", "BAND_AGENT1_ID"),
        "agent2_attribution": ("BAND_AGENT2_API_KEY", "BAND_AGENT2_ID"),
        "agent3_impact": ("BAND_AGENT3_API_KEY", "BAND_AGENT3_ID"),
        "agent4_postmortem": ("BAND_AGENT4_API_KEY", "BAND_AGENT4_ID"),
        "orchestrator": ("BAND_ORCHESTRATOR_API_KEY", "BAND_ORCHESTRATOR_ID"),
    }
    creds: Dict[str, BandAgentCreds] = {}
    for name, (key_env, id_env) in spec.items():
        api_key = os.getenv(key_env, "")
        agent_id = os.getenv(id_env, "")
        if api_key and agent_id and not api_key.startswith("your_") and not agent_id.startswith("your_"):
            creds[name] = BandAgentCreds(name=name, api_key=api_key, agent_id=agent_id)
    return creds


def is_live_configured() -> bool:
    """True when a room + at least the four worker agents are configured."""
    room = os.getenv("BAND_ROOM_ID", "")
    if not room or room.startswith("your_"):
        return False
    creds = load_creds_from_env()
    required = {"agent1_forensic", "agent2_attribution", "agent3_impact", "agent4_postmortem"}
    return required.issubset(creds.keys())


def encode_envelope(channel: str, msg: BandMessage) -> str:
    body = {"channel": channel, "message": msg.to_dict()}
    return f"{_ENVELOPE_PREFIX}{json.dumps(body)}"


def decode_envelope(content: str) -> Optional[Dict[str, Any]]:
    idx = content.find(_ENVELOPE_PREFIX)
    if idx == -1:
        return None
    try:
        return json.loads(content[idx + len(_ENVELOPE_PREFIX):])
    except json.JSONDecodeError:
        return None


def _import_sdk():
    try:
        from band.client.rest import (  # type: ignore
            RestClient,
            ChatMessageRequest,
            ChatMessageRequestMentionsItem,
        )
        return RestClient, ChatMessageRequest, ChatMessageRequestMentionsItem
    except Exception as exc:  # noqa: BLE001
        raise BandClientError(
            "band-sdk is not importable. Install it "
            "(`pip install band-sdk`) to enable live Band mode.",
            exc,
        )


class LiveBandClient:
    """Routes the NeXtrace pipeline through a real Band chat room via the SDK."""

    def __init__(self, room_id: str, creds: Dict[str, BandAgentCreds], logger, poll_interval: float = 1.0):
        self.room_id = room_id
        self.creds = creds
        self.logger = logger
        self.poll_interval = poll_interval
        self.subscribers: Dict[str, List[Callable]] = {}
        self._clients: Dict[str, Any] = {}          # name -> RestClient
        self._threads: List[threading.Thread] = []
        self._stop = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._sdk = None  # lazily-loaded (RestClient, ChatMessageRequest, MentionsItem)

    # -- lazy SDK + per-agent clients -------------------------------------
    def _ensure_clients(self) -> None:
        if self._sdk is None:
            self._sdk = _import_sdk()
        RestClient, _, _ = self._sdk
        for name, c in self.creds.items():
            if name not in self._clients:
                self._clients[name] = RestClient(api_key=c.api_key, base_url="https://app.band.ai")

    def _client_for(self, name: str):
        self._ensure_clients()
        return self._clients.get(name) or next(iter(self._clients.values()))

    # -- publish ----------------------------------------------------------
    def publish(self, channel: str, message: BandMessage) -> bool:
        self._ensure_clients()
        _, ChatMessageRequest, MentionsItem = self._sdk

        publisher = PUBLISHER_ALIASES.get(message.agent_id, "orchestrator")
        sender_name = publisher if publisher in self.creds else next(iter(self.creds))
        client = self._client_for(sender_name)

        recipient_name = CHANNEL_SUBSCRIBER.get(channel)
        recipient = self.creds.get(recipient_name) if recipient_name else None
        mentions = [MentionsItem(id=recipient.agent_id)] if recipient else []

        content = encode_envelope(channel, message)
        try:
            client.agent_api_messages.create_agent_chat_message(
                chat_id=self.room_id,
                message=ChatMessageRequest(content=content, mentions=mentions),
            )
            self.logger.info(
                f"[LIVE BAND] {sender_name} → room (channel '{channel}'"
                + (f", @{recipient_name}" if recipient else "") + ")",
                extra={"pipeline_run_id": message.pipeline_run_id},
            )
            return True
        except Exception as exc:  # noqa: BLE001
            raise BandClientError(f"Band send failed on '{channel}'", exc)

    def subscribe(self, channel: str, callback: Callable):
        self.subscribers.setdefault(channel, []).append(callback)
        self.logger.info(f"[LIVE BAND] Registered '{callback.__name__}' for channel '{channel}'")

    # -- dispatch ---------------------------------------------------------
    def _dispatch(self, content: str, own_agent_id: str) -> None:
        envelope = decode_envelope(content)
        if not envelope:
            return
        channel = envelope.get("channel")
        msg_dict = envelope.get("message")
        if not channel or not msg_dict:
            return
        try:
            message = BandMessage.model_validate(msg_dict)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"[LIVE BAND] Dropping unparseable inbound message: {exc}")
            return
        for cb in self.subscribers.get(channel, []):
            try:
                if asyncio.iscoroutinefunction(cb):
                    if self._loop is not None:
                        asyncio.run_coroutine_threadsafe(cb(message), self._loop)
                    else:  # pragma: no cover - loop always set in live runs
                        asyncio.run(cb(message))
                else:
                    cb(message)
            except Exception as exc:  # noqa: BLE001
                self.logger.error(f"[LIVE BAND] Subscriber error on '{channel}': {exc}")

    # -- receive (poll/ack loop per agent) --------------------------------
    def _poll_loop(self, name: str, creds: BandAgentCreds) -> None:
        client = self._client_for(name)
        msgs = client.agent_api_messages
        while not self._stop.is_set():
            try:
                resp = msgs.get_agent_next_message(chat_id=self.room_id)
                data = getattr(resp, "data", None)
                if data is None:
                    self._stop.wait(self.poll_interval)
                    continue
                msg_id = data.id
                try:
                    msgs.mark_agent_message_processing(chat_id=self.room_id, id=msg_id)
                    if getattr(data, "sender_id", None) != creds.agent_id:
                        self._dispatch(data.content or "", creds.agent_id)
                    msgs.mark_agent_message_processed(chat_id=self.room_id, id=msg_id)
                except Exception as exc:  # noqa: BLE001
                    self.logger.error(f"[LIVE BAND] {name} failed processing {msg_id}: {exc}")
                    try:
                        msgs.mark_agent_message_failed(chat_id=self.room_id, id=msg_id, error=str(exc)[:200])
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as exc:  # noqa: BLE001
                if getattr(exc, "status_code", None) == 204:
                    self._stop.wait(self.poll_interval)
                    continue
                self.logger.warning(f"[LIVE BAND] {name} poll error: {exc}")
                self._stop.wait(self.poll_interval)

    async def connect(self) -> None:
        """Start one background poll/ack thread per registered agent."""
        self._ensure_clients()
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self._stop.clear()
        for name, creds in self.creds.items():
            t = threading.Thread(target=self._poll_loop, args=(name, creds),
                                 name=f"band-poll-{name}", daemon=True)
            t.start()
            self._threads.append(t)
        self.logger.info(f"[LIVE BAND] Started {len(self._threads)} poll loop(s) on room {self.room_id}.")

    def stop(self) -> None:
        self._stop.set()

import asyncio
import inspect
import os
from typing import Any, Callable, Dict, List, Optional
from core.message_types import BandMessage
from utils.logger import get_logger

# Import Thenvoi classes safely
try:
    from thenvoi_rest import RestClient, ChatMessageRequest
    from thenvoi import Agent
    THENVOI_AVAILABLE = True
except ImportError:
    THENVOI_AVAILABLE = False


class BandClientError(Exception):
    """Custom wrapper for all Band-related exceptions."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class MockBandClient:
    """Mock in-memory pub-sub client for local/offline development."""

    def __init__(self, logger):
        self.logger = logger
        self.subscribers: Dict[str, List[Callable]] = {}

    def publish(self, channel: str, message: BandMessage) -> bool:
        self.logger.info(
            f"[MOCK BAND] Publishing message {message.message_id} to channel '{channel}'",
            extra={"pipeline_run_id": message.pipeline_run_id}
        )
        callbacks = self.subscribers.get(channel, [])
        for cb in callbacks:
            try:
                # Call callback asynchronously in the current loop if async, else call sync
                if inspect.iscoroutinefunction(cb):
                    asyncio.create_task(cb(message))
                else:
                    cb(message)
            except Exception as e:
                self.logger.error(
                    f"[MOCK BAND] Callback error on channel '{channel}': {e}",
                    extra={"pipeline_run_id": message.pipeline_run_id}
                )
        return True

    def subscribe(self, channel: str, callback: Callable):
        if channel not in self.subscribers:
            self.subscribers[channel] = []
        self.subscribers[channel].append(callback)
        self.logger.info(f"[MOCK BAND] Subscribed callback {callback.__name__} to '{channel}'")


class LiveBandClient:
    """Live Thenvoi-SDK based publisher/subscriber."""

    def __init__(self, api_key: str, agent_id: str, logger):
        self.api_key = api_key
        self.agent_id = agent_id
        self.logger = logger
        if not THENVOI_AVAILABLE:
            raise BandClientError("thenvoi-sdk is not installed or importable.")
        
        try:
            self.rest_client = RestClient(api_key=self.api_key)
            self.logger.info("Initialized Live Thenvoi REST client.")
        except Exception as e:
            raise BandClientError("Failed to initialize Thenvoi RestClient", e)

    def publish(self, channel: str, message: BandMessage) -> bool:
        self.logger.info(
            f"[LIVE BAND] Publishing message to chat room '{channel}'",
            extra={"pipeline_run_id": message.pipeline_run_id}
        )
        try:
            # Send message via REST API
            self.rest_client.agent_api_messages.create_agent_chat_message(
                chat_id=channel,
                message=ChatMessageRequest(
                    content=f"BandMessage: {message.model_dump_json()}",
                )
            )
            return True
        except Exception as e:
            self.logger.error(
                f"[LIVE BAND] Failed to publish message to channel '{channel}': {e}",
                extra={"pipeline_run_id": message.pipeline_run_id}
            )
            raise BandClientError(f"Error publishing to {channel}", e)

    def subscribe(self, channel: str, callback: Callable):
        # In Live Mode, the Thenvoi Agent SDK handles websocket subscription via adapters.
        # We register local callback bindings here to route platform events.
        self.logger.info(f"[LIVE BAND] Subscribed callback {callback.__name__} to room '{channel}'")
        # In a real environment, the framework adapter listens to messages on the room websocket,
        # parses the content, and invokes the callbacks.
        # For simplicity of our pipeline, we can keep a mapping of callbacks.
        pass


class BandClient:
    """Top-level client wrapping Mock or Live implementations based on environment configuration."""

    def __init__(self, api_key: Optional[str] = None, agent_id: Optional[str] = None, logger=None):
        self.logger = logger or get_logger("band_client")
        
        # Detect if we should use Mock Mode or Live Mode
        is_placeholder = not api_key or "your_key" in api_key.lower() or "your_api" in api_key.lower()
        
        if is_placeholder:
            self.logger.info("BAND_API_KEY is not configured or is a placeholder. Using MOCK offline mode.")
            self.mode = "mock"
            self.client = MockBandClient(self.logger)
        else:
            self.logger.info("BAND_API_KEY configured. Running in LIVE mode.")
            self.mode = "live"
            self.client = LiveBandClient(api_key, agent_id or "", self.logger)

    def publish(self, channel: str, message: BandMessage) -> bool:
        try:
            return self.client.publish(channel, message)
        except Exception as e:
            if isinstance(e, BandClientError):
                raise
            raise BandClientError(f"Unexpected error in publish: {e}", e)

    def subscribe(self, channel: str, callback: Callable):
        try:
            self.client.subscribe(channel, callback)
        except Exception as e:
            if isinstance(e, BandClientError):
                raise
            raise BandClientError(f"Unexpected error in subscribe: {e}", e)

    def __enter__(self):
        self.logger.info("Entering BandClient context.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("Exiting BandClient context.")
        if exc_type:
            self.logger.error(f"BandClient context exited with error: {exc_val}")
        return False

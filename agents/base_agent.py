from abc import ABC, abstractmethod
import json
import os
import re
import time
from typing import Any, Dict, Optional, Type
from dotenv import load_dotenv
load_dotenv()
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from pydantic import BaseModel, ValidationError

from core.client import BandClient
from core.message_types import BandMessage
from utils.logger import get_logger

_PROVIDER_CLIENTS = {}


class BaseAgent(ABC):
    """Abstract Base Agent providing LLM integration, schema correction, and Band communication."""

    def __init__(
        self,
        agent_id: str,
        input_channel: str,
        output_channel: str,
        band_client: BandClient,
        logger=None,
    ):
        self.agent_id = agent_id
        self.input_channel = input_channel
        self.output_channel = output_channel
        self.band_client = band_client
        self.logger = logger or get_logger(agent_id)

        # Initialize OpenAI client for OpenRouter or AIML API
        self.openai_client = self._init_openai_client()

    def _get_default_provider(self) -> str:
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        aiml_key = os.getenv("AIML_API_KEY")
        if openrouter_key and not openrouter_key.startswith("your_"):
            return "openrouter"
        elif aiml_key and not aiml_key.startswith("your_"):
            return "aiml"
        return "openrouter"

    def _has_key(self, provider: str) -> bool:
        if provider == "openrouter":
            k = os.getenv("OPENROUTER_API_KEY")
            return bool(k and not k.startswith("your_"))
        elif provider == "aiml":
            k = os.getenv("AIML_API_KEY")
            return bool(k and not k.startswith("your_"))
        elif provider == "featherless":
            k = os.getenv("FEATHERLESS_API_KEY")
            return bool(k and not k.startswith("your_"))
        return False

    def _get_client_for_provider(self, provider: str) -> Optional[OpenAI]:
        global _PROVIDER_CLIENTS
        if provider in _PROVIDER_CLIENTS:
            return _PROVIDER_CLIENTS[provider]

        if OpenAI is None:
            self.logger.warning(f"BaseAgent: 'openai' package not installed. Cannot instantiate OpenAI client.")
            return None

        client = None
        if provider == "openrouter":
            key = os.getenv("OPENROUTER_API_KEY")
            if key and not key.startswith("your_"):
                self.logger.info("BaseAgent: Configuring LLM client for OpenRouter")
                client = OpenAI(
                    api_key=key,
                    base_url="https://openrouter.ai/api/v1",
                )
        elif provider == "aiml":
            key = os.getenv("AIML_API_KEY")
            if key and not key.startswith("your_"):
                self.logger.info("BaseAgent: Configuring LLM client for AIML API")
                client = OpenAI(
                    api_key=key,
                    base_url="https://api.aimlapi.com/v1",
                )
        elif provider == "featherless":
            key = os.getenv("FEATHERLESS_API_KEY")
            if key and not key.startswith("your_"):
                self.logger.info("BaseAgent: Configuring LLM client for Featherless")
                client = OpenAI(
                    api_key=key,
                    base_url="https://api.featherless.ai/v1",
                )

        if client:
            _PROVIDER_CLIENTS[provider] = client
        return client

    def _init_openai_client(self) -> Optional[OpenAI]:
        """Configures OpenAI client using OpenRouter, AIML API, or Featherless based on env variables."""
        mapping = {
            "agent1_forensic": "AGENT1",
            "agent2_attribution": "AGENT2",
            "agent3_impact": "AGENT3",
            "agent4_postmortem": "AGENT4"
        }
        self.agent_prefix = mapping.get(self.agent_id)

        # Resolve provider
        provider = None
        if self.agent_prefix:
            provider = os.getenv(f"{self.agent_prefix}_PROVIDER")
        if not provider:
            provider = self._get_default_provider()

        # Check API key presence
        if not self._has_key(provider):
            default_p = self._get_default_provider()
            self.logger.warning(
                f"BaseAgent '{self.agent_id}': Provider '{provider}' API key is missing. "
                f"Falling back to default provider '{default_p}'."
            )
            provider = default_p

        self.provider = provider

        # Resolve model
        model = None
        if self.agent_prefix:
            model = os.getenv(f"{self.agent_prefix}_MODEL")
        if not model:
            model = os.getenv("MODEL_NAME", "anthropic/claude-3.5-sonnet")
        self.model_name = model

        if OpenAI is None:
            self.logger.warning("BaseAgent: 'openai' package is not installed. LLM client is disabled.")
            return None

        return self._get_client_for_provider(self.provider)

    @abstractmethod
    async def process(self, input_message: BandMessage) -> BandMessage:
        """Processes the input message and returns the output BandMessage.

        Subclasses must implement this.
        """
        pass

    def run(self, loop=None):
        """Starts the subscription listener on the input channel and runs message processing.

        This can be executed in a background thread or event loop.
        """
        self.logger.info(f"BaseAgent '{self.agent_id}': Starting run listener on '{self.input_channel}'")
        
        async def message_callback(msg: BandMessage):
            self.logger.info(
                f"BaseAgent '{self.agent_id}': Received message on '{self.input_channel}'",
                extra={"pipeline_run_id": msg.pipeline_run_id}
            )
            
            # Publish status: agent started processing
            status_msg = BandMessage.create(
                pipeline_run_id=msg.pipeline_run_id,
                agent_id=self.agent_id,
                channel="pipeline_status",
                sequence=msg.sequence + 1,
                status="success",
                confidence=0.8,
                payload={"stage": self.output_channel, "status": "processing"}
            )
            self.band_client.publish("pipeline_status", status_msg)

            try:
                # Call specialized agent processing
                output_msg = await self.process(msg)
                
                # Publish status: agent completed processing
                completion_status = BandMessage.create(
                    pipeline_run_id=msg.pipeline_run_id,
                    agent_id=self.agent_id,
                    channel="pipeline_status",
                    sequence=output_msg.sequence + 1,
                    status="success",
                    confidence=output_msg.confidence,
                    payload={"stage": self.output_channel, "status": "completed"}
                )
                self.band_client.publish("pipeline_status", completion_status)

                # Publish final output message
                self.band_client.publish(self.output_channel, output_msg)
                self.logger.info(
                    f"BaseAgent '{self.agent_id}': Published results to '{self.output_channel}'",
                    extra={"pipeline_run_id": msg.pipeline_run_id}
                )

            except Exception as e:
                self.logger.error(
                    f"BaseAgent '{self.agent_id}': Execution failed: {e}",
                    exc_info=True,
                    extra={"pipeline_run_id": msg.pipeline_run_id}
                )
                # Publish failure state to error channel
                err_msg = BandMessage.create(
                    pipeline_run_id=msg.pipeline_run_id,
                    agent_id=self.agent_id,
                    channel="pipeline_errors",
                    sequence=msg.sequence + 1,
                    status="error",
                    confidence=0.0,
                    payload={"error": str(e), "stage": self.output_channel}
                )
                self.band_client.publish("pipeline_errors", err_msg)

        # Register callback with client subscription
        self.band_client.subscribe(self.input_channel, message_callback)

    def _call_model(self, prompt: str, system_prompt: Optional[str] = None, run_id: Optional[str] = None) -> str:
        """Executes LLM call using openai library with retry logic and 15s timeout."""
        if not self.openai_client:
            raise ValueError("LLM Client is not configured. Check your env variables.")

        agent_model_map = {
            "agent1_forensic": os.getenv("AGENT1_MODEL"),
            "agent2_attribution": os.getenv("AGENT2_MODEL"),
            "agent3_impact": os.getenv("AGENT3_MODEL"),
            "agent4_postmortem": os.getenv("AGENT4_MODEL"),
        }
        model = agent_model_map.get(self.agent_id) or os.getenv(
            "MODEL_NAME", "meta-llama/llama-3-70b-instruct"
        )

        # Map model identifiers for AIML API compatibility
        if getattr(self, "provider", None) == "aiml":
            if model == "meta-llama/llama-3-70b-instruct":
                model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
            elif model == "anthropic/claude-3.5-sonnet":
                model = "claude-sonnet-4-6"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        from utils.rate_limiter import call_with_retry

        total_chars = len(prompt) + len(system_prompt or "")
        estimated_tokens = getattr(prompt, "estimated_tokens", None)
        if estimated_tokens is None:
            estimated_tokens = total_chars // 4

        self.logger.info(f"BaseAgent: Calling LLM (model={model}) with estimated {estimated_tokens} tokens")

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                response = call_with_retry(
                    self.openai_client.chat.completions.create,
                    model=model,
                    messages=messages,
                    temperature=0.1,
                    estimated_tokens=estimated_tokens,
                    timeout=60.0,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                error_msg = f"LLM call failed: {e}"
                self.logger.warning(
                    f"BaseAgent '{self.agent_id}': {error_msg} (Attempt {attempt+1}/{max_attempts})",
                    extra={"pipeline_run_id": run_id} if run_id else {}
                )
                
                is_transient = (attempt < max_attempts - 1)
                if run_id:
                    err_msg = BandMessage.create(
                        pipeline_run_id=run_id,
                        agent_id=self.agent_id,
                        channel="pipeline_errors",
                        sequence=999,
                        status="error",
                        confidence=0.0,
                        payload={
                            "error": f"{error_msg} (Retrying...)" if is_transient else error_msg,
                            "stage": self.output_channel,
                            "transient": is_transient
                        }
                    )
                    self.band_client.publish("pipeline_errors", err_msg)
                
                if not is_transient:
                    raise e
                time.sleep(1.0)

    def _sanitize_json_arithmetic(self, json_str: str) -> str:
        """Evaluates simple arithmetic expressions in raw JSON values (e.g. confidence scores)."""
        def eval_match(m):
            expr = m.group(1)
            try:
                # Safely evaluate simple arithmetic expressions
                if re.match(r'^[0-9.\s+\-*/()]+$', expr):
                    val = eval(expr, {"__builtins__": None}, {})
                    # Clamp confidence values if they exceed 1.0
                    if "confidence" in m.group(0).lower() and val > 1.0:
                        val = 0.95
                    return f': {val}'
            except Exception:
                pass
            return m.group(0)

        # Match ': ' followed by numbers combined with arithmetic operators (+, -, *, /)
        pattern = r':\s*([0-9]+(?:\.[0-9]+)?(?:\s*[+\-*/]\s*[0-9]+(?:\.[0-9]+)?)+)'
        json_str = re.sub(pattern, eval_match, json_str)
        # Also clean up "users_affected_count": -1 to 0 since Pydantic requires ge=0
        json_str = re.sub(r'"users_affected_count"\s*:\s*-1', '"users_affected_count": 0', json_str)
        return json_str

    def _call_model_json(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system_prompt: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> BaseModel:
        """Calls the LLM and validates JSON structure.

        Implements self-correcting retry loop for validation/syntax errors.
        """
        # Embed the target JSON schema in the system prompt
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        schema_instruction = (
            f"\nYou MUST return raw JSON that strictly conforms to the following schema:\n"
            f"{schema_json}\n"
            "Do NOT include conversational text. Return ONLY the raw JSON string. "
            "If using markdown formatting, use: ```json <json_content> ```\n"
            "Ensure all numeric fields are final single numeric values (do NOT include arithmetic expressions like 0.85 + 0.1)."
        )
        
        full_system_prompt = (system_prompt or "") + schema_instruction
        current_prompt = prompt

        for attempt in range(2):
            raw_response = self._call_model(current_prompt, system_prompt=full_system_prompt, run_id=run_id)
            
            # Clean up leading/trailing whitespace
            cleaned = raw_response.strip()
            
            # Remove fences if present
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Find first '{' and last '}' and slice
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                cleaned = cleaned[first_brace:last_brace + 1]

            # Evaluate any arithmetic expressions in JSON numeric values
            cleaned = self._sanitize_json_arithmetic(cleaned)

            try:
                # Parse JSON
                data = json.loads(cleaned)
                # Validate against target Pydantic model
                model_instance = response_model.model_validate(data)
                return model_instance
            except (json.JSONDecodeError, ValidationError) as e:
                # Log raw output at ERROR level
                self.logger.error(
                    f"BaseAgent: JSON parsing/validation failed on attempt {attempt+1}/2: {e}\n"
                    f"Raw response was: {raw_response}"
                )
                if attempt == 0:
                    # Retry once with exact instruction
                    current_prompt += "\n\nYour previous response was not valid JSON. Respond with ONLY the JSON object."
                else:
                    # Second failure raises error caught by run()
                    raise RuntimeError(f"BaseAgent: Failed to generate valid JSON schema for {response_model.__name__} after 2 attempts: {e}")


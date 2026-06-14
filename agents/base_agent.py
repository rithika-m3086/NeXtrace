from abc import ABC, abstractmethod
import json
import os
import time
from typing import Any, Dict, Optional, Type
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from core.client import BandClient
from core.message_types import BandMessage
from utils.logger import get_logger


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

    def _init_openai_client(self) -> Optional[OpenAI]:
        """Configures OpenAI client using OpenRouter or AIML API based on env variables."""
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        aiml_key = os.getenv("AIML_API_KEY")

        if openrouter_key and not openrouter_key.startswith("your_"):
            self.logger.info("BaseAgent: Configuring LLM client for OpenRouter")
            return OpenAI(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
            )
        elif aiml_key and not aiml_key.startswith("your_"):
            self.logger.info("BaseAgent: Configuring LLM client for AIML API")
            return OpenAI(
                api_key=aiml_key,
                base_url="https://api.aimlapi.com/v1",
            )
        else:
            # Fallback placeholder to prevent crashes if credentials aren't loaded yet
            self.logger.warning("BaseAgent: No LLM credentials configured. Calls will fail.")
            return None

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

    def _call_model(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Executes LLM call using openai library with retry logic."""
        if not self.openai_client:
            raise ValueError("LLM Client is not configured. Check your env variables.")

        model = os.getenv("MODEL_NAME", "anthropic/claude-3.5-sonnet")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        max_retries = 3
        delay = 2.0
        for attempt in range(max_retries):
            try:
                self.logger.info(f"BaseAgent: Calling LLM (model={model}), attempt {attempt+1}/{max_retries}")
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.1,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                self.logger.warning(f"BaseAgent: LLM call error: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2.0
        
        raise RuntimeError("BaseAgent: Failed to get response from LLM after 3 retries.")

    def _call_model_json(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system_prompt: Optional[str] = None,
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
            "If using markdown formatting, use: ```json <json_content> ```"
        )
        
        full_system_prompt = (system_prompt or "") + schema_instruction
        current_prompt = prompt

        for attempt in range(2):
            raw_response = self._call_model(current_prompt, system_prompt=full_system_prompt)
            
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


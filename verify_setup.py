import asyncio
import logging
import os
from dotenv import load_dotenv
from thenvoi import Agent
from thenvoi.adapters import LangGraphAdapter
from thenvoi.config import load_agent_config
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_setup():
    load_dotenv()

    # Load agent credentials
    agent_id, api_key = load_agent_config("my_agent")
    logger.info(f"Loaded agent: {agent_id}")

    # Create adapter
    adapter = LangGraphAdapter(
        llm=ChatOpenAI(model="gpt-4o"),
        checkpointer=InMemorySaver(),
    )

    # Create agent (validates connection)
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("THENVOI_WS_URL"),
        rest_url=os.getenv("THENVOI_REST_URL"),
    )

    # Start to validate connection, then stop
    await agent.start()
    logger.info(f"Connected as: {agent.agent_name}")
    logger.info("Setup verified successfully!")
    await agent.stop()

asyncio.run(verify_setup())

"""Manual demo: a self-healing chatbot loop powered by :class:`ReboundSession`.

Run with::

    python -m src.llm_circuit_router.demo_rebound_chatbot

Requires a compiled ``final_model_registry.json`` and live provider credentials.
"""

from __future__ import annotations

import asyncio

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.llm_circuit_router.console import enable_utf8_console
from src.llm_circuit_router.rebound import ReboundSession

PROMPT = "Write a python script to parse timestamps out of a JSON schema dictionary."
TASK_DOMAIN = "coding"


async def ask_chatbot(prompt_message: str, task_domain: str = "general") -> str:
    """Answer ``prompt_message``, failing over across models until one responds."""
    session = ReboundSession(task_type=task_domain)

    while True:
        model_setup = session.get_current_model_config()
        if not model_setup:
            raise RuntimeError(
                "❌ Chatbot pipeline error: all ranked candidates were exhausted."
            )

        print(f"🤖 [Chatbot] Routing payload to: {model_setup['model']}...")
        try:
            llm = ChatOpenAI(
                model=model_setup["model"],
                api_key=model_setup["api_key"],
                base_url=model_setup["base_url"],
                temperature=0.3,
                # Disable LangChain retries so the session can swap models instead.
                max_retries=0,
            )
            response = await llm.ainvoke([HumanMessage(content=prompt_message)])
            print("🎉 Chatbot prompt processed successfully!")
            return response.content.strip()
        except Exception as provider_exception:  # noqa: BLE001 - this is the failover path
            session.rebound(provider_exception)
            print("⏳ Swapping nodes... re-attempting request.")


async def main() -> None:
    reply = await ask_chatbot(PROMPT, task_domain=TASK_DOMAIN)
    print("\n💬 Final Chatbot User Output:")
    print("=" * 50)
    print(reply)
    print("=" * 50)


if __name__ == "__main__":
    enable_utf8_console()
    asyncio.run(main())

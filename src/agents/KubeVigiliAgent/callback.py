from langchain_core.agents import AgentFinish
from typing import Any
from langchain.callbacks.base import AsyncCallbackHandler

class FormatOutput(AsyncCallbackHandler):
    async def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any):
        try:
            outputs.pop("messages")
        except:
            print("")
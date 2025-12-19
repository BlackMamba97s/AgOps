import asyncio
from injectable import load_injection_container
from agents.KubeVigiliAgent.agent import KubeVigilAgent
from dotenv import load_dotenv
import os

load_injection_container()
load_dotenv()


async def main():
    agent = KubeVigilAgent()
    input_dict = {"input": "CIIIIAO"}

    async for chunk in agent.get_agent().astream(input_dict):
        # Agent Action
        if "actions" in chunk:
            for action in chunk["actions"]:
                print(f"\nCalling Tool: `{action.tool}` with input `{action.tool_input}`")

        # Observation
        elif "steps" in chunk:
            for step in chunk["steps"]:
                print(f"\n Tool Result: `{step.observation}`")

        else:
            print(f'\n Final Output: {chunk["output"]}')


if __name__ == "__main__":
    asyncio.run(main())
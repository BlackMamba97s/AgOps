import chainlit as cl
from injectable import load_injection_container
from agents.KubeVigiliAgent.agent import KubeVigilAgent
from langchain.schema.runnable import RunnableConfig
from langchain_core.runnables import Runnable


import os
from langfuse.callback import CallbackHandler

os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-05400f79-300a-432a-a1be-3c83194f5299" 
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-06b80cc7-6528-4b34-938a-fd3ce84cf827" 
os.environ["LANGFUSE_HOST"] = "https://langfuse.liquid-reply.net" 
langfuse_handler = CallbackHandler(
    secret_key="sk-lf-06b80cc7-6528-4b34-938a-fd3ce84cf827",
    public_key="pk-lf-05400f79-300a-432a-a1be-3c83194f5299",
    host="https://langfuse.liquid-reply.net")

load_injection_container()
from dotenv import load_dotenv
import os
load_dotenv(override=True)

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("agent", KubeVigilAgent())

@cl.on_message
async def on_message(message: cl.Message):
    input_dict = {}
    input_dict["input"] = message.content
    agent: KubeVigilAgent = cl.user_session.get("agent")

    msg = cl.Message(content="")
    async with cl.Step(name="Agent", type="llm") as step_main:
        async for chunk in agent.get_agent().astream(
                input_dict,
                config=RunnableConfig(callbacks=[langfuse_handler])
        ):
                # Agent Action
            if "actions" in chunk:
                for action in chunk["actions"]:
                    global tool_name
                    tool_name = str(action.tool)
                    async with cl.Step(name=tool_name, type="tool") as step_tool:
                        print(f"\nCalling Tool: `{action.tool}` with input `{action.tool_input}`")
                        
                        if str(action.tool) == 'PythonREPLTool':
                            #await msg.stream_token(f"""\nCalling Tool: `{action.tool}` with input \n
                            await step_tool.stream_token(f"""\nCalling Tool: `{action.tool}` with input \n
```python
{str(action.tool_input)}
```
                                                """)
                        else:
                            await step_tool.stream_token(f"Tool input `{action.tool_input}`")
                            #await msg.stream_token(f"\nCalling Tool: `{action.tool}` with input `{action.tool_input}`")
            # Observation
            elif "steps" in chunk:
                async with cl.Step(name=tool_name, type="tool") as step_tool:
                    for step in chunk["steps"]:
                        print(f"\n Tool Result: `{step.observation}`")
                        await step_tool.stream_token(f"""Tool Result: 
{step.observation}""")
                        #await msg.stream_token(f"Tool Result: `{step.observation}`")
                # Final result
            else:
                print(f'\n Final Output: {chunk["output"]}')
                await step_main.stream_token(str(chunk["output"]))
                # await msg.stream_token("\n"+str(chunk["output"]))

            # print("---")

        await msg.send()

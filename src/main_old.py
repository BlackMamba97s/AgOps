import sys, os
import chainlit as cl
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv, find_dotenv
from agents.KubeVigiliAgent.agent import KubeVigilAgent
from injectable import load_injection_container
from langchain.schema.runnable import RunnableConfig
from langchain_core.runnables import Runnable

# Load env vars
load_dotenv(find_dotenv())

# Creazione dell'API con FastAPI
app = FastAPI()

# Token di autenticazione (può essere preso da una variabile d'ambiente)
EVAL_TOKEN = os.getenv("EVAL_TOKEN", "c2RsY01hcmNvOnNkbGMyMDI0")
security = HTTPBearer()

# Funzione per verificare il token
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != EVAL_TOKEN:
        raise HTTPException(status_code=403, detail="Token non valido")

@app.get("/test")
async def test():
    return {"status": "success", "message": "API is working"}

# Endpoint protetto per eseguire la valutazione
@app.post("/evaluate", dependencies=[Depends(verify_token)])
async def evaluate(request: Request):
    if os.getenv("EVAL", "false").lower() == "true":
        # Estrazione dell'input dalla richiesta
        data = await request.json()
        input_data = data.get("input", None)
        print(f"[i] Input Data: {input_data}")

        if not input_data:
            raise HTTPException(status_code=400, detail="Input mancante")

        # Creazione di un'istanza dell'agente KubeVigilAgent
        agent = KubeVigilAgent()

        # Dati da passare all'agente
        input_dict = {"input": input_data}
        output = ""

        try:
            print("[i] Eseguo l'agente in modo async")
            # Esecuzione asincrona dell'agente e raccolta dell'output
            async for chunk in agent.astream(input_dict):
                # Se c'è un'azione, possiamo gestirla
                if "actions" in chunk:
                    for action in chunk["actions"]:
                        tool_name = str(action.tool)
                        output += f"Calling Tool: {tool_name} with input: {action.tool_input}\n"
                
                # Gestione dei risultati intermedi (steps)
                elif "steps" in chunk:
                    for step in chunk["steps"]:
                        output += f"Tool Result: {step.observation}\n"
                
                # Risultato finale
                else:
                    output += f"{chunk['output']}\n"

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore nell'esecuzione dell'agente: {str(e)}")

        # Restituzione del risultato come risposta JSON
        return {"status": "success", "output": output.strip()}

cl_app = cl.serve(app)

load_injection_container()

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("agent", KubeVigilAgent())

@cl.on_message
async def on_message(message: cl.Message):
    input_dict = {}
    input_dict["input"] = message.content
    agent: KubeVigilAgent = cl.user_session.get("agent")

    msg = cl.Message(content="")
    async with cl.Step(name="Agent", type="llm", root=True) as step_main:
        async for chunk in agent.get_agent().astream(
                input_dict,
        ):
                # Agent Action
            if "actions" in chunk:
                for action in chunk["actions"]:
                    global tool_name
                    tool_name = str(action.tool)
                    async with cl.Step(name=tool_name, type="tool", root=False) as step_tool:
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
                async with cl.Step(name=tool_name, type="tool", root=False) as step_tool:
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

if __name__ == "__main__":
    cl.run(cl_app)
import os
from langfuse.callback import CallbackHandler

os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-05400f79-300a-432a-a1be-3c83194f5299" 
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-06b80cc7-6528-4b34-938a-fd3ce84cf827" 
os.environ["LANGFUSE_HOST"] = "https://langfuse.liquid-reply.net" 
langfuse_handler = CallbackHandler(
    secret_key="sk-lf-06b80cc7-6528-4b34-938a-fd3ce84cf827",
    public_key="pk-lf-05400f79-300a-432a-a1be-3c83194f5299",
    host="https://langfuse.liquid-reply.net",
)
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from dotenv import load_dotenv, find_dotenv
from agents.KubeVigiliAgent.agent import KubeVigilAgent
from chainlit.utils import mount_chainlit
from langchain.schema.runnable import RunnableConfig
import nltk

from pydantic import BaseModel
nltk.download('punkt_tab')
import chainlit as cl
from typing import Optional
nltk.download('averaged_perceptron_tagger_eng')
# Load env vars

load_dotenv(find_dotenv())




app = FastAPI()

class ClusterVigilRequest(BaseModel):
    input: str  
    request_name: Optional[str] = None 


@app.get("/test")
async def test():
    return {"status": "success", "message": "API is working"}

@app.post("/call_clustervigil")
async def evaluate(data: ClusterVigilRequest):
    # Estrazione dell'input dalla richiesta
    input_data = data.input
    request_name = data.request_name
    langfuse_handler.metadata = { "request_name" : request_name or "anonymous_test"}

    agent = KubeVigilAgent()
    input_dict = {"input": input_data}
    output = ""

    try:
        async for result in await agent.istream(input_dict,config=RunnableConfig(callbacks=[langfuse_handler])):
            if "output" in result:
                output += f"{result['output']}\n"
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore nell'esecuzione dell'agente: {str(e)}")

    return {"status": "success", "output": output.strip()}

if __name__ == "__main__":
    mount_chainlit(app=app, target="cl-async.py", path="/home")
    uvicorn.run(app, host="0.0.0.0", port=8000)

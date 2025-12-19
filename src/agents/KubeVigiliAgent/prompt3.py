from langchain.prompts import PromptTemplate
from langchain import hub
from langfuse import Langfuse
import os


langfuse = Langfuse(public_key="pk-lf-05400f79-300a-432a-a1be-3c83194f5299" , secret_key="sk-lf-06b80cc7-6528-4b34-938a-fd3ce84cf827", host="https://langfuse.liquid-reply.net")

def get_prompt():
    prompt = hub.pull("hwchase17/openai-tools-agent")

    prompt[0].prompt = PromptTemplate.from_template(langfuse.get_prompt(name="ClusterVigil", version=os.environ["PROMPT_VERSION"]).get_langchain_prompt())

    return prompt


if __name__ == "__main__":
    os.environ["PROMPT_VERSION"] = "2"
    print(get_prompt())
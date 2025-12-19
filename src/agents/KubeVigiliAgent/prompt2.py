from langchain.prompts import PromptTemplate
from langchain import hub


def get_prompt():
    prompt = hub.pull("hwchase17/openai-tools-agent")
    with open("../../prompt_template.txt", "r") as f:
        template_str = f.read()
    prompt[0].prompt = PromptTemplate.from_template(template_str)

    return prompt
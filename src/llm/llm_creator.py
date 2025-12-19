from langchain_openai import AzureChatOpenAI
import os

def create_new_llm(temperature = 0):

    return AzureChatOpenAI(
        api_key        = os.getenv('AZURE_API_KEY_GPT4'),
        api_version    = os.getenv('AZURE_GPT_VERSION'),
        azure_endpoint = os.getenv('AZURE_ENDPOINT'),
        model_name     = os.getenv('AZURE_GPT_4_MODEL'),
        streaming      = True,
        temperature    = temperature,


    )
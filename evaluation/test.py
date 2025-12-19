from deepeval.models import AzureOpenAIModel
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams,LLMTestCase
from deepeval import evaluate
import sys
import requests
from dotenv import load_dotenv, find_dotenv
import os
import json
load_dotenv(find_dotenv())
MODEL_TO_TEST = sys.argv[1]
PATH_DATASET = sys.argv[2]

AZURE_API_KEY = os.getenv("AZURE_API_KEY_GPT4")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")  
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_GPT_4_MODEL") 
AZURE_MODEL_NAME = "gpt-4o"
AZURE_API_VERSION = os.getenv("AZURE_GPT_VERSION")


model = AzureOpenAIModel(
    model_name=AZURE_MODEL_NAME,
    deployment_name=AZURE_DEPLOYMENT_NAME,
    azure_openai_api_key=AZURE_API_KEY,
    openai_api_version=AZURE_API_VERSION,
    azure_endpoint=AZURE_ENDPOINT,
    temperature=0
)


correctness_metric = GEval(
    name="Correctness",
    criteria="Determine whether the actual output is factually correct based on the expected output.",
    # NOTE: you can only provide either criteria or evaluation_steps, and not both
    evaluation_steps=[
        "Check whether the facts in 'actual output' contradicts any facts in 'expected output'",
        "You should also heavily penalize omission of detail",
        "Vague language, or contradicting OPINIONS, are OK"
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    model = model,
    threshold = 0.7
)

failed = False

def load_dataset(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


dataset = load_dataset(PATH_DATASET)

test_cases = []
for i, item in enumerate(dataset, 1):

    input_text = item["input"]
    expected_output = item["expected_output"]

    url = MODEL_TO_TEST
    headers = {
    "Content-Type": "application/json"
    }
    data = {
    "input": item["input"]
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    json_data = response.json()
    output = json_data["output"]

    test_cases.append(
        LLMTestCase(
        input=input_text,
        actual_output=output,
        expected_output=expected_output
        )
    )


evaluate(test_cases=test_cases, metrics=[correctness_metric])
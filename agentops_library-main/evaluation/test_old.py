import os
os.environ["OTEL_PYTHON_DISABLED"] = "true"
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"

from deepeval.models import AzureOpenAIModel
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams,LLMTestCase, ToolCall
from deepeval.metrics import ToolCorrectnessMetric
from deepeval import evaluate
from deepeval.evaluate import DisplayConfig
import sys
import requests
from dotenv import load_dotenv, find_dotenv
import json
import argparse
from langfuse import Langfuse
from datetime import datetime, timedelta, timezone
import uuid
import time


load_dotenv(find_dotenv())
os.makedirs(".deepeval", exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument('--test', nargs='+', required=True, help='Lista di test da eseguire')
parser.add_argument('--thresholds', nargs='+', type = float, required=True, help='Lista di thresholds per considerare un test superato (0,1]')
parser.add_argument('--dataset', nargs='+', required=True, help='Lista di dataset')
parser.add_argument('--model', type=str, required=True, help='Endopoint del modello da contattare')
parser.add_argument('--langfuse-url', type=str, required=True, help='URL di langfuse')
parser.add_argument('--langfuse-public-key', type=str, required=True, help='Chiave pubblica di langfuse')
parser.add_argument('--langfuse-private-key', type=str, required=True, help='Chiave privata di langfuse')

args = parser.parse_args()

os.environ["LANGFUSE_PUBLIC_KEY"] = args.langfuse_public_key
os.environ["LANGFUSE_SECRET_KEY"] = args.langfuse_private_key
os.environ["LANGFUSE_HOST"] = args.langfuse_url

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

failed = False
langfuse = Langfuse()


def get_traces_by_metadata(key, value):

    all_traces = langfuse.api.trace.list(limit = 100).data

    filtered_traces = [
        t for t in all_traces
        if t.metadata is not None and t.metadata.get(key) == value
    ]
    return filtered_traces

def print_results(results, threshold):
    total_score = 0
    count = 0

    for test_case_result in results.test_results:
        print("TEST CASE: \n")
        print(f"\nTest input: {test_case_result.input}")
        for metric_result in test_case_result.metrics_data:
            print(f"  {metric_result.name} - Score: {metric_result.score}, Reason: {metric_result.reason}")
            total_score += metric_result.score
            count += 1
    print("_______________________________")
    if count > 0:
        overall_score = total_score / count
        print("\nOverall Score:", overall_score)
        return overall_score > threshold
    else:
        print("No metrics were evaluated.")

    

display_config=DisplayConfig(verbose_mode= False, print_results= False)
pass_status=True
for dataset_name, test, threshold in zip(args.dataset, args.test, args.thresholds):

    if (test == "correctness"):
        print(f"-------------------------{test.upper()}-------------------------")
        correctness_metric = GEval(
            name="Correctness",
            criteria="Determine whether the actual output is factually correct based on the expected output.",
            evaluation_steps=[
                "Check whether the facts in 'actual output' contradicts any facts in 'expected output'",
                "You should also heavily penalize omission of detail",
                "Vague language, or contradicting OPINIONS, are OK"
            ],
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
            model = model,
            threshold = threshold,
            
        
        )

        dataset = langfuse.get_dataset(dataset_name)

        test_cases = []
        for item in dataset.items:

            input_text = item.input
            expected_output = item.expected_output

            url = args.model
            request_name = "correctness_test_"+str(uuid.uuid4())
            headers = {
            "Content-Type": "application/json"
            }
            data = {
            "input": input_text,
            "request_name": request_name
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


        status = print_results(evaluate(test_cases=test_cases, metrics=[correctness_metric],display_config=display_config),threshold=threshold)
        pass_status = pass_status and status

    if (test == "tool_correctness"):
        print(f"-------------------------{test.upper()}-------------------------")
        tool_correctness_metric = ToolCorrectnessMetric(threshold=threshold)

        dataset = langfuse.get_dataset(dataset_name)

        test_cases = []
        expected_tools = []
        tools_called = []
        for item in dataset.items:
            input_json = item.input
            input_text = input_json.get("input")
            expected_output = item.expected_output
            for tool_name in input_json.get("expected_tools"):
                expected_tools.append(ToolCall(name=tool_name))

            url = args.model
            request_name = "tool_correctness_test_"+str(uuid.uuid4())
            headers = {
            "Content-Type": "application/json"
            }
            data = {
            "input": input_text,
            "request_name": request_name
            }

            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            json_data = response.json()
            output = json_data["output"]
            time.sleep(10)
            traces = get_traces_by_metadata(key = "request_name", value = request_name)

            tools_list = []


            for trace in traces:
                trace_input = getattr(trace, 'input', None)
                all_spans = trace.observations
                for span in all_spans:

                    input_span = langfuse.api.observations.get(span).dict()["input"]

                    if isinstance(input_span, list):
                        for msg in input_span:
                            if isinstance(msg, dict) and 'role' in msg.keys() and 'name' in msg.keys():
                                if msg['role'] == 'tool':
                                    tools_list.append(msg['name'])    

            

            tools_called = [ToolCall(name=tool) for tool in list(set(tools_list))]
            test_cases.append(
                LLMTestCase(
                input=input_text,
                actual_output=output,
                expected_output=expected_output,
                tools_called=tools_called,
                expected_tools=expected_tools
                )
            )


        status = print_results(evaluate(test_cases=test_cases, metrics=[tool_correctness_metric],display_config=display_config),threshold=threshold)
        pass_status = pass_status and status

if not pass_status:
    print("❌ Alcuni test non sono passati. Uscita con codice 1.")
    sys.exit(1)

print("✅ Tutti i test sono passati. Uscita con codice 0.")
sys.exit(0)

        
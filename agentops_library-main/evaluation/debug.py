
import os
from langfuse import Langfuse, get_client

os.environ['LANGFUSE_PUBLIC_KEY'] = 'pk-lf-05400f79-300a-432a-a1be-3c83194f5299'
os.environ['LANGFUSE_SECRET_KEY'] = 'sk-lf-06b80cc7-6528-4b34-938a-fd3ce84cf827'
os.environ['LANGFUSE_HOST'] = 'https://langfuse.liquid-reply.net'
langfuse = get_client()

def get_traces_by_name(name):

    all_traces = langfuse.api.trace.list(limit = 100).data

    filtered_traces = [
        t for t in all_traces
        if t.name == name
    ]
    return filtered_traces

traces = get_traces_by_name(name='tool_correctness_test_eba85c27-de12-4305-bdb3-30adfb87f007')

#print(traces)

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


tools_called = [tool for tool in list(set(tools_list))]

print(tools_called)
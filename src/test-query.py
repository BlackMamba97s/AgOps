# import requests
# import time
# import json

# def query_events(input):

#     input_json=json.loads(input)
#     try:
#         namespace = input_json["namespace"]
#     except:
#         namespace = None
#     try:
#         resource_name = input_json["resource_name"]
#     except:
#         resource_name = None
#     try:
#         resource_type = input_json["resource_type"]
#     except:
#         resource_type = None
#     try:
#         start_time = input_json["start_time"]
#     except:
#         start_time = 24
#     try:
#         end_time = input_json["end_time"]
#     except:
#         end_time = 0
#     if start_time < 0 or end_time < 0:
#         raise ValueError("start_time and end_time must be positive numbers.")

#     if start_time < end_time:
#         raise ValueError("You must enter start_time > end_time.")

#     url = "https://loki.liquid-reply.net/loki/api/v1/query_range"

#     end = int((time.time() - end_time*60*60)*1000000000)

#     start = end - start_time*60*60*1000000000
#     query = '{app="kubernetes-event-exporter"} |= `` | json | line_format `[{{.metadata_namespace}}] [{{.involvedObject_kind}}] "{{.involvedObject_name}}" [{{.type}}] [{{.reason}}] {{.message}}`'

#     if namespace or namespace != "":
#         query = query + f'| metadata_namespace =~ `{namespace}`'
#     if resource_name or resource_name != "":
#         query = query + f'| involvedObject_name =~ `{resource_name}`'
#     if resource_type or resource_type != "":
#         query = query + f'| involvedObject_kind =~ `{resource_type}`'

#     print(query)
#     params = {
#         "query": query,
#         "start": str(start),
#         "end": str(end)
#     }

#     response = requests.get(url, params=params)


#     if response.status_code != 200:
#         print(f"Request failed with status code {response.status_code}")
#         return
#     results = []
#     for event in response.json()["data"]["result"]:
#         print(event["values"][0][1],"\n")
#         results.append(event["values"][0][1])

# query_events('{"namespace":"","resource_name":"","resource_type":"Pod","start_time":24,"end_time":0}')


from tools.queryEvents_tool.tool import QueryEventsTool

# Initialize the search_events tool
search_events = QueryEventsTool().getTool()

# Define the namespaces
namespaces = ['angeloazzurro-cluster', 'argocd', 'otel-demo']#, 'backstage', 'botkube', 'crossplane', 'crossplane-providers', 'default', 'falco', 'gatekeeper-system', 'gitea', 'gitlab', 'jenkins', 'k8sgpt-operator-system', 'kepler', 'kube-node-lease', 'kube-public', 'kube-system', 'kubernetes-dashboard', 'observability', 'openldap', 'otel-demo', 'podtato-kubectl', 'registry', 'test', 'test-backstage', 'test-err', 'test-gatekeeper', 'test-listener', 'test-ns1', 'test-ns2', 'traefik']

# Prepare the input for the search_events tool
inputs = [f'''{{"namespace": "{namespace}","resource_name": "","resource_type": "","event_type": "Warning","start_time": 24.0,"end_time": 0.0}}''' for namespace in namespaces]

warning_events_count = {}
for input in inputs:
    input = input.replace('"',"'")
    events = search_events._run(input)
    print(events,"\n","-------------------------------------------------------------------------------------")
    #warning_events_count[input['namespace']] = len(events)




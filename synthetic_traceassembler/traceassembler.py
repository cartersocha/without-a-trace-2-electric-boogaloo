import requests
import os
import time
from datetime import datetime, timezone, timedelta

from opentelemetry.trace import SpanKind
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (ConsoleSpanExporter, BatchSpanProcessor)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def make_json_post_request(url, data, headers):
    try:
        # Send the POST request with the provided data and headers
        response = requests.post(url, json=data, headers=headers)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Return the JSON response
            return response.json()
        else:
            print(f"Request failed with status code {response.status_code} - {response.reason}")
            print(response.text)
            return None

    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def parse_api_response(json_response):
    nodes = set()
    edges = []

    series = json_response['data']['attributes']['series']
    for s in series:
        labels = s['group-labels']
        # find label that contains client.service.name
        client_svc_name = [l for l in labels if 'client.service.name' in l][0]
        server_svc_name = [l for l in labels if 'server.service.name' in l][0]

        if len(client_svc_name) > 0:
            client_svc_name = client_svc_name.split('=')[1]
            if len(client_svc_name) > 0:
                nodes.add(client_svc_name)

        if len(server_svc_name) > 0:
            server_svc_name = server_svc_name.split('=')[1]
            if len(server_svc_name) > 0:
                nodes.add(server_svc_name)

        if len(client_svc_name) > 0 and len(server_svc_name) > 0 and client_svc_name != server_svc_name:
            edges.append((client_svc_name, server_svc_name))
    
    return list(nodes), edges

def parse_otterize_input(input_text):
    """Parse the input text from otterize CLI and return a list of nodes and edges."""
    nodes = set()
    edges = []

    lines = input_text.strip().split('\n')
    for line in lines:
        if 'calls:' in line:
            source_service, _ = line.split(' in namespace')
            nodes.add(source_service.strip())
        elif line.startswith('  - '):
            _, target = line.split('-', 1)
            target_service, _ = target.split(' in namespace')
            nodes.add(target_service.strip())
            # do not add edges for calls to self
            if source_service.strip() != target_service.strip():
                edges.append((source_service.strip(), target_service.strip()))

    return list(nodes), edges

def find_root_nodes(nodes, edges):
    """Find the root nodes in the graph."""
    nodes_with_incoming_edges = set(edge[1] for edge in edges)    
    root_nodes = [node for node in nodes if node not in nodes_with_incoming_edges]

    return root_nodes

def get_otlp_exporter():
    ls_access_token = os.environ.get("LS_ACCESS_TOKEN")
    return OTLPSpanExporter(
        endpoint="ingest.lightstep.com:443",
        headers=(("lightstep-access-token", ls_access_token),),
    )

console_exporter = ConsoleSpanExporter()
span_processor = BatchSpanProcessor(console_exporter)
otlp_processor = BatchSpanProcessor(get_otlp_exporter())

def build_trace(root_nodes, edges):
    # Function to simulate the processing of a node
    def process_node(node):
        # Replace this with your actual processing logic
        time.sleep(0.1)
        print(f"Processing node: {node}")

    for root_node in root_nodes:
        tp = TracerProvider(resource=Resource.create({'service.name': root_node}))
        tp.add_span_processor(span_processor)
        tp.add_span_processor(otlp_processor)
        tracer = tp.get_tracer(__name__)

        with tracer.start_as_current_span(root_node, kind=SpanKind.SERVER) as root_span:
            root_span.add_event(f"Processing root node: {root_node}")
            root_span.set_attribute('synthetic', True)
            root_span.set_attribute('node', root_node)
            process_node(root_node)
            trace_children(root_node, process_node, edges)

def trace_children(current_node, process_node, edges):
    for edge in edges:
        source, target = edge
        if source == current_node:
            tp = TracerProvider(resource=Resource.create({'service.name': target}))
            tp.add_span_processor(span_processor)
            tp.add_span_processor(otlp_processor)
            tracer = tp.get_tracer(__name__)
            with tracer.start_as_current_span(target, kind=SpanKind.SERVER) as span:
                span.add_event(f"Processing node: {target}")
                span.set_attribute('synthetic', True)
                span.set_attribute('node', target)
                process_node(target)
                trace_children(target, process_node, edges)

if __name__ == "__main__":
    api_url = f"https://api.lightstep.com/public/v0.2/{os.environ['LS_ORG']}/projects/{os.environ['LS_PROJ']}/telemetry/query_timeseries"
    now = datetime.now(timezone.utc).astimezone()
    oldest_time = datetime.now(timezone.utc) - timedelta(minutes = 5)

    json_data = {
        'data': {
            'attributes': {
                'input-language': 'tql',
                'oldest-time': oldest_time.isoformat(),
                'youngest-time': now.isoformat(),
                'query': 'metric traces_service_graph_request_total_test0 | delta | group_by ["client.service.name", "server.service.name"], sum'
            }
        }
    }
    # eyJhbGciOiJIUzI1NiIsImtpZCI6IjIwMTktMDMtMDEiLCJ0eXAiOiJKV1QifQ.eyJzY3AiOnsicm9sZSI6ImU1MTI5ODNiLTFjYjktMTFlOC05M2Y1LTQyMDEwYWYwMGFkNiJ9LCJ2ZXIiOjEsImRlYnVnIjp7Im9yZyI6IkxpZ2h0U3RlcCIsInJvbGUiOiJPcmdhbml6YXRpb24gQWRtaW4ifSwiYXVkIjoiYXBwLmxpZ2h0c3RlcC5jb20iLCJleHAiOjE3MjIzMTEyMzIsImp0aSI6ImhsZ242dWthcTNuNTRybXlhNG1icGU2Nmt3enhkNmZpbmNndGhnbWVna3VodGh4bCIsImlhdCI6MTY5MDc3NTIzMiwiaXNzIjoibGlnaHRzdGVwLmNvbSIsInN1YiI6IjEyOWY2ZWIzNGE3ZGJjZDcxZTI2NDM1Yzc4OSJ9.w43UydlSIxQsqL1Uz0Ztj8Gtih_MXtro-3jv70TgWFo
    api_token = os.environ.get("LS_API_TOKEN")
    # Example headers to be set in the POST request
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }

    json_response = make_json_post_request(api_url, json_data, headers)

    if json_response:
        nodes, edges = parse_api_response(json_response)
        print(nodes)
        print(edges)
        root_nodes = find_root_nodes(nodes, edges)
        build_trace(root_nodes, edges)
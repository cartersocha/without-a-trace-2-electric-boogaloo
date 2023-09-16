import os
import sys
import time
from opentelemetry.trace import SpanKind
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (ConsoleSpanExporter, BatchSpanProcessor)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def parse_input(input_text):
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
        # set span.kind to server
        with tracer.start_as_current_span(root_node, kind=SpanKind.SERVER) as root_span:
            #root_span_context = root_span.get_span_context()
            #print("context is", root_span_context)
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


# print colorized text that says without a trace
print("\033[1;32;40mWithout a trace\033[0m")
                      

# get first command line arg
input_text = open(os.path.join(os.path.dirname(__file__), sys.argv[1])).read()
print(input_text)

nodes, edges = parse_input(input_text)

print("Nodes:")
print(nodes)
print("\nEdges:")
print(edges)
print("\nRoot nodes:")
root_nodes = find_root_nodes(nodes, edges)
print(root_nodes)

build_trace(root_nodes, edges)
# my_cluster_utils.py

from ast import Tuple
import os
# from tkinter.font import names
from kubernetes import client, config
from typing import List
from my_policy_interface import NodeInfo, PodInfo
from node_delay_measure_Parallel import measure_http_latency

class NodeInfo:
    """
    Example domain-specific structure for node information.
    Expand or modify as needed for your scheduling logic.
    """
    def __init__(self, node_name: str,
                 cpu_capacity: float,
                 mem_capacity: float,
                 current_cpu_usage: float,
                 current_mem_usage: float,
                 network_latency=None,
                 network_bandwidth=None):
        self.node_name = node_name
        self.cpu_capacity = cpu_capacity
        self.mem_capacity = mem_capacity
        self.current_cpu_usage = current_cpu_usage
        self.current_mem_usage = current_mem_usage
        # Optional dictionaries or placeholders for additional data
        self.network_latency = network_latency if network_latency else {}
        self.network_bandwidth = network_bandwidth if network_bandwidth else {}

class PodInfo:
    """
    Example domain-specific structure for pod information.
    """
    def __init__(self, pod_name: str,
                 cpu_req: float,
                 mem_req: float,
                 sla_latency_requirement: float,
                 deployment_name: str = None):
        self.pod_name = pod_name
        self.cpu_req = cpu_req
        self.mem_req = mem_req
        self.sla_latency_requirement = sla_latency_requirement
        self.deployment_name = deployment_name

def gather_all_nodes() -> List[client.V1Node]:
    """
    Gather all the Node objects from the Kubernetes cluster.
    Returns:
        A list of raw Kubernetes Node objects.
    """
    # Load config only once at your program entrypoint if possible,
    # or do in-cluster config if running inside the cluster:
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()

    v1 = client.CoreV1Api()
    raw_nodes = v1.list_node().items
    return raw_nodes

def gather_all_pods(namespace: str = None) -> List[client.V1Pod]:
    """
    Gather Pod objects from Kubernetes. If namespace is provided,
    returns pods from that namespace; otherwise returns pods across all namespaces.
    """
    try:
        config.load_incluster_config() # Load in-cluster config if available from a pod within the cluster
    except:
        config.load_kube_config()

    v1 = client.CoreV1Api()
    if namespace: # return Pods from a specific namespace
        raw_pods = v1.list_namespaced_pod(namespace).items
    else: # return Pods from all namespaces
        raw_pods = v1.list_pod_for_all_namespaces().items
    return raw_pods


def build_nodeinfo_objects(raw_nodes: List[client.V1Node]) -> List[NodeInfo]:
    """
    Convert raw Node objects to NodeInfo. You can adapt resource usage logic
    to your environment (e.g. using Metrics API, custom usage collectors, etc.)

    Args:
        raw_nodes: List of Kubernetes node objects.

    Returns:
        A list of NodeInfo objects containing relevant capacity/usage data.
    """
    nodeinfo_list = []

    # If you have a metrics server running, you could fetch live usage.
    # For simplicity, let's just read capacities from node.status.capacity
    # and set usage to 0 or some approximate value.
    # If you want to incorporate usage from metrics, see note below.
    for node in raw_nodes:
        node_name = node.metadata.name
        # print(f"node_name: {node_name}")
        
        # Example: parse CPU capacity in cores (converting from millicores if needed)
        # Node capacity might be 'cpu': '4', or '4000m' => 4 cores
        cpu_capacity_str = node.status.capacity.get('cpu', '0')
        if cpu_capacity_str.endswith('m'):
            cpu_capacity = float(cpu_capacity_str[:-1]) / 1000.0
        else:
            cpu_capacity = float(cpu_capacity_str)

        # Memory capacity might be Ki, Mi, Gi, etc. Let's assume Ki => convert to Mi
        mem_capacity_str = node.status.capacity.get('memory', '0')
        mem_capacity = _convert_memory_to_mebibytes(mem_capacity_str)

        # Usage can be fetched from metrics if desired:
          
        # PROMETHEUS Service URL and port; 
        # Option 1: Find with command "kuebctl get svc -A"; prom_url = "http://<cluster-ip>:<port>" = "http://10.105.116.175:9090"
        # OPtion 2: use the provided following function " prom_url = find_prometheus_url_in_all_namespaces() "
        current_cpu_usage, current_mem_usage = fetch_live_node_usage_prometheus(node_name=node_name, prom_url="http://10.105.116.175:9090") 
        # for easier calculation, make the cpu_usage and mem_usage as float with two decimal points
        current_cpu_usage = math.ceil(current_cpu_usage * 100) / 100
        current_mem_usage = math.ceil(current_mem_usage * 100) / 100
        
        # get the network latency and bandwidth
        latency_results = measure_http_latency(namespace='measure-nodes')
        _network_latency_ = get_latency_to_other_nodes(latency_results, node_name)

        # Build the NodeInfo object
        node_info = NodeInfo(
            node_name=node_name,
            cpu_capacity=cpu_capacity,
            mem_capacity=mem_capacity,
            current_cpu_usage=current_cpu_usage,
            current_mem_usage=current_mem_usage,
            network_latency=_network_latency_,     # Populate later if you have latency data
            network_bandwidth={}    # Populate later if you have bandwidth data
        )
        nodeinfo_list.append(node_info)

    return nodeinfo_list

def build_podinfo_objects(raw_pods: List[client.V1Pod]) -> List[PodInfo]:
    """
    Convert raw Pod objects into PodInfo. 
    For CPU/Memory requests, parse from pod.spec.containers[].resources.requests.

    Args:
        raw_pods: List of Kubernetes Pod objects.

    Returns:
        A list of PodInfo objects with relevant fields for scheduling.
    """
    podinfo_list = []

    for pod in raw_pods:
        pod_name = pod.metadata.name

        # For simplicity, sum up CPU/memory requests across all containers in the Pod
        total_cpu_req = 0.0
        total_mem_req = 0.0

        if pod.spec and pod.spec.containers:
            for container in pod.spec.containers:
                requests = container.resources.requests
                if requests:
                    # CPU
                    cpu_req_str = requests.get('cpu', '0')
                    total_cpu_req += _parse_cpu_request(cpu_req_str)
                    # Memory
                    mem_req_str = requests.get('memory', '0')
                    total_mem_req += _convert_memory_to_mebibytes(mem_req_str)

        # Suppose we store the Deployment name for reference:
        deployment_name = _extract_deployment_from_pod(pod)

        # If your system has an SLA or desired latency requirement:
        # You could store it in an annotation, or pass it in from somewhere else.
        # We'll just use a placeholder of 200 ms for now.
        sla_latency_requirement = 200.0 # can be changed as needed

        pod_info = PodInfo(
            pod_name=pod_name,
            cpu_req=total_cpu_req,
            mem_req=total_mem_req,
            sla_latency_requirement=sla_latency_requirement,
            deployment_name=deployment_name
        )
        podinfo_list.append(pod_info)

    return podinfo_list

from typing import Tuple # different from "from ast import Tuple", which is used for type hints, not for returning a tuple
from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
import math

# the 'live' is the recent last 5 minutes usage data. 'live' is not the real-time usage data here.
# 5 min is configured and can be changed in the following function
def fetch_live_node_usage_prometheus(node_name: str,
                                     prom_url: str = "http://localhost:9090") -> Tuple[float, float]: # NEED to specify the node name and prometheus urls
    """
    Fetch approximate CPU usage (in cores) and memory usage (in MiB) for a node
    from Prometheus using typical node_exporter metrics. 
    """
    prom = PrometheusConnect(url=prom_url, disable_ssl=True)

    # 1. Build a time range for the query. We query the rate at "now"
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=5)  # 5-min window

    # 2. CPU Usage Query
    #
    # Here’s a typical pattern:
    #   100 * (1 - avg by(instance) (rate(node_cpu_seconds_total{mode="idle",instance="<node>:..."}[5m])))
    # if using IP addresses, you can use "instance=~'<Node_ip>:.*'"
    # if using node names, you can use "node=~'<node_host_name>:.*'"
    # That yields a percentage of CPU usage. We'll convert it to fractional cores 
    # by multiplying by the node’s CPU count or by using a different formula.
    #
    # Alternatively, if you want total CPU usage in cores:
    #   sum by (instance) (rate(node_cpu_seconds_total{mode!="idle",instance="<node>"}[5m]))
    #
    # For demonstration, let's do the sum of all non-idle cores usage:
    cpu_query = f'''
      sum by (instance) (
        rate(node_cpu_seconds_total{{mode!="idle", node=~"{node_name}.*"}}[5m])
      )
    '''
    # The instance label often looks like "ip:9100" or "node_name:9100". Adjust as needed.

    cpu_data = prom.custom_query_range(
        query=cpu_query,
        start_time=start_time,
        end_time=end_time,
        step="30s" # 30s resolution
    )

    cpu_usage_cores = 0.0
    if cpu_data:
        # Usually, you'll get a list of results. Let's take the last value from the first result.
        values = cpu_data[0]['values']  # array of [timestamp, value]
        if values:
            # take the most recent data point
            _, val_str = values[-1]
            cpu_usage_cores = float(val_str)  # e.g. "2.3" -> 2.3 cores

    # 3. Memory Usage Query
    #
    # A typical node_exporter metric is node_memory_MemTotal_bytes and node_memory_MemAvailable_bytes.
    # You can compute used = total - available. We'll do that for the node, then convert to MiB.
    mem_query = f'''
      node_memory_MemTotal_bytes{{node=~"{node_name}.*"}}
      -
      node_memory_MemAvailable_bytes{{node=~"{node_name}.*"}}
    '''
    mem_data = prom.custom_query_range(
        query=mem_query,
        start_time=start_time,
        end_time=end_time,
        step="30s"
    )

    mem_usage_mib = 0.0
    if mem_data:
        values = mem_data[0]['values']
        if values:
            _, val_str = values[-1]
            used_bytes = float(val_str)
            mem_usage_mib = used_bytes / (1024.0 * 1024.0)

    return (cpu_usage_cores, mem_usage_mib)
# Example of using the above fetch_live_node_usage_prometheus function:
# node_name = "k8s-worker-1"
# prom_url = "http://10.105.116.175:9090"
# cpu_usage, mem_usage = fetch_live_node_usage_prometheus(node_name, prom_url=prom_url)
# print(f"Node {node_name} => CPU usage: {cpu_usage:.2f} cores, Memory usage: {mem_usage:.1f} MiB")


def get_latency_to_other_nodes(latency_results: dict, source_node_name: str) -> dict:
    
    """
    Given a dictionary containing latency measurements between nodes,
    and a source node name, return a dictionary of the latencies from
    the source node to other nodes.

    :param latency_results: A nested dictionary mapping:
                           { source_node: { destination_node: latency_value, ... }, ... }
    this parameter is the result of the function "measure_http_latency(namespace='measure-nodes')"
    
    :param source_node_name: The name of the node from which latencies to other nodes are requested.
    :return: A dictionary of { destination_node: latency_value } for the specified source node.
             Excludes the source node itself.
    """
    # Retrieve the dictionary of latencies for the source node (or an empty dict if not found)
    source_latencies = latency_results.get(source_node_name, {})

    # Filter out the entry for the source node itself
    return {
        dst_node: latency
        for dst_node, latency in source_latencies.items()
        if dst_node != source_node_name
    }



# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def _extract_deployment_from_pod(pod: client.V1Pod) -> str:
    """
    If a pod is controlled by a ReplicaSet, which is in turn controlled by a Deployment,
    return the deployment name; otherwise return None.
    """
    if not pod.metadata.owner_references:
        return None
    apps_v1 = client.AppsV1Api()
    for owner_ref in pod.metadata.owner_references:
        if owner_ref.kind == "ReplicaSet":
            replicaset_name = owner_ref.name
            # Retrieve the replicaset to see if it references a deployment
            try:
                rs = apps_v1.read_namespaced_replica_set(replicaset_name, pod.metadata.namespace)
                if rs.metadata.owner_references:
                    for rs_owner_ref in rs.metadata.owner_references:
                        if rs_owner_ref.kind == "Deployment":
                            return rs_owner_ref.name
            except:
                pass
    return None

def _parse_cpu_request(cpu_req_str: str) -> float:
    """
    Parse CPU request strings like '250m', '1', '2.5', etc. into float cores.
    """
    if cpu_req_str.endswith('m'):
        return float(cpu_req_str[:-1]) / 1000.0
    else:
        return float(cpu_req_str)

def _convert_memory_to_mebibytes(mem_str: str) -> float:
    """
    Handle memory strings like '512Mi', '1Gi', '1000Ki', etc.
    Return a float for memory in Mi (Mebibytes).
    """
    # Common K8s notation: Ki, Mi, Gi, etc.
    # A rough approach is to parse out the numeric portion and scale accordingly.
    # For example: '512Mi' => 512, '1Gi' => 1024, '1000Ki' => 1000 / 1024 => ~0.98Mi.
    # or '2G' => might parse as 2048
    # We'll keep it simple:
    #   1 Ki = 1/1024 Mi
    #   1 Mi = 1 Mi
    #   1 Gi = 1024 Mi
    #   1 Ti = 1048576 Mi, etc.
    if not mem_str:
        return 0

    mem_str = mem_str.strip()
    number_part = ''
    unit_part = ''

    # Separate numeric from alpha characters
    for ch in mem_str:
        if ch.isdigit() or ch == '.':
            number_part += ch
        else:
            unit_part += ch

    if not number_part:
        return 0

    val = float(number_part)

    unit_part = unit_part.lower()
    if 'ki' in unit_part:
        return val / 1024.0
    elif 'mi' in unit_part:
        return val
    elif 'gi' in unit_part:
        return val * 1024.0
    elif 'ti' in unit_part:
        return val * 1024.0 * 1024.0
    elif 'k' in unit_part:  # plain 'k' might appear
        return val / 1024.0
    elif 'm' in unit_part:  # plain 'm'? Rare for memory, but let's just do a pass
        return val  # or interpret differently if you want
    elif 'g' in unit_part:
        return val * 1024.0
    # If no recognized suffix, assume it's bytes => convert to Mi
    # e.g., "524288000" bytes => ~500 Mi
    return val / (1024.0 * 1024.0)


from kubernetes import client, config

def find_prometheus_url_in_all_namespaces():
    """
    Searches all namespaces for a Service whose name includes 'prometheus'.
    Returns a single URL string like 'http://<cluster-ip>:<port>' for the first match,
    or None if not found.
    """
    # Load kube config (for local) or in-cluster config (if running in a Pod).
    # Typically, you'd do one or the other depending on your environment.
    try:
        config.load_kube_config()  # Use local ~/.kube/config
    except:
        config.load_incluster_config()  # If the script is running inside the cluster

    # Initialize the CoreV1 API
    v1 = client.CoreV1Api()

    # List all services in all namespaces
    all_services = v1.list_service_for_all_namespaces()

    # Look for a service name containing 'prometheus'
    for svc in all_services.items:
        svc_name = svc.metadata.name.lower()
        if 'prometheus' in svc_name:
            # Found a potential Prometheus service
            cluster_ip = svc.spec.cluster_ip  # e.g., 10.105.116.175
            if not cluster_ip or cluster_ip == "None":
                # e.g. headless service that doesn't have a ClusterIP
                continue

            # If there's at least one port, pick the first
            if not svc.spec.ports:
                continue
            port = svc.spec.ports[0].port  # e.g. 9090

            # Return the first valid match
            #print(f"Prometheus URL found: {url}")
            return f"http://{cluster_ip}:{port}"

    # If no matching service was found, return None
    print("No Prometheus service found in any namespace.")
    return None
# url = find_prometheus_url_in_all_namespaces()
# if url:
#     print(f"Prometheus URL found: {url}")
# else:
#     print("No Prometheus service found in any namespace.")
results = measure_http_latency(namespace='measure-nodes')
print(results)
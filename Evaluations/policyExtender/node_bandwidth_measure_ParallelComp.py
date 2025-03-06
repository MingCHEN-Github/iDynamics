'''Deploy cross-node bandwidth measurement pods'''

from kubernetes import client, config

def check_pods_existence(namespace):
    core_v1 = client.CoreV1Api()
    try:
        pods = core_v1.list_namespaced_pod(namespace=namespace)
        return len(pods.items) > 0  # return True if pods exist
    except client.rest.ApiException as e:
        print(f"Exception when calling CoreV1Api->list_namespaced_pod: {e}")
        return False

def deploy_bandwidth_measurement_daemonset_if_needed():
    namespace = 'measure-nodes-bd'
    ds_name = 'bandwidth-measurement-ds'
    
    # Load Kubernetes configuration
    config.load_kube_config()
    apps_v1 = client.AppsV1Api()

    # Check if pods exist in the namespace
    pods_exist = check_pods_existence(namespace)

    # If no pods exist, deploy the DaemonSet
    if not pods_exist:
        # Define the body of the DaemonSet for `iperf3` server deployment
        ds_body = client.V1DaemonSet(
            api_version="apps/v1",
            kind="DaemonSet",
            metadata=client.V1ObjectMeta(name=ds_name),
            spec=client.V1DaemonSetSpec(
                selector=client.V1LabelSelector(
                    match_labels={"app": "bandwidth-measurement"}
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": "bandwidth-measurement"}),
                    spec=client.V1PodSpec(
                        containers=[client.V1Container(
                            name="iperf3-server",
                            image="networkstatic/iperf3",
                            args=["-s"],  # Run in server mode
                            ports=[client.V1ContainerPort(container_port=5201)]
                        )],
                        restart_policy="Always"
                    )
                )
            )
        )

        # Deploy the DaemonSet
        try:
            apps_v1.create_namespaced_daemon_set(namespace=namespace, body=ds_body)
            print(f"Deployed DaemonSet {ds_name} in namespace {namespace}")
        except client.rest.ApiException as e:
            print(f"Exception when calling AppsV1Api->create_namespaced_daemon_set: {e}")
    else:
        print("Pods already exist in the namespace. Skipping DaemonSet deployment.")

# Call the function to deploy the DaemonSet if needed
# deploy_bandwidth_measurement_daemonset_if_needed()

import re
from kubernetes import client, config, stream
import concurrent.futures
import time

# Load Kubernetes configuration
# config.load_kube_config()
# v1 = client.CoreV1Api()

# Function to measure bandwidth between source and target pods with retries
def measure_bandwidth_from_source_to_target(v1, namespace, source_pod, target_pod, test_duration=5, max_retries=3):
    source_pod_name = source_pod.metadata.name
    source_pod_node_name = source_pod.spec.node_name
    target_pod_ip = target_pod.status.pod_ip
    target_pod_name = target_pod.metadata.name
    target_pod_node_name = target_pod.spec.node_name
    result = (source_pod_node_name, target_pod_node_name, None)

    if source_pod_name != target_pod_name:
        exec_command = ['iperf3', '-c', target_pod_ip, '-t', str(test_duration)]
        attempts = 0

        while attempts < max_retries:
            try:
                # Run iperf3 command
                resp = stream.stream(v1.connect_get_namespaced_pod_exec,
                                     source_pod_name,
                                     namespace,
                                     command=exec_command,
                                     stderr=True,
                                     stdin=False,
                                     stdout=True,
                                     tty=False)

                # Check for "server is busy" in the output
                if "the server is busy" in resp:
                    print(f"Server is busy for connection from {source_pod_name} to {target_pod_name}. Retrying...")
                    attempts += 1
                    time.sleep(test_duration/2)  # Wait before retrying
                    continue

                # Parse the output for bandwidth
                # print(f"Full output from {source_pod_name} to {target_pod_name}:\n{resp}")
                
                match = re.search(r'(\d+\.?\d*\s[MKG]bits/sec)', resp)
                if match:
                    bandwidth = match.group(1)
                    result = (source_pod_node_name, target_pod_node_name, bandwidth)
                    # print(f"Bandwidth from {source_pod_node_name} to {target_pod_node_name}: {bandwidth}")
                else:
                    print(f"Could not extract bandwidth for connection from {source_pod_name} to {target_pod_name}.")
                    result = (source_pod_node_name, target_pod_node_name, "Parsing Error")
                break  # Exit loop on success

            except Exception as e:
                print(f"Error executing command in pod {source_pod_name}: {e}")
                result = (source_pod_node_name, target_pod_node_name, "Error")
                break

        if attempts == max_retries:
            print(f"Max retries reached for connection from {source_pod_name} to {target_pod_name}.")
            result = (source_pod_node_name, target_pod_node_name, "Server Busy Error")

    return result

def measure_bandwidth(namespace='measure-nodes-bd', max_concurrent_tasks=3, test_duration=5):
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace, label_selector="app=bandwidth-measurement").items
    bandwidth_results = {}

    # Use ThreadPoolExecutor for controlled concurrent execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
        futures = []
        for source_pod in pods:
            for target_pod in pods:
                if source_pod.metadata.name != target_pod.metadata.name:  # Skip self-tests
                    futures.append(executor.submit(measure_bandwidth_from_source_to_target,
                                                   v1, namespace, source_pod, target_pod, test_duration))

        # Collect the completed results
        for future in concurrent.futures.as_completed(futures):
            source_pod_node_name, target_pod_node_name, bandwidth = future.result()
            if source_pod_node_name not in bandwidth_results:
                bandwidth_results[source_pod_node_name] = {}
            bandwidth_results[source_pod_node_name][target_pod_node_name] = bandwidth

    return bandwidth_results

# Call the function to measure bandwidth after deploying the DaemonSet
# namespace = 'measure-nodes-bd'
# # Reduced concurrency and added retry logic
# bandwidth_results = measure_bandwidth(namespace=namespace, max_concurrent_tasks=3, test_duration=10)
# print(bandwidth_results)

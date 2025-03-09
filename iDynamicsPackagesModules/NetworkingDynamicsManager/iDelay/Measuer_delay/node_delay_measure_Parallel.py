'''Deploy cross-node communication measuring pods'''

from kubernetes import client, config

def check_pods_existence(namespace):
    core_v1 = client.CoreV1Api()
    try:
        pods = core_v1.list_namespaced_pod(namespace=namespace)
        return len(pods.items) > 0 # return True
    except client.rest.ApiException as e:
        print(f"Exception when calling CoreV1Api->list_namespaced_pod: {e}")
        return False

def deploy_latency_measurement_daemonset_if_needed():
    namespace = 'measure-nodes'
    ds_name = 'latency-measurement-ds'
    
    # Assuming config and apps_v1 have been defined as before
    config.load_kube_config()
    apps_v1 = client.AppsV1Api()

    # Check if pods exist in the namespace
    pods_exist = check_pods_existence(namespace)

    # If no pods exist, deploy the DaemonSet
    if not pods_exist:
        # Define the body of the DaemonSet
        ds_body = client.V1DaemonSet(
            api_version="apps/v1",
            kind="DaemonSet",
            metadata=client.V1ObjectMeta(name=ds_name),
            spec=client.V1DaemonSetSpec(
                selector=client.V1LabelSelector(
                    match_labels={"app": "latency-measurement"}
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": "latency-measurement"}),
                    spec=client.V1PodSpec(
                        containers=[client.V1Container(
                            name="latency-container",
                            image="curlimages/curl",
                            security_context=client.V1SecurityContext(
                                capabilities=client.V1Capabilities(
                                    add=["NET_RAW"]  # Required for ping
                                )
                            )
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
deploy_latency_measurement_daemonset_if_needed()


'''As there are network jitter sometimes, means soemtimes sudden rise for a signle measurement:
To sovle this measuring issue:
(1) a easy and simple way to do is just the choose the lowest measured vaule to represent the latency 
between the measured node pair.
(2) another way, that can do is to meaured more vaules (like meaure 20 times), and use the 80% percentile as
the latency.

'''

from kubernetes import client, config, stream
import concurrent.futures

# Handle individual latency measurements between source and target pods.
def measure_latency_from_source_to_target(v1, namespace, source_pod, target_pod):
    source_pod_name = source_pod.metadata.name
    source_pod_node_name = source_pod.spec.node_name
    target_pod_ip = target_pod.status.pod_ip
    target_pod_name = target_pod.metadata.name
    target_pod_node_name = target_pod.spec.node_name
    result = (source_pod_node_name, target_pod_node_name, None)

    if source_pod_name != target_pod_name:
        exec_command = ['curl', '-o', '/dev/null', '-s', '-w', '%{time_total}', f'http://{target_pod_ip}']
        latencies = []
        for _ in range(5):
            try:
                resp = stream.stream(v1.connect_get_namespaced_pod_exec,
                                     source_pod_name,
                                     namespace,
                                     command=exec_command,
                                     stderr=True,
                                     stdin=False,
                                     stdout=True,
                                     tty=False)
                latency = float(resp) * 1000  # Convert the measured seconds into milliseconds
                latencies.append(latency)
            except Exception as e:
                print(f"Error executing command in pod {source_pod_name}: {e}")
        
        if latencies:
            min_latency = min(latencies) #choose the lowest measured vaule to represent the latency
            result = (source_pod_node_name, target_pod_node_name, min_latency)
            print(f"Latency from source node {source_pod_node_name} to target node {target_pod_node_name}: {min_latency} milliseconds")
        else:
            result = (source_pod_node_name, target_pod_node_name, "Error")

    return result

def measure_http_latency(namespace='measure-nodes'):
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace, label_selector="app=latency-measurement").items
    latency_results = {}
    
    # Run the latency measurement tasks concurrently
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for source_pod in pods:
            for target_pod in pods:
                futures.append(executor.submit(measure_latency_from_source_to_target, v1, namespace, source_pod, target_pod))
        
        # Aggregate the completed results into the latency_results dictionary
        for future in concurrent.futures.as_completed(futures):
            source_pod_node_name, target_pod_node_name, latency = future.result()
            if source_pod_node_name not in latency_results:
                latency_results[source_pod_node_name] = {}
            latency_results[source_pod_node_name][target_pod_node_name] = latency

    return latency_results

# Call the function to measure latency after deploying the DaemonSet
namespace = 'measure-nodes'
# After the DaemonSet is ready, and the related pods are ready
latency_results = measure_http_latency(namespace=namespace)
print(latency_results)

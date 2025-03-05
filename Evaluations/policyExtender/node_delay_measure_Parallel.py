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
            # print(f"Latency from source node {source_pod_node_name} to target node {target_pod_node_name}: {min_latency} milliseconds")
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
# namespace = 'measure-nodes'
# # After the DaemonSet is ready, and the related pods are ready
# latency_results = measure_http_latency(namespace=namespace)
# print(latency_results)
'''Latency results will be like:
latency_results = {
    'k8s-worker-3': {'k8s-worker-3': None, 'k8s-worker-9': 3.6470000000000002, 'k8s-worker-7': 3.613, 'k8s-worker-6': 8.477, 'k8s-worker-5': 4.726, 'k8s-worker-4': 2.6029999999999998, 'k8s-worker-1': 0.434, 'k8s-worker-2': 9.785, 'k8s-worker-8': 16.631},
    'k8s-worker-6': {'k8s-worker-6': None, 'k8s-worker-5': 10.571, 'k8s-worker-3': 8.504, 'k8s-worker-7': 13.501000000000001, 'k8s-worker-4': 18.779, 'k8s-worker-9': 15.601, 'k8s-worker-1': 7.571, 'k8s-worker-8': 10.734, 'k8s-worker-2': 23.711},
    'k8s-worker-9': {'k8s-worker-9': None, 'k8s-worker-3': 3.677, 'k8s-worker-4': 15.834999999999999, 'k8s-worker-5': 19.834999999999997, 'k8s-worker-8': 7.711, 'k8s-worker-7': 11.684999999999999, 'k8s-worker-1': 3.574, 'k8s-worker-2': 11.684, 'k8s-worker-6': 15.665999999999999},
    'k8s-worker-7': {'k8s-worker-7': None, 'k8s-worker-1': 6.423, 'k8s-worker-5': 11.564, 'k8s-worker-3': 3.554, 'k8s-worker-6': 13.603, 'k8s-worker-2': 16.726000000000003, 'k8s-worker-9': 11.609, 'k8s-worker-4': 15.443, 'k8s-worker-8': 18.721},
    'k8s-worker-5': {'k8s-worker-5': None, 'k8s-worker-9': 19.84, 'k8s-worker-3': 4.657, 'k8s-worker-7': 11.491, 'k8s-worker-2': 11.66, 'k8s-worker-1': 5.569, 'k8s-worker-6': 10.7, 'k8s-worker-8': 13.703999999999999, 'k8s-worker-4': 6.581},
    'k8s-worker-1': {'k8s-worker-1': None, 'k8s-worker-9': 3.646, 'k8s-worker-3': 0.49700000000000005, 'k8s-worker-7': 6.472, 'k8s-worker-6': 7.550000000000001, 'k8s-worker-5': 5.472, 'k8s-worker-2': 5.599, 'k8s-worker-4': 11.704, 'k8s-worker-8': 30.546},
    'k8s-worker-2': {'k8s-worker-2': None, 'k8s-worker-1': 5.597, 'k8s-worker-3': 9.58, 'k8s-worker-5': 11.647, 'k8s-worker-9': 11.917, 'k8s-worker-6': 23.654999999999998, 'k8s-worker-4': 12.67, 'k8s-worker-7': 16.677, 'k8s-worker-8': 39.675000000000004},
    'k8s-worker-8': {'k8s-worker-8': None, 'k8s-worker-6': 10.678, 'k8s-worker-3': 16.924000000000003, 'k8s-worker-9': 7.979, 'k8s-worker-7': 18.68, 'k8s-worker-5': 13.747, 'k8s-worker-1': 30.576, 'k8s-worker-4': 20.668, 'k8s-worker-2': 39.684},
    'k8s-worker-4': {'k8s-worker-4': None, 'k8s-worker-3': 2.71, 'k8s-worker-5': 6.644, 'k8s-worker-7': 15.691, 'k8s-worker-9': 15.970999999999998, 'k8s-worker-2': 12.761, 'k8s-worker-8': 20.767, 'k8s-worker-1': 11.724, 'k8s-worker-6': 18.787000000000003}
}
'''
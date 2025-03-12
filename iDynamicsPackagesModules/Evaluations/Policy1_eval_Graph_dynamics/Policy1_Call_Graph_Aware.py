from kubernetes import client, config
from prometheus_api_client import PrometheusConnect
import time
import multiprocessing as mp
import concurrent.futures

from typing import List, Dict, Tuple
from datetime import datetime, timedelta

from iDynamicsPackagesModules.GraphDynamicsAnalyzer  import graph_builder
from iDynamicsPackagesModules.SchedulingPolicyExtender.my_policy_interface import AbstractSchedulingPolicy, NodeInfo, PodInfo, SchedulingDecision
from iDynamicsPackagesModules.SchedulingPolicyExtender.my_cluster_utils import gather_all_nodes, gather_all_pods, build_nodeinfo_objects, build_podinfo_objects, _extract_deployment_from_pod

########################################################################
# Policy1: Call-Graph–Aware Scheduling
########################################################################
class Policy1CallGraphAware(AbstractSchedulingPolicy):
    """
    Policy1:
    - Good at scenario with call-graph dynamics (Request A, B, C, etc.),
      so we want to collocate heavily communicating microservices.
    - We'll use a 'traffic_matrix' from an external source
      (e.g. from graph_builder.py) to guide microservice placements.
    """

    def __init__(self):
        super().__init__()
        self.traffic_matrix = {}  # (serviceA, serviceB) -> traffic volume

    def initialize_policy(self, dynamics_config: dict, 
                          prom_url: str, 
                          qos_target: int, #QoS target for average response time in milliseconds
                          time_window: int, 
                          namespace: str, 
                          response_code='200') -> None:
        """
        Load or prepare a call graph or traffic matrix from 'dynamics_config'.
        Example: config["traffic_matrix"] could be a dict:
            {("serviceA", "serviceB"): 1000, ...}
        """
         # Kubernetes Config
        config.load_kube_config()
        self.v1 = client.CoreV1Api()

        # Prometheus Config
        self.prom = PrometheusConnect(url=prom_url, disable_ssl=True)
        self.qos_target = qos_target # QoS target for average response time in milliseconds
        self.time_window = time_window
        self.namespace = namespace
        self.response_code = response_code # default code is 200 (success); can be changed to 500 (error)
        
        self.traffic_matrix = dynamics_config.get("traffic_matrix", {})
    
    def trigger_migration(self):
        """
        Determine if migration should be triggered based on SLA (eg., QoS targets) and time window.
        """
        trigger = False
        step = str(self.time_window * 60)  # Step size in seconds for Prometheus queries

        # Prometheus queries for Istio metrics
        istio_request_duration_query = f'rate(istio_request_duration_milliseconds_sum{{namespace="{self.namespace}", response_code="{self.response_code}"}}[{self.time_window}m])'
        istio_requests_total_query = f'rate(istio_requests_total{{namespace="{self.namespace}", response_code="{self.response_code}"}}[{self.time_window}m])'

        # Define the time range for the query
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=self.time_window)

        # Fetch the data from Prometheus
        istio_request_duration_response = self.prom.custom_query_range(
            query=istio_request_duration_query,
            start_time=start_time,
            end_time=end_time,
            step=step
        )
        istio_requests_total_response = self.prom.custom_query_range(
            query=istio_requests_total_query,
            start_time=start_time,
            end_time=end_time,
            step=step
        )

        # Ensure there is data to process
        if istio_request_duration_response and istio_requests_total_response:
            duration_values = [float(val[1]) for val in istio_request_duration_response[0]['values']]
            total_requests_values = [float(val[1]) for val in istio_requests_total_response[0]['values']]

            if total_requests_values and duration_values:
                # Compute the average response time in milliseconds
                total_requests_sum = sum(total_requests_values)
                if total_requests_sum > 0:
                    average_response_time = sum(duration_values) / total_requests_sum
                    print(f"Average response time = {average_response_time:.2f} ms")

                    # Check if the average response time exceeds the QoS target
                    if average_response_time > self.qos_target:
                        trigger = True
                else:
                    print("Total requests sum is zero, cannot compute average response time.")
            else:
                print("No traffic detected, no trigger.")
        else:
            print("Query returned no data, no trigger.")

        print(f"Trigger = {trigger}")

        return trigger

    def schedule_pod(self, pod: PodInfo, candidate_nodes: List[NodeInfo]) -> SchedulingDecision:
        """
        Simple single-pod scheduling: 
        pick the node with the most free CPU for demonstration,
        or might choose a more advanced logic (co-locate with related pods).
        """
        best_node = None
        best_free_cpu = -1

        for node in candidate_nodes:
            free_cpu = node.cpu_capacity - node.current_cpu_usage
            if free_cpu > best_free_cpu:
                best_free_cpu = free_cpu
                best_node = node

        return SchedulingDecision(pod_name=pod.pod_name, selected_node=best_node.node_name)

    def schedule_all(self, pods: List[PodInfo], candidate_nodes: List[NodeInfo]) -> List[SchedulingDecision]:
        """
        Batch scheduling approach:
        1. We want to place heavily communicating pairs on the same node if feasible.
        2. 'traffic_matrix' is a dict with traffic volumes between pairs (podA, podB).
        3. We attempt to co-locate the top-k highest traffic pairs.
        """
        # We'll need usage info on each node as we place pods
        node_allocations = {node.node_name: [] for node in candidate_nodes}  # track which pods are on each node

        # For quick lookups, assume each pod's CPU is small enough that we rarely conflict,
        # but you can do a real capacity check.
        # Let's build a dict to store each pod's CPU requirement for easy reference.
        pod_cpu_req = {p.pod_name: p.cpu_req for p in pods}

        # Convert traffic_matrix to a list of ((podA, podB), traffic), sorted in descending order
        traffic_list = sorted(self.traffic_matrix.items(), key=lambda x: x[1], reverse=True)

        placed_pods = set()

        for (podA, podB), traffic_val in traffic_list:
            # if these pods are in the set of pods to schedule:
            if podA not in pod_cpu_req or podB not in pod_cpu_req:
                continue

            # if both unplaced, try to co-locate them
            if (podA not in placed_pods) and (podB not in placed_pods):
                best_node_for_pair = None
                best_free_cpu = -1
                for node in candidate_nodes:
                    current_cpu_usage_on_node = sum(pod_cpu_req[pn] for pn in node_allocations[node.node_name])
                    free_cpu_here = node.cpu_capacity - current_cpu_usage_on_node
                    
                    # to make sure that the two pods can be placed on the same node
                    # more strict condition can be used, e.g.,
                    free_cpu_here = 0.5*free_cpu_here 

                    # if we can place both
                    if free_cpu_here >= (pod_cpu_req[podA] + pod_cpu_req[podB]) > best_free_cpu:
                        best_free_cpu = free_cpu_here
                        best_node_for_pair = node

                if best_node_for_pair:
                    node_allocations[best_node_for_pair.node_name].append(podA)
                    node_allocations[best_node_for_pair.node_name].append(podB)
                    placed_pods.add(podA)
                    placed_pods.add(podB)

        # place any unplaced pods individually
        for pod in pods: # pod includes the attributes of 'pod_nmae' and corresponding 'deployment_name'
            if pod.pod_name in placed_pods:
                continue
            best_node = None
            best_free_cpu = -1
            for node in candidate_nodes:
                current_cpu_usage_on_node = sum(pod_cpu_req[pn] for pn in node_allocations[node.node_name])
                free_cpu_here = node.cpu_capacity - current_cpu_usage_on_node
                if (free_cpu_here >= pod_cpu_req[pod.pod_name]) and (free_cpu_here > best_free_cpu):
                    best_free_cpu = free_cpu_here
                    best_node = node

            if best_node:
                node_allocations[best_node.node_name].append(pod.pod_name)
                placed_pods.add(pod.pod_name)
            else:
                # fallback: place on node with largest free CPU
                fallback = max(candidate_nodes, key=lambda nd: nd.cpu_capacity - sum(pod_cpu_req[pn] for pn in node_allocations[nd.node_name]))
                node_allocations[fallback.node_name].append(pod.pod_name)
                placed_pods.add(pod.pod_name)

        # build SchedulingDecisions
        decisions = []
        for node_name, pod_list in node_allocations.items():
            for p_name in pod_list:
                # dec_microservice = _extract_deployment_from_pod(p_name)
                decisions.append(SchedulingDecision(pod_name=p_name, selected_node=node_name))

        return decisions

    def on_update_metrics(self, app_namespace = "social-network") -> None:
        """
        If traffic patterns changed because we switched from Request A to Request B, etc.,
        we could re-build or reload the traffic matrix here using graph_builder.
        """
        # 1. Re-build the call graph (you might need to parameterize the namespace or other parameters).
        #    For example, if your microservices run in a namespace named "social-network":
        G = graph_builder.build_call_graph(namespace=app_namespace)

        # 2. Convert the resulting NetworkX DiGraph into a new traffic_matrix.
        #    Each edge in G has a "weight" attribute (KB/s, bytes, or some traffic unit).
        #    For example, (u, v, data) => data["weight"] is the traffic from u to v.
        new_traffic_matrix = {}
        for u, v, data in G.edges(data=True):
            if "weight" in data:
                new_traffic_matrix[(u, v)] = data["weight"]  # store the numeric traffic volume

        # 3. Replace our old traffic matrix with the newly built one
        self.traffic_matrix = new_traffic_matrix

        # Optionally, log or print for debugging
        print(f"[Policy1CallGraphAware] Updated traffic matrix for app in namespace {app_namespace} with {len(self.traffic_matrix)} edges.")
        
       
    #### Helper Functions (Begin) #### 
    def exclude_non_App_ms(self, migrations, microservice_names, exclude_deployments=['jager']):
        """
        Exclude non-application microservices from the pod migration/scheduling list.
        eg., exclude deployments like 'jaeger', 'nginx', etc.
        """
        excluded_indices = {index for index, name in enumerate(microservice_names) if name in exclude_deployments}
        return [(ms, initial, final) for ms, initial, final in migrations if ms not in excluded_indices]
    
    def patch_deployment(self, deployment_name, new_node_name):
        """
        Patch the deployment to use a specific node.
        """
        body = {
            "spec": {
                "template": {
                    "spec": {
                        "nodeSelector": {
                            "kubernetes.io/hostname": new_node_name
                        }
                    }
                }
            }
        }
        try:
            client.AppsV1Api().patch_namespaced_deployment(name=deployment_name, namespace=self.namespace, body=body)
            print(f"Deployment '{deployment_name}' patched to schedule pods on '{new_node_name}'.")
        except Exception as e:
            print(f"Failed to patch the deployment: {e}")
            return False
        return True
    
    def wait_for_rolling_update_to_complete(self, deployment_name, new_node_name):
        """
        Wait for the rolling update to complete.
        """
        print("Waiting for the rolling update to complete...")
        while True:
            pods = client.CoreV1Api().list_namespaced_pod(namespace=self.namespace, label_selector=f'app={deployment_name}').items
            all_pods_updated = all(pod.spec.node_name == new_node_name and pod.status.phase == 'Running' for pod in pods)
            print("all_pods_updated=", all_pods_updated)
            print("len(pods)=", len(pods))
            if all_pods_updated and len(pods) >= 0:
                print("All pods are running on the new node.")
                break
            else:
                print("Rolling update in progress...")
                time.sleep(5)
    
    def migrate_and_wait_for_update(self, deployment_name, new_node_name):
        """
        Handles the migration of a single microservice by patching the deployment and waiting for the rolling update.
        """
        # new_node_name = f'k8s-worker-{new_node_index}'
        print(f"Starting migration of {deployment_name} to {new_node_name}")

        # Patch the deployment to the new node
        if self.patch_deployment(deployment_name, new_node_name):
            # Wait for the rolling update to complete
            self.wait_for_rolling_update_to_complete(deployment_name, new_node_name)
            print(f"Microservice {deployment_name} migrated successfully to {new_node_name}.")
            return f"Migration of {deployment_name} to {new_node_name} completed."
        else:
            return f"Failed to migrate {deployment_name} to {new_node_name}."   
        
    #### Helper Functions (END) #### 

    def run(self):
        """
        This scheduler class is designed to be a runtime scheduler, which means it will be continuously running
        to monitor the deployed application in the given 'namespace' and take scheduling decisions once certain
        defined SLA (like QoS average response time) is violated to trigger scheduling decisions.
        Main function to run the scheduler.
        """
        if self.trigger_migration():
            # trigger migration (True or False)
            '''
            (1) Get the current state of the system
            (2) Run the scheduling algorithm.
            (3) Apply the scheduling decisions.
            '''
            #(1) Get the current state of the system, e.g., pods, nodes, metrics (prometheus, istio, jaeger).
            raw_nodes = gather_all_nodes()
            candidate_nodes = build_nodeinfo_objects(raw_nodes)
            # Gather and prepare pod data for policy1
            raw_pods_Policy1 = gather_all_pods(namespace=self.namespace)
            pods_Policy1 = build_podinfo_objects(raw_pods_Policy1)
            self.on_update_metrics(app_namespace=self.namespace)
            
            print("=== Scenario1: Call-Graph_Aware ===")
            #(2) Run the scheduling algorithm (single pod scheduling or batch pod scheduling or other customized).
            decisions_s1 = self.schedule_all(pods_Policy1, candidate_nodes) # pods managed by Policy1
            for dec in decisions_s1:
                # dec_microservice = _extract_deployment_from_pod(dec.pod_name)

                print(f" Pod {dec.pod_name} -> schedule to Node {dec.selected_node}")
            
            
            
            # Perform migrations concurrently using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for dec in decisions_s1:
                    
                    dec_microservice = _extract_deployment_from_pod(dec.pod_name)
                    future = executor.submit(self.migrate_and_wait_for_update, dec_microservice, dec.selected_node)
                    futures.append(future)

                # Wait for all futures to complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        print(f"Migration result: {result}")
                    except Exception as exc:
                        print(f"Generated an exception: {exc}")
            
        else:
            print("[Policy1CallGraphAware] No migration triggered.")

        # Optionally, update the traffic matrix based on the current call graph
        

        # Optionally, log or print for debugging
        # print("[Policy1CallGraphAware] Running the scheduler...")
        

print("Policy1CallGraphAware class defined.")

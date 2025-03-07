from typing import List, Dict, Tuple
import math

from llm_scheduling.llm_images_builder.backend_LLMs.bartLarge_backend import app
from policyExtender.my_policy_interface import AbstractSchedulingPolicy, NodeInfo, PodInfo, SchedulingDecision
import graph_builder


########################################################################
# Policy1: Call-Graph–Aware Scheduling
########################################################################
class Policy1CallGraphAware(AbstractSchedulingPolicy):
    """
    Policy1:
    - Good at scenario with call-graph dynamics (Request A, B, C, etc.),
      so we want to collocate heavily communicating microservices.
    - We'll use a 'traffic_matrix' or call graph from an external source
      (e.g. from graph_builder.py) to guide microservice placements.
    """

    def __init__(self):
        super().__init__()
        self.traffic_matrix = {}  # (serviceA, serviceB) -> traffic volume

    def initialize_policy(self, config: dict) -> None:
        """
        Load or prepare a call graph or traffic matrix from 'config'.
        Example: config["traffic_matrix"] could be a dict:
            {("serviceA", "serviceB"): 1000, ...}
        """
        self.traffic_matrix = config.get("traffic_matrix", {})

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
        for pod in pods:
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



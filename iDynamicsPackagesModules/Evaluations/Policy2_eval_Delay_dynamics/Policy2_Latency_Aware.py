from typing import List, Dict, Tuple
import math
from iDynamicsPackagesModules.SchedulingPolicyExtender.my_policy_interface import (
    AbstractSchedulingPolicy,
    NodeInfo,
    PodInfo,
    SchedulingDecision
)


########################################################################
# Policy2: Latency-Aware Scheduling
########################################################################
class Policy2LatencyAware(AbstractSchedulingPolicy):
    """
    Policy2:
    - Good at scenario with dynamically changing cross-node delays
    - Minimizes latency for pods that have strict latency requirements
    """

    def __init__(self):
        super().__init__()
        self.latency_threshold = 10.0

    def initialize_policy(self, dynamics_config: dict) -> None:
        """
        Possibly load a user-specified threshold or latency weighting factor from config.
        """
        self.latency_threshold = dynamics_config.get("latency_threshold", 10.0)

    def schedule_pod(self, pod: PodInfo, candidate_nodes: List[NodeInfo]) -> SchedulingDecision:
        """
        Single-pod scheduling:
        - Put the pod on the node that has the smallest average latency to the rest of the cluster
          OR we might specifically place the pod near certain critical pods.
        """
        best_node = None
        best_latency_val = float("inf")
        
        for node in candidate_nodes:
            # For demonstration, let's do "average" node->others latency
            lat_values = node.network_latency.values()
            avg_lat = sum(lat_values)/len(lat_values) if len(lat_values) > 0 else 0
            # Check capacity
            free_cpu = node.cpu_capacity - node.current_cpu_usage
            free_mem = node.mem_capacity - node.current_mem_usage
            
            # add more strict conditions, to avoid all pods are placed on the same node
            free_cpu = 0.5 * free_cpu
            free_mem = 0.5 * free_mem

            if (pod.cpu_req < free_cpu) and (pod.mem_req < free_mem) and (avg_lat < best_latency_val):
                best_latency_val = avg_lat
                best_node = node

        if not best_node:
            # fallback: pick the node with the smallest average latency ignoring capacity
            best_node = min(candidate_nodes, key=lambda n: sum(n.network_latency.values()) / (len(n.network_latency) or 1))

        return SchedulingDecision(pod_name=pod.pod_name, selected_node=best_node.node_name)

    def schedule_all(self, pods: List[PodInfo], candidate_nodes: List[NodeInfo]) -> List[SchedulingDecision]:
        """
        A simple approach:
        1) Sort pods by sla_latency_requirement ascending (most strict first).
        2) Assign them to the node with the lowest average latency that has enough capacity.
        """
        decisions = []
        
        # track usage
        node_usage_cpu = {n.node_name: n.current_cpu_usage for n in candidate_nodes}
        node_usage_mem = {n.node_name: n.current_mem_usage for n in candidate_nodes}

        # sort pods by SLA requirement
        pods_sorted = sorted(pods, key=lambda p: p.sla_latency_requirement)

        for pod in pods_sorted:
            best_node = None
            best_latency_val = float("inf")
            for node in candidate_nodes:
                lat_values = node.network_latency.values()
                avg_lat = sum(lat_values)/len(lat_values) if lat_values else 0
                free_cpu = node.cpu_capacity - node_usage_cpu[node.node_name]
                free_mem = node.mem_capacity - node_usage_mem[node.node_name]

                if (pod.cpu_req <= free_cpu) and (pod.mem_req <= free_mem) and (avg_lat < best_latency_val):
                    best_latency_val = avg_lat
                    best_node = node

            if best_node:
                node_usage_cpu[best_node.node_name] += pod.cpu_req
                node_usage_mem[best_node.node_name] += pod.mem_req
                decisions.append(SchedulingDecision(pod_name=pod.pod_name, selected_node=best_node.node_name))
            else:
                # fallback: pick node with smallest avg latency ignoring capacity
                fallback_node = min(candidate_nodes, key=lambda n: sum(n.network_latency.values()) / (len(n.network_latency) or 1))
                node_usage_cpu[fallback_node.node_name] += pod.cpu_req
                node_usage_mem[fallback_node.node_name] += pod.mem_req
                decisions.append(SchedulingDecision(pod_name=pod.pod_name, selected_node=fallback_node.node_name))

        return decisions

    def on_update_metrics(self, nodes: List[NodeInfo]) -> None:
        """
        Could re-calculate latencies or thresholds if needed. For now, do nothing.
        """
        pass



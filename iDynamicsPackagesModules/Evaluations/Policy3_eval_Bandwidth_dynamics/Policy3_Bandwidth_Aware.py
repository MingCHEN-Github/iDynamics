# Description: Policy3: Bandwidth-Aware Scheduling
from typing import List, Dict, Tuple
import math
from iDynamicsPackagesModules.SchedulingPolicyExtender.my_policy_interface import (
    AbstractSchedulingPolicy,
    NodeInfo,
    PodInfo,
    SchedulingDecision
)


########################################################################
# Policy3: Bandwidth-Aware Scheduling
########################################################################
class Policy3BandwidthAware(AbstractSchedulingPolicy):
    """
    Policy3:
    - Good at scenario with dynamically changing cross-node bandwidth
    - Tries to place pods that have high traffic demand on the highest-bandwidth links
    """

    def __init__(self):
        super().__init__()
        self.high_traffic_threshold = 200.0

    def initialize_policy(self, dynamics_config: dict) -> None:
        """
        Possibly load a user-specified threshold or weighting factor from config.
        """
        self.high_traffic_threshold = dynamics_config.get("high_traffic_threshold", 200.0)

    def schedule_pod(self, pod: PodInfo, candidate_nodes: List[NodeInfo]) -> SchedulingDecision:
        """
        Single-pod scheduling:
        - Place the pod on the node with the highest average bandwidth if we suspect
          the pod will consume a lot of traffic.
        """
        best_node = None
        best_avg_bw = 0.0

        for node in candidate_nodes:
            bw_values = node.network_bandwidth.values()
            avg_bw = sum(bw_values)/len(bw_values) if bw_values else 0
            free_cpu = node.cpu_capacity - node.current_cpu_usage
            free_mem = node.mem_capacity - node.current_mem_usage

            if (pod.cpu_req < free_cpu) and (pod.mem_req < free_mem) and (avg_bw > best_avg_bw):
                best_node = node
                best_avg_bw = avg_bw

        if not best_node:
            # fallback: pick node with largest avg bandwidth ignoring capacity
            best_node = max(candidate_nodes, key=lambda n: sum(n.network_bandwidth.values()) / (len(n.network_bandwidth) or 1))

        return SchedulingDecision(pod_name=pod.pod_name, selected_node=best_node.node_name)

    def schedule_all(self, pods: List[PodInfo], candidate_nodes: List[NodeInfo]) -> List[SchedulingDecision]:
        """
        Attempt to place the highest traffic pods on the best-bandwidth nodes:
        1) If you had a traffic demand attribute in PodInfo, you'd sort pods by that demand.
        2) Then pick the node with highest average bandwidth that has capacity.
        """
        decisions = []

        node_usage_cpu = {n.node_name: n.current_cpu_usage for n in candidate_nodes}
        node_usage_mem = {n.node_name: n.current_mem_usage for n in candidate_nodes}

        # In a real system, you might track each Pod's traffic demand, but here we'll assume they're the same
        # or rely on a separate data structure. We'll just schedule in the order they come in.
        for pod in pods:
            best_node = None
            best_bw_score = -1.0
            for node in candidate_nodes:
                free_cpu = node.cpu_capacity - node_usage_cpu[node.node_name]
                free_mem = node.mem_capacity - node_usage_mem[node.node_name]
                
                # add more stricter conditions, to avoid all pods are placed on the same node
                free_cpu = 0.5 * free_cpu
                free_mem = 0.5 * free_mem
                
                if (pod.cpu_req <= free_cpu) and (pod.mem_req <= free_mem):
                    # print("node.network_bandwidth: ", node.network_bandwidth)
                    
                    bw_values = node.network_bandwidth.values()
                    # print("bw_values: ", bw_values)
                    numeric_bw_values = [float(val) for val in bw_values] # convert the string values to floats
                    avg_bw = sum(numeric_bw_values) / len(numeric_bw_values) if numeric_bw_values else 0

                    if avg_bw > best_bw_score:
                        best_bw_score = avg_bw
                        best_node = node
            
            if best_node:
                node_usage_cpu[best_node.node_name] += pod.cpu_req
                node_usage_mem[best_node.node_name] += pod.mem_req
                decisions.append(SchedulingDecision(pod_name=pod.pod_name, selected_node=best_node.node_name))
            else:
                # fallback: pick node with largest avg bandwidth ignoring capacity
                fallback_node = max(candidate_nodes, key=lambda n: sum(n.network_bandwidth.values()) / (len(n.network_bandwidth) or 1))
                node_usage_cpu[fallback_node.node_name] += pod.cpu_req
                node_usage_mem[fallback_node.node_name] += pod.mem_req
                decisions.append(SchedulingDecision(pod_name=pod.pod_name, selected_node=fallback_node.node_name))

        return decisions

    def on_update_metrics(self, nodes: List[NodeInfo]) -> None:
        """
        Possibly refresh bandwidth data or any internal weighting logic. 
        For demonstration, we do nothing.
        """
        pass

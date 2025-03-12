from typing import List
from iDynamicsPackagesModules.SchedulingPolicyExtender.my_policy_interface import (
    AbstractSchedulingPolicy, NodeInfo, PodInfo, SchedulingDecision)
from iDynamicsPackagesModules.GraphDynamicsAnalyzer import graph_builder

class Policy1CallGraphAware(AbstractSchedulingPolicy):
    def __init__(self):
        self.traffic_matrix = {}

    def initialize_policy(self, config: dict) -> None:
        self.traffic_matrix = config.get("traffic_matrix", {})

    def schedule_pod(self, pod: PodInfo, candidate_nodes: List[NodeInfo]) -> SchedulingDecision:
        best_node = max(candidate_nodes, key=lambda node: node.cpu_capacity - node.current_cpu_usage)
        return SchedulingDecision(pod_name=pod.pod_name, selected_node=best_node.node_name)

    def schedule_all(self, pods: List[PodInfo], candidate_nodes: List[NodeInfo]) -> List[SchedulingDecision]:
        node_allocations = {node.node_name: [] for node in candidate_nodes}
        pod_cpu_req = {p.pod_name: p.cpu_req for p in pods}
        placed_pods = set()
        
        sorted_pairs = sorted(self.traffic_matrix.items(), key=lambda x: x[1], reverse=True)
        decisions = []

        for (podA, podB), _ in sorted_pairs:
            if podA in placed_pods or podB in placed_pods:
                continue
            for node in candidate_nodes:
                usage = sum(p.cpu_req for p in pods if p.pod_name in node_allocations[node.node_name])
                if (usage + pods[0].cpu_req * 2) <= node.cpu_capacity:
                    node_allocations[node.node_name].extend([podA, podB])
                    placed_pods.update({podA, podB})
                    break

        for pod in pods:
            if pod.pod_name not in placed_pods:
                best_node = max(candidate_nodes,
                                key=lambda n: n.cpu_capacity - sum(p.cpu_req for p in pods if p.pod_name in node_allocations[n.node_name]))
                node_allocations[best_node.node_name].append(pod.pod_name)

        return [SchedulingDecision(p, node) for node, plist in node_allocations.items() for p in plist]

    def on_update_metrics(self, app_namespace="social-network"):
        G = graph_builder.build_call_graph(namespace=app_namespace)
        self.traffic_matrix = {(u, v): data["weight"] for u, v, data in G.edges(data=True)}

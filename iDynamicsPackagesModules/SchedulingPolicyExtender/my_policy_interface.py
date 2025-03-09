from abc import ABC, abstractmethod
from typing import List

class NodeInfo:
    def __init__(self, node_name, cpu_capacity, mem_capacity, current_cpu_usage, current_mem_usage,
                 network_latency, network_bandwidth):
        self.node_name = node_name
        self.cpu_capacity = cpu_capacity
        self.mem_capacity = mem_capacity
        self.current_cpu_usage = current_cpu_usage
        self.current_mem_usage = current_mem_usage
        self.network_latency = network_latency       # Could be a dict
        self.network_bandwidth = network_bandwidth   # Could be a dict

class PodInfo:
    def __init__(self, pod_name, cpu_req, mem_req, sla_latency_requirement, deployment_name=None):
        self.pod_name = pod_name
        self.cpu_req = cpu_req
        self.mem_req = mem_req
        self.sla_latency_requirement = sla_latency_requirement
        self.deployment_name = deployment_name  # helpful if need to patch the deployment

class SchedulingDecision:
    def __init__(self, pod_name, selected_node):
        self.pod_name = pod_name
        self.selected_node = selected_node

class AbstractSchedulingPolicy(ABC):
    @abstractmethod
    def initialize_policy(self, config: dict) -> None:
        """
        Load the Prometheus URL, or set up connections or configuration objects if needed.
        
    
        Called once when the policy is created.# load
        """
        pass

    @abstractmethod
    def schedule_pod(self, pod: PodInfo, candidate_nodes: List[NodeInfo]) -> SchedulingDecision:
        """
        Basic single-Pod scheduling method (eg., NetMARKS))
        
        Return a SchedulingDecision for a single pod.
        """
        pass

    @abstractmethod
    def schedule_all(self, pods: List[PodInfo], candidate_nodes: List[NodeInfo]) -> List[SchedulingDecision]:
        """
       #  Batch or multi-service scheduling. (eg., TraDE)
        
        *Optional extension.* Return scheduling decisions for a batch of Pods simultaneously.
        This is useful for multi-service or multi-pod optimization.
        """
        pass
    
    @abstractmethod
    def on_update_metrics(self, nodes: List[NodeInfo], app_namespace: str) -> None:
        """
        Respond to new telemetry. 
        Parameters:
        - nodes: List of NodeInfo objects, which can be used for node-realted metrics
        - app_namespace: The namespace of the application, which can be used for application-specific metrics.
        
        For instance, if the user triggers a “re-scheduling event,” you can gather new usage data here.
        
        Called periodically if metrics are updated at runtime.
        """
        pass

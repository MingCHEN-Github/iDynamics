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
    def __init__(self, pod_name, cpu_req, mem_req, sla_requirement, deployment_name=None):
        self.pod_name = pod_name
        self.cpu_req = cpu_req
        self.mem_req = mem_req
        self.sla_requirement = sla_requirement
        self.deployment_name = deployment_name  # helpful if need to patch the deployment

# class SchedulingDecision:
#     def __init__(self, pod_name, selected_node):
#         self.pod_name = pod_name
#         self.selected_node = selected_node

class SchedulingDecision:
    # return the PodIno obeject and NodeInfo object
    def __init__(self, pod: PodInfo, node: NodeInfo):
        self.pod = pod
        self.node = node

class AbstractSchedulingPolicy(ABC):
    @abstractmethod
    def initialize_policy(self, dynamics_config: dict) -> None:
        """
        Load the Prometheus URL, or set up connections or configuration objects if needed.
        
    
        Called once when the policy is created.# load
        """
        pass
    
    @abstractmethod
    def trigger_migration(self) -> bool:
        """
        Trigger a migration event. 
        
        Called when the user triggers a migration event.
        
        Users can define a QoS metric to trigger a migration event.
        
        return a boolean indicating whether the migration is triggered.
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
    
    @abstractmethod
    def run(self):
        """
        This scheduler class is designed to be runtime scheduler, which means it will be continuously running
        to monoitor the deployed application in the given 'namespace' and take scheduling decisions once certain
        defined SLA (like QoS average response time) is violated to trigger scheduling decisions.
        Main function to run the scheduler.
        """
        if self.trigger_migration():
            # trigger microservice pods migration (True of False)
            '''
            (1) Get the current state of the system, e.g, pods, nodes, metrics (promethues, istio, jager).
            (2) Run the scheduling algorithm.
            (3) Apply the scheduling decisions.
            '''
            
            pass

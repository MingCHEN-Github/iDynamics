# file: main_controller.py
from Example_policies.NetMARKS.singlePodPolicy_NetMARKS import NetMARKS_Policy
from Example_policies.TraDE.MultiPodPolicy_TraDE import TraDE_Policy
from my_cluster_utils import gather_all_nodes, gather_all_pods, build_nodeinfo_objects, build_podinfo_objects
from my_policy_interface import AbstractSchedulingPolicy

def main():
    # 1. Connect to cluster, prom, gather data
    raw_nodes = gather_all_nodes()  # returns raw K8s node objects
    raw_pods = gather_all_pods()    # returns raw K8s pod objects

    node_infos = build_nodeinfo_objects(raw_nodes)
    pod_infos  = build_podinfo_objects(raw_pods)
    node_infos = build_nodeinfo_objects(raw_nodes)
    for i in range(len(node_infos)):
        print(node_infos[i].node_name)
        print(node_infos[i].cpu_capacity)
        print(node_infos[i].current_cpu_usage)
        print(node_infos[i].mem_capacity)
        print(node_infos[i].current_mem_usage)
        print(node_infos[i].network_latency)
        print(node_infos[i].network_bandwidth)

    # 2. Choose a policy
    # policy = NetMARKS_Policy()  # or TraDE_Policy
    # policy.initialize_policy({
    #     "prom_url": "http://10.105.116.175:9090", # Prometheus URL
    #     "namespace": "social-network",
    #     "timerange": 1,
    # })

    # # 3. Decide if we want single-pod or multi-pod scheduling
    # #    For NetMARKS, let's do single-pod:
    # target_pod = pod_infos[0]
    # decision = policy.schedule_pod(target_pod, node_infos)
    # print(f"Schedule {decision.pod_name} on {decision.selected_node}")

    # 4. Patch the cluster, wait for rolling updates, etc.
    # if decision.selected_node != "NoSuitableNode":
    #     patch_deployment_to_node(target_pod.deployment_name, decision.selected_node)

if __name__ == "__main__":
    main()

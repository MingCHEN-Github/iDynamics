'''the code is executed in paralla '''

import random
import csv
import paramiko
from multiprocessing import Pool

# Function to generate a realistic delay matrix
def generate_delay_matrix(num_nodes, base_latency=5, max_additional_latency=50):
    delay_matrix = [[0 for _ in range(num_nodes)] for _ in range(num_nodes)]

    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j:
                delay_matrix[i][j] = 0 # node-to-node its self, latency set to zero
            else:
                # additional_latency = random.uniform(0, max_additional_latency)
                additional_latency = random.uniform(0, max_additional_latency)
                distance_factor = abs(i - j) / num_nodes
                simulated_latency = base_latency + additional_latency * distance_factor
                congestion_factor = random.uniform(0.5, 1.5)
                delay_matrix[i][j] = int(simulated_latency * congestion_factor) # change the float to integer
    return delay_matrix

# Generate delay matrix for 9 worker nodes
'''Injecting no latencies'''

# clear all delays between nodes
delay_matrix = generate_delay_matrix(num_nodes=9, base_latency=0, max_additional_latency=0)

# Generate delay matrix for 9 worker nodes
# delay_matrix = generate_delay_matrix(num_nodes=9, base_latency= 5, max_additional_latency= 50)


# Save the delay matrix to a CSV file
with open('delay_matrix_parallel.csv', mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerows(delay_matrix)

def apply_latency_between_nodes(source_node_name, username, key_path, interface, delay_matrix, node_details):
    """Apply latency between source and destination nodes using SSH with a private key."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    
    try:
        source_node_ip = node_details[source_node_name]['ip']
        client.connect(source_node_ip, username=username, key_filename=key_path)
        
        # Clear existing rules:
        client.exec_command(f"sudo tc qdisc del dev {interface} root")
        
        client.exec_command(f"sudo tc qdisc add dev {interface} root handle 1: htb default 1")
        client.exec_command(f"sudo tc class add dev {interface} parent 1: classid 1:1 htb rate 100mbps")
        
        mark_count = 2  # Start from 2 to reserve 1:1 as the default class
        dst_node_details = exclude_src_node(source_node_name, node_details)
        source_node_index = list(node_details.keys()).index(source_node_name)

        for dst_node, details in dst_node_details.items():
            dst_node_index = list(node_details.keys()).index(dst_node)
            dst_node_ip = details['ip']
            latency = delay_matrix[source_node_index][dst_node_index]
            print(dst_node_ip)
            
            command_class_add = f"sudo tc class add dev {interface} parent 1: classid 1:{mark_count} htb rate 100mbps"
            command_delay_add = f"sudo tc qdisc add dev {interface} parent 1:{mark_count} handle {mark_count}0: netem delay {latency}ms"
            command_filter_add = f"sudo tc filter add dev {interface} protocol ip parent 1:0 prio 1 u32 match ip dst {dst_node_ip} flowid 1:{mark_count}"
            
            client.exec_command(command_class_add)
            client.exec_command(command_delay_add)
            client.exec_command(command_filter_add)
            
            print(f'From {source_node_name} to {dst_node}: injected latency {latency} ms ')
            mark_count += 1

    except Exception as e:
        print(f"Failed to apply latency for {source_node_name}: {e}")
    finally:
        client.close()

def exclude_src_node(src_node_name, node_details):
    return {name: details for name, details in node_details.items() if name != src_node_name}

def automate_latency_injection(params):
    source_node_name, delay_matrix, node_details = params
    username = node_details[source_node_name]['username']
    key_path = node_details[source_node_name]['key_path']
    interface = 'eth0'  # Assuming the interface name is eth0
    apply_latency_between_nodes(source_node_name, username, key_path, interface, delay_matrix, node_details)

# Assuming correct IP addresses and no duplication in node keys
node_details = {
    'k8s-worker-1': {'ip': '172.26.128.30', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'},
    'k8s-worker-2': {'ip': '172.26.132.91', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'},
    'k8s-worker-3': {'ip': '172.26.133.31', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'},
    'k8s-worker-4': {'ip': '172.26.132.241', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'},
    'k8s-worker-5': {'ip': '172.26.132.142', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'},
    'k8s-worker-6': {'ip': '172.26.133.55', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'},
    'k8s-worker-7': {'ip': '172.26.130.22', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'},
    'k8s-worker-8': {'ip': '172.26.130.82', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'},
    'k8s-worker-9': {'ip': '172.26.133.118', 'username': 'ubuntu', 'key_path': '/home/ubuntu/.ssh/id_rsa'}
}

# Apply latency injection using the generated delay matrix with multiprocessing
params_list = [(source_node, delay_matrix, node_details) for source_node in node_details.keys()]

if __name__ == '__main__':
    with Pool(processes=len(node_details)) as pool:
        pool.map(automate_latency_injection, params_list)

# plot the delay matrix
# import pandas as pd
# import seaborn as sns
# import matplotlib.pyplot as plt

# # Read the delay matrix from the CSV file
# delay_matrix = pd.read_csv('delay_matrix_parallel.csv', header=None)

# # Plot the heatmap
# plt.figure(figsize=(10, 8))
# sns.heatmap(delay_matrix, annot=True, fmt=".1f", cmap="viridis", cbar=True)
# plt.title('Latency Heatmap')
# plt.xlabel('Target Node')
# plt.ylabel('Source Node')
# plt.show()

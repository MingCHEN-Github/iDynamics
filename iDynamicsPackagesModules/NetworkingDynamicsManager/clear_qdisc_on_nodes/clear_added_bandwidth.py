#!/usr/bin/env python3
from datetime import datetime
import paramiko
import logging
from multiprocessing import Pool

# Configure logging with a timestamped log file
timestamp = datetime.now().strftime("%Y_%b_%d_%H%M")  # Example: 2024_Oct_20_1930
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(processName)s] %(message)s',
    filename=f'/home/ubuntu/iDynamics/Evaluations/clear_qdisc_on_nodes/{timestamp}_clear_qdisc_bandwidths.log'
)

# Function to execute commands via SSH
def execute_ssh_command(client, command):
    stdin, stdout, stderr = client.exec_command(command)
    stdout_output = stdout.read().decode().strip()
    stderr_output = stderr.read().decode().strip()
    if stderr_output:
        logging.error(f"Error executing command: {command}\n{stderr_output}")
    return stdout_output, stderr_output

# Function to clear the qdisc rules on a given node
def clear_qdisc_on_node(node_name, username, key_path, interface, node_details):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()

    try:
        node_ip = node_details[node_name]['ip']
        client.connect(node_ip, username=username, key_filename=key_path)
        # Execute the command to delete the root qdisc; the "|| true" ensures that
        # the command always succeeds even if there is no qdisc configured.
        command = f"sudo tc qdisc del dev {interface} root || true"
        stdout_output, _ = execute_ssh_command(client, command)
        logging.info(f"Cleared qdisc rules on {node_name} ({node_ip}): {stdout_output}")
    except Exception as e:
        logging.error(f"Failed to clear qdisc rules for {node_name}: {e}")
    finally:
        client.close()

# Function for multiprocessing; prepares SSH parameters for each node.
def automate_qdisc_clearing(params):
    node_name, node_details = params
    username = node_details[node_name]['username']
    key_path = node_details[node_name]['key_path']
    interface = 'eth0'  # Assuming the interface is eth0
    clear_qdisc_on_node(node_name, username, key_path, interface, node_details)

# Node details with IPs and SSH credentials
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

# Prepare parameters for parallel execution (one entry per node)
params_list = [(node_name, node_details) for node_name in node_details.keys()]

if __name__ == '__main__':
    with Pool(processes=len(node_details)) as pool:
        pool.map(automate_qdisc_clearing, params_list)

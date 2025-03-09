import paramiko, logging
from datetime import datetime
from multiprocessing import Pool
# Configure logging with a timestamped log file

timestamp = datetime.now().strftime("%Y_%b_%d_%H%M")  # Example: 2024_Oct_20_1930
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(processName)s] %(message)s',
    filename=f'/home/ubuntu/iDynamics/Evaluations/clear_qdisc_on_nodes/{timestamp}_clear_qdisc_delays.log'
)


def clear_qdisc_delay_rules(source_node_name, username, key_path, interface, node_details):
    """
    Connects via SSH to a worker node and clears any existing qdisc rules on the specified interface.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    
    try:
        source_node_ip = node_details[source_node_name]['ip']
        client.connect(source_node_ip, username=username, key_filename=key_path)
        
        # Delete any existing qdisc on the interface. The "|| true" ensures that the command
        # does not fail if no qdisc exists.
        command = f"sudo tc qdisc del dev {interface} root || true"
        stdin, stdout, stderr = client.exec_command(command)
        stdout_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode().strip()
        
        print(f"Cleared qdisc delay rules on {source_node_name} ({source_node_ip}).")
        if stderr_output:
            print(f"Note: {source_node_name} reported: {stderr_output}")
    except Exception as e:
        print(f"Failed to clear qdisc delay rules for {source_node_name}: {e}")
    finally:
        client.close()

def automate_latency_clearing(params):
    """
    Multiprocessing helper function to clear delay rules on a node.
    """
    source_node_name, node_details = params
    username = node_details[source_node_name]['username']
    key_path = node_details[source_node_name]['key_path']
    interface = 'eth0'  # Target interface for delay rules
    clear_qdisc_delay_rules(source_node_name, username, key_path, interface, node_details)

# Node details with IPs and SSH credentials for each worker node
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
        pool.map(automate_latency_clearing, params_list)

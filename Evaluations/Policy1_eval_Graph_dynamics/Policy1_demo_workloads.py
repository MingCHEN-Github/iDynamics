# using wrk tool to run the four differnt test workloads (request A, request B, request C, request_mix ABC) for Social Network Application in name space of "social-network"
# this test is used to observe the different performace of the Social Network Application under different workloads(requests). Each type of request is running 5 mins

import os
import subprocess
from datetime import datetime

request_A_script_path = "/home/ubuntu/DeathStarBench/socialNetwork/wrk2/scripts/social-network/compose-post.lua"
request_B_script_path = "/home/ubuntu/DeathStarBench/socialNetwork/wrk2/scripts/social-network/read-home-timeline.lua"
request_C_script_path = "/home/ubuntu/DeathStarBench/socialNetwork/wrk2/scripts/social-network/read-user-timeline.lua"

request_mix_script_path = "/home/ubuntu/DeathStarBench/socialNetwork/wrk2/scripts/social-network/mixed-workload.lua" # default mix percentage: 60% A, 30% B, 10% C

script_path = [
    request_A_script_path,
    request_B_script_path,
    request_C_script_path,
    request_mix_script_path
]

url = [
    #diffferent namespace of social-network Application
    "http://nginx-thrift.social-network.svc.cluster.local:8080"       # in namespace of "social-network"
#     "http://nginx-thrift.social-network2.svc.cluster.local:8080",
#    "http://nginx-thrift.social-network3.svc.cluster.local:8080"
]


def wrk_different_requests(req_script:str, url:str, request_interval: str):
    # Define the parameters, which an be changed for different tests
    thread_num = 4
    connections = 100
    duration = request_interval # eg., "30s", "1m", 5m", "10m", "15m"
    QPS = [20] # can adde more QPS for different tests, like [20, 50, 80, 36]

    script_path = req_script
    url = url

    # Define the output file path in the current directory and file name with the format of current time (Year_MONTH_Day_Hour_Minute)

    # Generate the current time as a string in the format Year_MONTH_Day_Hour_Minute
    timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M')
    # Construct your desired filename, appending the timestamp
    filename = f"output_result_{timestamp}.txt"
    # Combine the current working directory with your new filename
    output_file = os.path.join("~/iDynamics/Evaluations/Policy1_eval_Graph_dynamics", filename)

    # Ensure the output file is empty at the start
    with open(output_file, 'w') as f:
        f.write("")


    for i in range(len(url)):
        for script in script_path:
            command = [
                "/home/ubuntu/DeathStarBench/wrk2/wrk",
                "-D", "exp",
                f"-t{thread_num}",
                f"-c{connections}",
                f"-d{duration}",
                "-L",
                "-s", script,
                url[i],
                f"-R{QPS[0]}"
            ]
            print(f"Running command: {' '.join(command)}")

            # make sure each loop runs one command, after finish current loop, run the next command
            # run the command
            process = subprocess.Popen(command, stdout=subprocess.PIPE)
            output, error = process.communicate()
            output = output.decode("utf-8")
            print(output)
            # Write the output to the output file
            with open(output_file, 'a') as f:
                f.write(output)
                f.write("\n\n")
            print(f"Finished running command: {' '.join(command)}")
            print("--------------------------------------------------")
    print("All wrk_different_requests tests are done!")





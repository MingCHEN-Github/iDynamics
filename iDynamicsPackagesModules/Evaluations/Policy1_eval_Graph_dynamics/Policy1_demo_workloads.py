# using wrk tool to run the four differnt test workloads (request A, request B, request C, request_mix ABC) for Social Network Application in name space of "social-network"
# this test is used to observe the different performace of the Social Network Application under different workloads(requests). Each type of request is running 5 mins

import os
import subprocess
from datetime import datetime

def wrk_different_requests(req_script: str, url: str, request_interval: str):
    # Define the parameters for different tests
    thread_num = 4
    connections = 100
    duration = request_interval  # e.g., "30s", "1m", "5m", "10m", "15m"
    QPS = [20]  # can add more QPS values for different tests, e.g., [20, 50, 80, 36]

    # Allow req_script and url to be either a single string or a list of strings.
    if isinstance(req_script, str):
        req_scripts = [req_script]
    else:
        req_scripts = req_script

    if isinstance(url, str):
        urls = [url]
    else:
        urls = url

    # Define the output directory path and expand the tilde to the home directory.
    output_dir = os.path.expanduser("~/iDynamics/Evaluations/Policy1_eval_Graph_dynamics/Policy1_demo_data/")
    # Create the directory if it doesn't exist.
    os.makedirs(output_dir, exist_ok=True)

    # Generate the current timestamp for the output filename.
    timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M')
    filename = f"output_result_{timestamp}.txt"
    output_file = os.path.join(output_dir, filename)

    # xxxx Ensure the output file is empty at the start.
    with open(output_file, 'w') as f:
        f.write("")

    # Iterate over each URL and each script to run tests.
    for u in urls:
        print(f"Running wrk_different_requests test for url: {u}")
        for script in req_scripts:
            command = [
                "/home/ubuntu/DeathStarBench/wrk2/wrk",
                "-D", "exp",
                f"-t{thread_num}",
                f"-c{connections}",
                f"-d{duration}",
                "-L",
                "-s", script,
                u,
                f"-R{QPS[0]}"
            ]
            print(f"Running command: {' '.join(command)}")

            # Execute the command and capture the output.
            process = subprocess.Popen(command, stdout=subprocess.PIPE)
            output, error = process.communicate()
            output = output.decode("utf-8")
            print(output)
            
            # Append the output to the output file.
            with open(output_file, 'a') as f:
                f.write(output)
                f.write("\n\n")
            print(f"Finished running command: {' '.join(command)}")
            print("--------------------------------------------------")
    print("All wrk_different_requests tests are done!")



# def wrk_different_requests(req_script:str, url:str, request_interval: str):
#     # Define the parameters, which an be changed for different tests
#     thread_num = 4
#     connections = 100
#     duration = request_interval # eg., "30s", "1m", 5m", "10m", "15m"
#     QPS = [20] # can adde more QPS for different tests, like [20, 50, 80, 36]

#     script_path = req_script
#     url = url

#     # Define the output file path in the current directory and file name with the format of current time (Year_MONTH_Day_Hour_Minute)

#     # Generate the current time as a string in the format Year_MONTH_Day_Hour_Minute
#     timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M')
#     # Construct your desired filename, appending the timestamp
#     filename = f"output_result_{timestamp}.txt"
#     # Combine the current working directory with your new filename
#     output_file = os.path.join("/home/ubuntu/iDynamics/iDynamicsPackagesModules/Evaluations/Policy1_eval_Graph_dynamics/Policy1_demo_data/", filename)

#     # Ensure the output file is empty at the start
#     with open(output_file, 'w') as f:
#         f.write("")


#     for i in range(len(url)):
#         print(f"Running wrk_different_requests test for url: {url[i]}")
#         for script in script_path:
#             command = [
#                 "/home/ubuntu/DeathStarBench/wrk2/wrk",
#                 "-D", "exp",
#                 f"-t{thread_num}",
#                 f"-c{connections}",
#                 f"-d{duration}",
#                 "-L",
#                 "-s", script,
#                 url[i],
#                 f"-R{QPS[0]}"
#             ]
#             print(f"Running command: {' '.join(command)}")

#             # make sure each loop runs one command, after finish current loop, run the next command
#             # run the command
#             process = subprocess.Popen(command, stdout=subprocess.PIPE)
#             output, error = process.communicate()
#             output = output.decode("utf-8")
#             print(output)
#             # Write the output to the output file
#             with open(output_file, 'a') as f:
#                 f.write(output)
#                 f.write("\n\n")
#             print(f"Finished running command: {' '.join(command)}")
#             print("--------------------------------------------------")
#     print("All wrk_different_requests tests are done!")





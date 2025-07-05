#!/usr/bin/env python3
"""
Add **or** remove the `trial/exclude=lab:NoSchedule` taint on k8s-worker-6 … k8s-worker-14.

Usage
-----
python taint_toggle.py add      # add / overwrite taint
python taint_toggle.py remove   # remove taint
"""

import subprocess, sys

TAINT_KEY   = "trial/exclude"
TAINT_VALUE = "lab:NoSchedule"  # newly launched microservice will not be launched on the tainted nodes
NODES       = [f"k8s-worker-{i}" for i in range(6, 15)]  # 6-14 inclusive

def sh(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True)

if len(sys.argv) != 2 or sys.argv[1] not in {"add", "remove"}:
    sys.exit("usage: taint_toggle.py [add|remove]")

if sys.argv[1] == "add":
    for n in NODES:
        sh(["kubectl", "taint", "nodes", n, f"{TAINT_KEY}=lab:{TAINT_VALUE.split(':')[1]}", "--overwrite"])
else:  # remove
    for n in NODES:
        sh(["kubectl", "taint", "nodes", n, f"{TAINT_KEY}-"])

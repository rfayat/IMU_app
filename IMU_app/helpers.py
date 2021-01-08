"Helper functions for running the data acquisition GUI"
import json
import shutil
import signal
import os
import subprocess


def read_config(config_path="./config.json"):
    "Read the JSON configuration file"
    with open(config_path) as f:
        config = json.load(f)
    return config


def save_file(file, destination_path):
    "Save a binary file to a selected file"
    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file, buffer)

# WARNING: The finally clauses of python scripts doesn't seem to be executed

# def kill_by_pid(pid: int):
#     "Kill a local process using its pid"
#     try:
#         return os.kill(pid, signal.CTRL_C_EVENT)
#     except OSError:  # the process does not exist
#         return None

def kill_by_pid(pid: int):
    "Kill a local process using its pid"
    # sometimes need to call taskkill twice for it to work
    for i in range(2):
        subprocess.call(["taskkill", "/PID", str(pid)])

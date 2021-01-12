"Helper functions for running the data acquisition GUI"
import json
import shutil
import signal
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List


# File handling helpers
def read_config(config_path="./config.json"):
    "Read the JSON configuration file"
    with open(config_path) as f:
        config = json.load(f)
    return config

def save_file(file, destination_path):
    "Save a binary file to a selected file"
    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file, buffer)


def copy_file(source_path, destination_path):
    "Copy a file at a given path to another input path"
    # Convert the inputs to str if a pathlib.Path is provided
    if isinstance(source_path, str):
        source_path = Path(source_path)
    if isinstance(destination_path, str):
        destination_path = Path(destination_path)
    # Create the path to the destination if needed
    if not destination_path.parent.is_dir():
        mkdirs(destination_path.parent)
    # Copy the file
    shutil.copyfile(source_path, destination_path)


def mkdirs(path):
    "Walk through a path to create a directory and its parents if needed"
    if isinstance(path, str):  # Conversion to pathlib.Path if needed
        path = Path(path).expanduser().absolute()
    if not path.is_dir():
        path.mkdir(parents=True)


# Process management
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


def kill_multiple_by_pid(pid_list: List[int]):
    "Kill a list of local processes using their pids"
    for pid in pid_list:
        kill_by_pid(pid)


# Date helpers
def now_as_str():
    "Return the current date and time as a string"
    current_time = datetime.now()
    return current_time.strftime("%Y%m%d-%H:%M:%S")


def today_as_str():
    "Return the current date and time as a string"
    current_time = datetime.now()
    return current_time.strftime("%Y%m%d")

"Helper functions for running the data acquisition GUI"
import json
import os
import shutil


def read_config(config_path="./config.JSON"):
    "Read the JSON configuration file"
    with open(config_path) as f:
        config = json.load(f)
    return config


def save_file(file, destination_path):
    "Save a binary file to a selected file"
    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file, buffer)


def state_file_from_cam_name(cam_name: str):
    "Return the name which will be used to save the statfile for a camera"
    return f"{cam_name}_state_file"


def cam_name_from_state_file(state_file: str):
    "Return the camera name from the state file name"
    return state_file.rstrip("_state_file")


def is_stored_state_file(file_name: str):
    """Check if the input file name corresponds to a stored state file

    Could be extended to check if the content of the file corresponds to a
    state file (this would also be useful when uploading the file).
    """
    if file_name.endswith("_state_file"):
        return True
    else:
        return False

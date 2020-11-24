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

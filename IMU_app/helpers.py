"Helper functions for running the data acquisition GUI"
import json


def read_config(config_path="./config.JSON"):
    "Read the JSON configuration file"
    with open(config_path) as f:
        config = json.load(f)
    return config

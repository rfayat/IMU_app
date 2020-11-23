"Helper functions for running the data acquisition GUI"
import json

config_path = "config.JSON"

with open(config_path) as f:
    config = json.load(f)

if __name__ == "__main__":
    print(config)

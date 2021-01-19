"""
Start a live stream  using a provided state file.

Author: Romain Fayat, October 2020
"""
import cv2
import argparse
from IC_trigger.camera import Camera
import os

# Argument parsing
parser = argparse.ArgumentParser(__doc__)
parser.add_argument("pathCamParam",
                    help="Path to the state file of the camera")
args = parser.parse_args()

pathCamParam = args.pathCamParam


def loop():
    "Wait for any user interaction with the preview window"
    while True:
        cv2.waitKey(1)


if __name__ == "__main__":
    # Select the camera from the provided statefile
    cam = Camera.from_file(pathCamParam)
    cam.StartLive(1)  # Start the preview
    try:
        print(f"Preview for state file: {pathCamParam}")
        print(f"PID: {os.getpid()}")
        loop()
    except KeyboardInterrupt:
        print("Interrupted by the user")
    finally:
        cam.StopLive()

"""Helpers for handling TIS camera on windows.

Author: Romain Fayat, January 2021
"""
from pathlib import Path
import subprocess


def state_file_from_cam_name(cam_name: str):
    "Return the name which will be used to save the statfile for a camera"
    return f"{cam_name}_state_file"


def cam_name_from_state_file(state_file: str):
    "Return the camera name from the state file name"
    state_file = Path(state_file).name
    return state_file.rstrip("_state_file")


def is_stored_state_file(file_name: str):
    """Check if the input file name corresponds to a stored state file

    Could be extended to check if the content of the file corresponds to a
    state file (this would also be useful when uploading the file).
    """
    # Convert to string if a Path is provided
    if isinstance(file_name, Path):
        file_name = file_name.name

    return file_name.endswith("_state_file")


def start_tis_preview(state_file_path):
    "Start a live preview for an input state file"
    command = f"python -m IMU_app.tis_camera_win.live_stream_from_statefile {state_file_path}"  # noqa E501
    p = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
    return p.pid


def start_tis_recording(state_file_path, options={}):
    "Start a recording for an input state file"
    options_as_str = " ".join([f"--{k} {v}" for k, v in options.items()])
    command = f"python -m IMU_app.tis_camera_win.record_video_queue {state_file_path} {options_as_str}"  # noqa E501
    p = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
    # Make the priority of the process higher
    subprocess.run(f"wmic process where ProcessId={p.pid} CALL setpriority \"Realtime\"")
    return p.pid


def start_ffmpeg_recording(state_file_path, options={}):
    "Start a recording for an input state file"
    options_as_str = " ".join([f"--{k} {v}" for k, v in options.items()])
#     command = f"python -m IMU_app.tis_camera_win.record_video {state_file_path} {options_as_str}"  # noqa E501
    command = f"python -m IMU_app.tis_camera_win.record_video_ffmpeg {state_file_path} {options_as_str}"  # noqa E501
    p = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
    # Make the priority of the process higher
    subprocess.run(f"wmic process where ProcessId={p.pid} CALL setpriority \"Realtime\"")
    return p.pid

"""
Main code for the application for data acquisition.

Author: Romain Fayat, November 2020
"""
import os
from fastapi import FastAPI, Request, File, UploadFile, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from .rpi import RPI_connector
from . import helpers
from .helpers import read_config, save_file


parameters = read_config()
param_pwm = parameters["pwm"]
param_tis_win = parameters["tis_camera_win"]

# Create the folder for saving tis state files if needed
tis_saving_path = param_tis_win["saving_path"]
if not os.path.isdir(tis_saving_path):
    os.makedirs(tis_saving_path)

app = FastAPI()
templates = Jinja2Templates(directory="IMU_app/templates/")


@app.get("/")
async def dashboard(request: Request):
    "Return the main dashboard"
    return templates.TemplateResponse("dashboard.html",
                                      context={"request": request})


@app.get("/success")
async def success(request: Request, success: bool, message: Optional[str]=""):
    "Return the main dashboard"
    return templates.TemplateResponse("success.html",
                                      context={"request": request,
                                               "success": success,
                                                "message": message})


# Handle TIS cameras
@app.get("/tis_camera_win")
async def tis_cam_windows(request: Request):
    "Return TIS camera selection page"
    # Get all cam names and the path to their corresponding state file
    available_state_files = {}  # came_name: state_file_path
    for file_name in os.listdir(tis_saving_path):
        if helpers.is_stored_state_file(file_name):
            cam_name = helpers.cam_name_from_state_file(file_name)
            state_file_path = os.path.sep.join([tis_saving_path, file_name])
            available_state_files[cam_name] = state_file_path

    # Render the camera selection page
    context={"request": request, "state_files": available_state_files}
    return templates.TemplateResponse("tis_camera_windows.html", context)

@app.get("/tis_camera_win/upload_page")
async def tis_cam_windows_upload_page(request: Request):
    "Return the file upload page for a TIS cam state file"
    return templates.TemplateResponse("tis_camera_windows_upload.html",
                                      context={"request": request})


@app.post("/tis_camera_win/upload")
async def tis_cam_windows_upload(request: Request,
                                 state_file: UploadFile = File(...),
                                 cam_name: str = Form(...)):
    "Upload a TIS cam state file"
    file_name = helpers.state_file_from_cam_name(cam_name)
    saving_path = os.path.sep.join([tis_saving_path, file_name])
    save_file(state_file.file, saving_path)
    return {"file_name": state_file.filename, "cam_name": cam_name,
            "saving_path": saving_path}


# TODO: Change to /tis_camera_win/cam_name/[record/kill/preview]
# TODO: The finally statement of the script does not seem to be executed when running $ kill pid
@app.post("/tis_camera_win/record")
async def tis_cam_windows_record(request: Request,
                                 state_file_path: str = Form(...),
                                 selected_action: str = Form(...)):
    if selected_action == "Preview":
        pid = helpers.start_tis_preview(state_file_path)
    return {"state_file_path": state_file_path, "selected_action": selected_action, "pid": pid}

# Handle raspberry pi
@app.get("/rpi/pwm")
async def start_pwm():
    "Start PWM with the parameters stored in the config JSON"
    ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
    pid = ssh.run_script(param_pwm["path"], param_pwm["options"])
    ssh.close()
    os.environ["pwm_pid"] = str(pid)
    return {"message": "Started PWM", "pid": pid}


@app.get("/rpi/pwm/test_connection")
async def test_connection_pwm():
    "Test the connection to the remote raspberry pi"
    connected = RPI_connector.test_connection(**param_pwm["ssh"])
    if connected:
        return {"message": "success"}
    else:
        return {"message": "failure"}


@app.get("/rpi/kill")
async def kill_all():
    "Kill all python processes on the remote rpi"
    ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
    ssh.kill_all()
    ssh.close()
    return {"message": "Killed all python processes"}


@app.get("/rpi/pwm/kill")
@app.get("/rpi/kill/pwm")
async def kill_pwm():
    "Kill the pwm process on the RPI"
    pid = os.environ.get("pwm_pid")
    if pid is None:
        return {"message": "No PWM process running"}
    else:
        ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
        ssh.kill(pid)
        ssh.close()
        return {"message": "Killed PWM", "pid": int(pid)}


@app.get("/rpi/kill/{pid}")
async def kill(pid: int):
    "Kill a given process on the RPI"
    ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
    ssh.kill(pid)
    ssh.close()
    return {"message": "Killed process", "pid": pid}

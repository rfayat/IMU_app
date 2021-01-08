"""
Main code for the application for data acquisition.

Author: Romain Fayat, November 2020
"""
import os
from fastapi import FastAPI, Request, File, UploadFile, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from .rpi import RPI_connector
from . import tis_camera_win
from . import helpers
from .database import AcquisitionDB

# TinyDB database
db = AcquisitionDB()
processes = {}

# Read the configuration file and extract:
# - The loggin information to the PWM-RPI (host name, username...)
# - The path to the camera configuration files
parameters = helpers.read_config()
param_pwm = parameters["pwm"]
param_tis_win = parameters["tis_camera_win"]

# Create the folder for saving tis state files if needed
tis_saving_path = param_tis_win["saving_path"]
if not os.path.isdir(tis_saving_path):
    os.makedirs(tis_saving_path)

# Initialize the app
app = FastAPI()
templates = Jinja2Templates(directory="IMU_app/templates/")


# TODO "/" redirect to /dashboard if a session is running, to /new else
@app.get("/new")
async def new_session(request: Request):
    db.reinitialize()  # Clear the data from the last session
    # TODO: Add the animal and folder selection here
    return RedirectResponse("/dashboard")


@app.get("/dashboard")
async def dashboard(request: Request):
    "Return the main dashboard"
    context = {"request": request,
               "available_cameras": db.get_available_cameras(),
               "available_rpi": db.get_available_rpi()}
    return templates.TemplateResponse("dashboard.html", context=context)


@app.get("/success")
async def success(request: Request, success: bool, message: Optional[str]=""):
    "Return the main dashboard"
    return templates.TemplateResponse("success.html",
                                      context={"request": request,
                                               "success": success,
                                               "message": message})


@app.get("/kill/{pid}")
async def kill_by_pid(pid: int):
    "Kill a local process using its process ID"
    helpers.kill_by_pid(pid)
    db.remove_local_process(pid)
    return {"pid": pid, "message": f"Killed process {pid}"}


# Handle TIS cameras
@app.get("/tis_camera_win")
async def tis_cam_windows(request: Request):
    "Return TIS camera selection page"
    # Get names of the available cameras
    available_cameras = db.get_available_cameras()
    # Render the camera selection page
    context={"request": request, "available_cameras": available_cameras}
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
    file_name = tis_camera_win.state_file_from_cam_name(cam_name)
    saving_path = os.path.sep.join([tis_saving_path, file_name])
    helpers.save_file(state_file.file, saving_path)
    db.initialize_tiscamera(saving_path)  # Logging in the database
    return {"file_name": state_file.filename, "cam_name": cam_name,
            "saving_path": saving_path}


# TODO: The finally statement of the script does not seem to be executed when running $ kill pid
@app.post("/tis_camera_win/action")
async def tis_cam_windows_action(request: Request,
                                 cam_name: str = Form(...),
                                 selected_action: str = Form(...)):
    if selected_action == "Preview":
        return RedirectResponse(f"/tis_camera_win/{cam_name}/preview",
                                status_code=status.HTTP_303_SEE_OTHER)
    if selected_action == "Start recording":
        return RedirectResponse(f"/tis_camera_win/{cam_name}/record",
                                status_code=status.HTTP_303_SEE_OTHER)


@app.get("/tis_camera_win/{cam_name}/preview")
async def tis_cam_windows_preview(cam_name: str):
    "Start a TIS camera preview from a cam_name"
    state_file_path = db.get_state_file_path(cam_name)
    pid = tis_camera_win.start_tis_preview(state_file_path=state_file_path)
    db.add_tis_cam_process(cam_name, "preview", pid)
    return {"cam_name": cam_name, "action": "preview", "pid": pid}


@app.get("/tis_camera_win/{cam_name}/record")
async def tis_cam_windows_record(cam_name: str):
    "Start a TIS camera recording from a cam_name"
    # TODO: Implement + add file name
    # pid = ...
    pid = 43
    db.add_tis_cam_process(cam_name, "record", pid)
    return {"cam_name": cam_name, "action": "record", "pid": pid}


# Handle raspberry pi
# TODO: Grab the parameters from the database rather than the config json
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


# Handle the rodents (TODO: create the UI for this)
@app.get("/rodents/new/{rodent_name}/{sensor_id}")
@app.put("/rodents/{rodent_name}/{sensor_id}")
async def add_rodent(rodent_name: str, sensor_id: str):
    "Add a new rodent and its sensor id to the rodents table"
    db.add_rodent(rodent_name, sensor_id)
    return {"message": f"Added {rodent_name} with sensor {sensor_id}"}


@app.get("/rodents/remove/{rodent_name}")
@app.delete("/rodents/{rodent_name}")
async def remove_rodent(rodent_name: str):
    "Remove a rodent from the rodents table"
    db.remove_rodent(rodent_name)
    return {"message": f"Removed {rodent_name}"}

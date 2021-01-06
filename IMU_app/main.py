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
from .helpers import save_file, read_config
from .database import AcquisitionDB

db = AcquisitionDB()

parameters = read_config()
param_pwm = parameters["pwm"]
param_tis_win = parameters["tis_camera_win"]

# Create the folder for saving tis state files if needed
tis_saving_path = param_tis_win["saving_path"]
if not os.path.isdir(tis_saving_path):
    os.makedirs(tis_saving_path)

app = FastAPI()
templates = Jinja2Templates(directory="IMU_app/templates/")

# TODO "/" redirect to /dashboard if a session is running, to /new else

@app.get("/new")
async def new_session(request: Request):
    db.reinitialize()
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
    db.initialize_tiscamera(saving_path)  # Logging in the database
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


@app.get("/tis_camera_win/{cam_name}/preview")
async def tis_cam_windows_preview(cam_name: str):
    return {"cam_name": cam_name, "action": "preview"}


@app.get("/tis_camera_win/{cam_name}/record")
async def tis_cam_windows_record(cam_name: str):
    return {"cam_name": cam_name, "action": "record"}

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
async def add_rodent(rodent_name: str, sensor_id: str):
    "Add a new rodent and its sensor id to the rodents table"
    db.add_rodent(rodent_name, sensor_id)
    return {"message": f"Added {rodent_name} with sensor {sensor_id}"}


@app.get("/rodents/remove/{rodent_name}")
async def remove_rodent(rodent_name: str):
    "Remove a rodent from the rodents table"
    db.remove_rodent(rodent_name)
    return {"message": f"Removed {rodent_name}"}

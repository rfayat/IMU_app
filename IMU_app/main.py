"""
Main code for the application for data acquisition.

Author: Romain Fayat, November 2020
"""
from fastapi import FastAPI, Request, File, UploadFile, Form
from fastapi.templating import Jinja2Templates
from .rpi import RPI_connector
from .helpers import read_config
import os


parameters = read_config()
param_pwm = parameters["pwm"]

app = FastAPI()
templates = Jinja2Templates(directory="IMU_app/templates/")


@app.get("/")
async def dashboard(request: Request):
    "Return the main dashboard"
    return templates.TemplateResponse("dashboard.html",
                                      context={"request": request})


# Handle TIS cameras
@app.get("/tis_camera_win")
async def tis_cam_windows(request: Request):
    "Return the file upload page for a TIS cam state file"
    return templates.TemplateResponse("tis_camera_windows.html",
                                      context={"request": request})


@app.post("/tis_camera_win/upload")
async def tis_cam_windows_upload(request: Request,
                                 file: UploadFile = File(...),
                                 cam_name: str = Form(...)):
    "Upload a TIS cam state file"
    return {"file_name": file.filename, "cam_name": cam_name}


# Handle raspberry pi
@app.get("/rpi/pwm")
async def start_pwm():
    "Start PWM with the parameters stored in the config JSON"
    ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
    pid = ssh.run_script(param_pwm["path"], param_pwm["options"])
    ssh.close()
    os.environ["pwm_pid"] = str(pid)
    return {"message": "Started PWM", "pid": pid}


@app.get("/rpi/kill")
async def kill_all():
    "Kill all python processes on the remote rpi"
    ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
    ssh.kill_all()
    ssh.close()
    return {"message": "Killed all python processes"}


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

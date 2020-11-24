"""
Main code for the application for data acquisition.

Author: Romain Fayat, November 2020
"""
from fastapi import FastAPI, Request
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

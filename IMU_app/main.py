"""
Main code for the application for data acquisition.

Author: Romain Fayat, November 2020
"""
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from rpi import RPI_connector
from helpers import read_config


parameters = read_config()
param_pwm = parameters["pwm"]

app = FastAPI()
templates = Jinja2Templates(directory="templates/")


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
    return {"message": "Started PWM", "pid": pid}


@app.get("/rpi/kill/{pid}")
async def stop_pwm(pid: int):
    "Kill a given process on the RPI"
    ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
    ssh.kill(pid)
    ssh.close()
    return {"message": "Killed process", "pid": pid}

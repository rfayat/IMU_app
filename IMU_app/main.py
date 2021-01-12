"""
Main code for the application for data acquisition.

Author: Romain Fayat, November 2020
"""
import os
from fastapi import FastAPI, Request, File, UploadFile, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from pathlib import Path
from .rpi import RPI_connector
from . import tis_camera_win
from . import helpers
from .database import AcquisitionDB
from . import session

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


@app.get("/")
async def home():
    "Redirect to /dashboard if a session is running, to /new_session else"
    if db.has_session():
        return RedirectResponse("/dashboard")
    else:
        return RedirectResponse("/new_session")

@app.get("/new_session")
async def new_session(request: Request):
    users = db.table("users").all()
    rodents = db.table("rodents").all()
    default_block = session.create_default_block()

    context = {"request": request,
               "users": users,
               "rodents": rodents,
               **default_block}
    return templates.TemplateResponse("new_session.html", context=context)


@app.get("/new_block")
async def new_block(request: Request):
    block_id = f"{len(db.session_table) + 1 :02d}"
    session_properties = db.get_session_properties()
    block_properties = session.create_default_block(block_id=block_id)
    context = {
        "request": request,
        **session_properties,
        **block_properties,
    }
    return templates.TemplateResponse("new_block.html", context=context)


@app.post("/create_new_session")
async def create_new_session(request: Request,
                             user_name: str = Form(...),
                             rodent_name: str = Form(...),
                             data_folder: str = Form(...),
                             session_folder: str = Form(...),
                             session_notes: str = Form(""),
                             block_folder: str = Form(...),
                             block_notes: str = Form("")):
    db.reinitialize()  # Clear the data from the last session

    # Create the session and block folder architecture
    session_path = Path(data_folder).joinpath(session_folder)
    session.create_session_folder(session_path)

    block_path = session_path.joinpath(block_folder)
    session.create_block_folder(block_path)

    # Create the content that will be uploaded to the session table
    block_content = session.create_default_block()
    block_content.update({
        "user_name": user_name, "rodent_name": rodent_name,
        "data_folder": data_folder, "session_folder": session_folder,
        "session_notes": session_notes, "block_folder": block_folder,
        "block_notes": block_notes, "session_path": str(session_path),
        "block_path": str(block_path),
        })

    db.insert_active_block(block_content)
    return block_content


@app.post("/create_new_block")
async def create_new_block(request: Request,
                           block_folder: str = Form(...),
                           block_notes: str = Form("")):
    # Grab default values
    block_id = f"{len(db.session_table) + 1 :02d}"
    session_properties = db.get_session_properties()
    block_properties = session.create_default_block(block_id=block_id)
    block_content = {**session_properties, **block_properties}

    # Create the appropriate folder architecture
    block_path = Path(block_content["session_path"]).joinpath(block_folder)
    session.create_block_folder(block_path)

    # Add the new block to the session table
    block_content.update({"block_folder": block_folder,
                          "block_notes": block_notes,
                          "block_path": str(block_path)})
    db.insert_active_block(block_content)
    return block_content


@app.get("/dashboard")
async def dashboard(request: Request):
    "Return the main dashboard"
    context = {"request": request,
               "available_cameras": db.get_available_cameras(),
               "available_rpi": db.get_available_rpi(),
               "local_active_processes": db.get_local_active_processes(),
               "rpi_active_processes": db.get_rpi_active_processes()}
    return templates.TemplateResponse("dashboard.html", context=context)


@app.get("/end")
async def end_session():
    "Redirect to the page for validating the end of the session"
    raise NotImplementedError
    kill_all()
    db.save_in_session_folder()


@app.get("/success")
async def success(request: Request, success: bool, message: Optional[str]=""):
    "Return the main dashboard"
    return templates.TemplateResponse("success.html",
                                      context={"request": request,
                                               "success": success,
                                               "message": message})


# Handle processes
@app.get("/kill/{pid}")
async def kill_by_pid(pid: int):
    "Kill a local process using its process ID"
    helpers.kill_by_pid(pid)
    db.remove_local_process(pid)
    return {"pid": pid, "message": f"Killed process {pid}"}


@app.get("/kill_all")
async def kill_all():
    "Kill a local and remote processes"
    # Kill local processes
    local_processes = db.get_local_active_processes()
    local_processes_pids = [int(pid) for pid in local_processes]
    helpers.kill_multiple_by_pid(local_processes_pids)
    db.remove_multiple_local_processes(local_processes_pids)
    # Kill RPI processes
    busy_rpi = db.get_busy_rpi()
    for rpi in busy_rpi:
        rpi_type = rpi["rpi_type"]
        credentials = db.get_rpi_credentials(rpi_type)
        ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
        ssh.kill_all()
        ssh.close()
        db.remove_all_active_process_rpi(rpi_type=rpi_type)

    return {"message": "Killed local and remote processes",
            "local": local_processes_pids,
            "remote": {rpi["rpi_type"]: rpi["active_processes"] for rpi in busy_rpi}}  # noqa E501

@app.get("/test")
async def test():
    return db.get_local_active_processes()

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


# TODO: The finally statement of the script does not seem to be run when running $ kill pid
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
@app.get("/rpi/{rpi_type}/start")
async def start_rpi_process(rpi_type: str):
    "Start PWM with the parameters stored in the config JSON"
    credentials = db.get_rpi_credentials(rpi_type)
    script_path, script_options = db.get_script_parameters(rpi_type)
    ssh = RPI_connector.from_credentials(**credentials)
    pid = ssh.run_script(script_path, script_options)
    ssh.close()
    description = db.get_rpi(rpi_type=rpi_type)["extended_description"]
    db.add_active_process_rpi(rpi_type, pid=pid, description=description)

    return {"message": "Started PWM", "pid": pid}


@app.get("/rpi/{rpi_type}/test_connection")
async def test_rpi_connection(rpi_type: str):
    "Test the connection to the remote raspberry pi"
    credentials = db.get_rpi_credentials(rpi_type)
    connected = RPI_connector.test_connection(**credentials)
    if connected:
        return {"message": "success"}
    else:
        return {"message": "failure"}


# @app.get("/rpi/kill_all")
# async def rpi_kill_all():
#     "Kill all python processes on each remote rpi"
#     # TODO: Use the RPI table to loop over all rpis
#     raise NotImplementedError
#     # ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
#     # ssh.kill_all()
#     # ssh.close()
#     # return {"message": "Killed all python processes"}

@app.get("/test")
def test():
    return {"out": db.get_processes_from_table("rpi")}


@app.get("/rpi/{rpi_type}/kill_all")
async def rpi_kill_all(rpi_type: str):
    "Kill all python processes on a particular rpi"
    credentials = db.get_rpi_credentials(rpi_type)
    ssh = RPI_connector.from_credentials(**param_pwm["ssh"])
    ssh.kill_all()
    ssh.close()
    db.remove_all_active_process_rpi(rpi_type=rpi_type)
    return {"message": f"Killed all python processes on rpi {rpi_type}"}

# TODO: The finally statement doesn't seem to be run when killing a process
@app.get("/rpi/{rpi_type}/kill/{pid}")
async def rpi_kill_process(rpi_type: str, pid: int):
    "Kill a given process on a remote RPI"
    # Connect to the rpi and kill the process
    credentials = db.get_rpi_credentials(rpi_type)
    ssh = RPI_connector.from_credentials(**credentials)
    ssh.kill(pid)
    ssh.close()
    # Update the database
    db.remove_active_process_rpi(rpi_type=rpi_type, pid=pid)
    return {"message": f"Killed process {pid} on rpi {rpi_type}", "pid": pid}


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


# Handle the users (TODO: create the UI for this)
@app.get("/users/new/{user_name}")
@app.put("/users/{user_name}")
async def add_user(user_name: str):
    "Add a new user to the users table"
    db.add_user(user_name)
    return {"message": f"Added {user_name}"}


@app.get("/users/remove/{user_name}")
@app.delete("/users/{user_name}")
async def remove_user(user_name: str):
    "Remove a user from the users table"
    db.remove_user(user_name)
    return {"message": f"Removed {user_name}"}

"""Handling of the tinydb database for run time variables.

TODO: Modularize the database so that we can easily add new tables etc.
      E.G. create a class TIS_CAM_DB with all methods related to the TIS
      camera table and make AcquisitionDB inherit from it.

Author: Romain Fayat, January 2021
"""
from pathlib import Path
from datetime import datetime
from .helpers import read_config, copy_file
from . import tis_camera_win

from tinydb import TinyDB, where, Query
from typing import List
# Serializer
from tinydb_serialization import Serializer
from tinydb_serialization import SerializationMiddleware

TinyDB.DEFAULT_TABLE_KWARGS = {'cache_size': 0}
PATH_DATABASE = ".db.json"
PATH_CONFIG = "config.json"


# Serializer doesn't seem to be working recursively in the tables
class DateTimeSerializer(Serializer):
    "Serializer for storing datetime.datetime objects using tinydb"

    OBJ_CLASS = datetime  # The class this serializer handles

    def __init__(self, date_format="%Y%m%d-%H:%M:%S"):
        "Initialize the date serializer with a specified datetime format"
        self.date_format = date_format
        super().__init__()

    def encode(self, obj):
        "Convert from datetime to string using the custom datetime format"
        return obj.strftime(self.date_format)

    def decode(self, s):
        "Convert from string to datetime using the custom datetime format"
        return datetime.strptime(s, self.date_format)


class PathSerializer(Serializer):
    "Serializer for storing pathlib.Path objects using tinydb"

    OBJ_CLASS = Path  # The class this serializer handles

    def encode(self, obj):
        "Store the path after making it absolute"
        return str(obj.expanduser().absolute())

    def decode(self, s):
        "Create a path object from the stored absolute path"
        return Path(s)


def append_to_list(key_to_target, value_to_append):
    "Create a function appending a value to a list, to be used with db.update"
    def transform(doc):
        "Append an element to the list specified by key_to_target in doc"
        doc[key_to_target].append(value_to_append)
        return doc
    return transform


def update_dict(key_to_target, update_value):
    "Create a function updating a dict, to be used with db.update"
    def transform(doc):
        "Update a dict of doc accessed with key_to_target"
        doc[key_to_target].update(update_value)
        return doc
    return transform


def pop_element(key_to_target, key_to_pop):
    "Create a function to pop an element from a dict, use with db.update"
    def transform(doc):
        "Pop an element from a dict of doc accessed with key_to_target"
        try:
            doc[key_to_target].pop(key_to_pop)
        # key_to_pop not in the dict accessed w/ key_to_target
        except KeyError:
            pass
        return doc
    return transform


def clear_dict(key_to_target):
    "Create a function which clears a dict content, to be used with db.update"
    def transform(doc):
        "Clear a dict of doc accessed with key_to_target"
        try:
            doc[key_to_target] = {}
        # key_to_pop not in the dict accessed w/ key_to_target
        except KeyError:
            pass
        return doc
    return transform


class AcquisitionDB(TinyDB):
    "Enhanced tinydb database for storing the output of offset computations"

    def __init__(self, **kwargs):
        "Initialize the database with extended object type handlers"
        kw = {"path": PATH_DATABASE, "indent": 4}
        kw.update(kwargs)

        # Grab the serializer if provided in the kwargs, else create a new one
        if "storage" in kwargs:
            serialization = kwargs["storage"]
        else:
            serialization = SerializationMiddleware()

        # Add the date and path serializers
        datetime_serializer = DateTimeSerializer()
        serialization.register_serializer(datetime_serializer, 'TinyDate')
        path_serializer = PathSerializer()
        serialization.register_serializer(path_serializer, 'TinyPath')

        # Instantiate the TinyDB using the new serializer
        kwargs.update({"storage": serialization})
        super().__init__(**kw)

    @property
    def rpi_table(self):
        "Table used for storing the rpi parameters and ongoing processes"
        return self.table("rpi")

    @property
    def tis_cam_win_table(self):
        "Table containing the TIS cameras properties and active processes"
        return self.table("tis_cam_win")

    @property
    def session_table(self):
        "Table containining the current session's blocks properties"
        return self.table("session")

    # TODO: Would be nice to have a centralized process table
    # @property
    # def local_processes_table(self):
    #     return self.table("tis_cam_win", cache_size=0)

    # Initialization
    def reinitialize(self):
        "Reinitialize the database for a new session using the config file"
        # Save the session's data if the session was still running
        if self.has_active_block():
            self.save_in_session_folder()
        # Default values for the session, rpi and tis camera parameters
        self.reinitialize_session()
        self.reinitialize_rpi()
        self.reinitialize_tis_cam_win()

    def reinitialize_rpi(self):
        "Reinitialize the rpi table"
        self.drop_table("rpi")
        self.initialize_rpi_pwm()

    def reinitialize_tis_cam_win(self):
        "Reinitialize the TIS camera for windows table"
        config = read_config()
        self.drop_table("tis_cam_win")
        # Use the state files to infer the available cameras
        state_file_folder = Path(config["tis_camera_win"]["saving_path"])
        for state_file_path in state_file_folder.iterdir():
            self.initialize_tiscamera(state_file_path)

    def reinitialize_session(self):
        "Reinitialize the session table"
        self.drop_table("session")

    def save_in_session_folder(self):
        "Save the current tinydb json to the session folder"
        if self.has_session():
            session_path = self.get_session_path()
            copy_file(Path(PATH_DATABASE), session_path.joinpath("db.json"))

    # Session handling
    def has_session(self):
        "Return True if a block is in the session table, else False."
        return len(self.session_table) > 0

    def has_active_block(self):
        "Return True if a block is currently running, else False."
        return self.session_table.contains(where("running") == True)  # noqa E712

    def insert_active_block(self, *args, **kwargs):
        "Set all active blocks to inactive and insert an active block"
        # Set all other blocks to inactive
        self.set_blocks_to_inactive()
        # Insert a new block in the session table
        self.session_table.insert(*args, **kwargs)

    def get_session_properties(self):
        "Grab the session properties from the first block"
        first_block = self.session_table.get(where("block_id") == "01")
        session_properties = ["date", "data_folder", "user_name",
                              "rodent_name", "session_folder",
                              "session_notes", "session_path"]
        return {k: first_block[k] for k in session_properties}

    def get_session_path(self):
        "Return the path to the session directory"
        session_path = self.get_session_properties()["session_path"]
        return Path(session_path)

    def get_active_block(self):
        "Return the currently active block if any"
        return self.session_table.get(where("running") == True)  # noqa E712

    def get_active_block_path(self):
        "Return the path to the active block"
        active_block = self.get_active_block()
        if active_block is not None:
            return Path(active_block["block_path"])
        else:
            raise ValueError

    def set_blocks_to_inactive(self):
        "Set the running property of all blocks to False"
        if self.has_session():
            Q = Query()
            self.session_table.upsert({"running": False}, Q.running.exists())

    # Process handling
    def remove_local_process(self, pid: int):
        "Delete a local process matching a pid from the active process dicts"
        # Table names where local active processes can be found
        for table_name in ["tis_cam_win"]:
            self.remove_local_process_from_table(table_name, pid)

    def remove_multiple_local_processes(self, pid_list: List[int]):
        "Delete multiple local processes matching a pid from the db"
        for pid in pid_list:
            self.remove_local_process(pid)

    def remove_local_process_from_table(self, table_name: str, pid: int):
        "Delete a pid from the active process dict of a given table"
        # Select the target table
        target_table = self.table(table_name)
        # Query to get the element in which the pid is in the active processes
        # WARNING: The pid in the active_processes dict is a str (json format)
        Elem = Query()
        has_selected_pid = Elem.active_processes.test(lambda x: str(pid) in x)
        # Pop the pid from the active_processes dict where it can be found
        operation = pop_element("active_processes", str(pid))
        target_table.update(operation, has_selected_pid)

    def get_processes_from_table(self, table_name: str):
        "Get all local processes from a table"
        # Grab all elements of the table that have active processes
        selected_table = self.table(table_name, cache_size=0)
        has_active_processes = where("active_processes") != {}
        elem_with_active_processes = selected_table.search(has_active_processes)  # noqa E501
        # Loop through the elements with active processes
        active_processes = {}
        for e in elem_with_active_processes:
            active_processes.update(e["active_processes"])
        return active_processes

    def get_local_active_processes(self):
        "Get all local active processes as a dict with key str(pid)"
        active_processes = {}
        for table_name in ["tis_cam_win"]:
            active_processes.update(self.get_processes_from_table(table_name))
        return active_processes

    # TIS camera handling
    def get_video_path(self):
        "Return the path to the video folder of the currently active block"
        active_block_path = self.get_active_block_path()
        return active_block_path.joinpath("videos")

    def initialize_tiscamera(self, state_file_path):
        "Initialize a camera in the tis_cam_win table"
        if tis_camera_win.is_stored_state_file(state_file_path):
            cam_name = tis_camera_win.cam_name_from_state_file(state_file_path)
            cam_entry = {"cam_name": cam_name,
                         "state_file_path": str(state_file_path),
                         "active_processes": {}}
            cam_query = where("cam_name") == cam_name
            self.tis_cam_win_table.upsert(cam_entry, cam_query)

    def get_available_cameras(self):
        "Return the cameras without any ongoing process"
        return self.tis_cam_win_table.search(where("active_processes") == {})

    def get_available_cameras_names(self):
        "Return the names of the cameras without any ongoing process"
        available_cameras = self.get_available_cameras()
        return [c["cam_name"] for c in available_cameras]

    def get_cameras_names_with_recording(self):
        "Return a list of the cameras for which a video was already recorded"
        cam_with_recording = []
        if self.has_active_block():  # Check for the active block only
            try:
                video_path = self.get_video_path()
                for d in video_path.iterdir():  # Lopp over the video folders
                    # Append the name for which data was recorded
                    cam_with_recording.append(d.name)
            except FileNotFoundError:
                pass
        return cam_with_recording

    def get_state_file_path(self, cam_name):
        "Return the path to the state file of a given camera"
        cam_query = where("cam_name") == cam_name
        cam_entry = self.tis_cam_win_table.get(cam_query)
        return cam_entry["state_file_path"]

    def add_tis_cam_process(self, cam_name: str, action: str, pid: int):
        "Add an active process to a tis camera"
        description = f"TIS Camera {action} on {cam_name} (pid: {pid})"
        new_active_process_content = {"action": action,
                                      "pid": pid,
                                      "description": description}
        new_active_process = {pid: new_active_process_content}
        cam_query = where("cam_name") == cam_name  # selection of the camera
        self.tis_cam_win_table.update(
            update_dict("active_processes", new_active_process), cam_query
        )

    # RPI handling
    def initialize_rpi_pwm(self):
        "Initialize the PWM raspberry PI"
        config = read_config()
        process_pwm = config["pwm"]

        description = "PWM RPI"

        # Additional information to be displayed
        options = config["pwm"]["options"]
        host = config["pwm"]["ssh"]["host"]
        options_str = ', '.join([f'{k}: {v}' for k, v in options.items()])
        extended_description = f"Host: {host}\n Parameters: {options_str}"

        # Extend the config data and store it in the rpi_table
        process_pwm.update({"rpi_type": "pwm",
                            "active_processes": {},
                            "description": description,
                            "extended_description": extended_description})
        self.rpi_table.insert(process_pwm)

    def get_available_rpi(self):
        "Return the rpi without any ongoing process"
        return self.rpi_table.search(where("active_processes") == {})

    def get_busy_rpi(self):
        "Return the rpi with ongoing processes"
        return self.rpi_table.search(where("active_processes") != {})

    def get_rpi(self, rpi_type: str):
        "Return the entry in the rpi table matching the input rpi type"
        return self.rpi_table.get(where("rpi_type") == rpi_type)

    def get_rpi_credentials(self, rpi_type):
        "Return the credentials for logging to a rpi via ssh"
        rpi = self.get_rpi(rpi_type)
        return rpi["ssh"]

    def get_script_parameters(self, rpi_type):
        "Return the path to the rpi python script and the linked options"
        rpi = self.get_rpi(rpi_type)
        script_path = rpi["path"]
        script_options = rpi["options"]
        return script_path, script_options

    def add_active_process_rpi(self, rpi_type, pid: int, description: str):
        "Add a new active process to a rpi's active processes field"
        process_properties = {"pid": pid,
                              "action": rpi_type,
                              "description": description,
                              "rpi_type": rpi_type}
        new_process = {str(pid): process_properties}
        self.rpi_table.update(update_dict("active_processes", new_process),
                              where("rpi_type") == rpi_type)

    def remove_active_process_rpi(self, rpi_type: str, pid: int):
        "Remove a processes associated to a pid from the process dict of a rpi"
        self.rpi_table.update(pop_element("active_processes", str(pid)),
                              where("rpi_type") == rpi_type)

    def remove_all_active_process_rpi(self, rpi_type: str):
        "Clear all active processes from the active processes dict of a rpi"
        self.rpi_table.update(clear_dict("active_processes"),
                              where("rpi_type") == rpi_type)

    def get_rpi_active_processes(self):
        "Return all active processes on all remote raspberry pis"
        return self.get_processes_from_table("rpi")

    # Management of the rodent database
    def add_rodent(self, rodent_name, sensor_id):
        "Add a new rodent and its sensor id to the rodents table"
        rodents_table = self.table("rodents")
        rodent_data = {"rodent_name": rodent_name, "sensor_id": sensor_id}
        rodents_table.upsert(rodent_data, where("rodent_name") == rodent_name)

    def remove_rodent(self, rodent_name):
        "Remove a rodent from the rodents table"
        rodents_table = self.table("rodents", cache_size=0)
        rodents_table.remove(where("rodent_name") == rodent_name)

    # Management of the user database
    def add_user(self, user_name):
        "Add a new user to the user table"
        user_table = self.table("users")
        user_data = {"user_name": user_name}
        user_table.upsert(user_data, where("user_name") == user_name)

    def remove_user(self, user_name):
        "Remove an user from the user table"
        user_table = self.table("users")
        user_table.remove(where("user_name") == user_name)

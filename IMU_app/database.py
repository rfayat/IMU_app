"""Handling of the tinydb database for run time variables.

Author: Romain Fayat, January 2021
"""
from pathlib import Path, WindowsPath
from datetime import datetime
from .helpers import read_config
from . import helpers

from tinydb import TinyDB, where
# Serializer
from tinydb_serialization import Serializer
from tinydb_serialization import SerializationMiddleware

PATH_DATABASE = ".db.json"
PATH_CONFIG = "config.json"

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
        return self.table("rpi", cache_size=0)

    @property
    def tis_cam_win_table(self):
        return self.table("tis_cam_win", cache_size=0)

    def reinitialize(self):
        "Reinitialize the database for a new session using the config file"
        config = read_config()

        # Insert the raspberry parameters
        self.drop_table("rpi")
        self.initialize_rpi_pwm()

        # Insert the tis camera parameters
        self.drop_table("tis_cam_win")
        state_file_folder = Path(config["tis_camera_win"]["saving_path"])
        for p in state_file_folder.iterdir():
            self.initialize_tiscamera(p)

    def initialize_tiscamera(self, state_file_path):
        "Initialize a camera in the tis_cam_win table"
        if helpers.is_stored_state_file(state_file_path):
            cam_name = helpers.cam_name_from_state_file(state_file_path)
            cam_entry = {"cam_name": cam_name,
                         "state_file_path": str(state_file_path),
                         "active_processes": []}
            self.tis_cam_win_table.upsert(cam_entry, where("cam_name")==cam_name)

    def initialize_rpi_pwm(self):
        "Initialize the PWM raspberry PI"
        config = read_config()
        process_pwm = config["pwm"]

        description = f"PWM RPI"

        # Additional information to be displayed
        options = config["pwm"]["options"]
        host = config["pwm"]["ssh"]["host"]
        options_str = ', '.join([f'{k}: {v}' for k, v in options.items()])
        extended_description = f"Host: {host}\n Parameters: {options_str}"

        process_pwm.update({"rpi_type": "pwm",
                            "active_processes": [],
                            "description": description,
                            "extended_description": extended_description})
        self.rpi_table.insert(process_pwm)


    def get_available_cameras(self):
        "Return the cameras without any ongoing process"
        return self.tis_cam_win_table.search(where("active_processes")==[])

    def get_available_rpi(self):
        "Return the rpi without any ongoing process"
        return self.rpi_table.search(where("active_processes")==[])

    # Management of the rodent database
    def add_rodent(self, rodent_name, sensor_id):
        "Add a new rodent and its sensor id to the rodents table"
        rodents_table = self.table("rodents", cache_size=0)
        rodent_data = {"rodent_name": rodent_name, "sensor_id": sensor_id}
        rodents_table.upsert(rodent_data, where("rodent_name")==rodent_name)

    def remove_rodent(self, rodent_name):
        "Remove a rodent from the rodents table"
        rodents_table = self.table("rodents", cache_size=0)
        rodents_table.remove(where("rodent_name")==rodent_name)

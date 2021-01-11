"""Helper functions for handling recording sessions.

Author: Romain Fayat, January 2021
"""
from pathlib import Path
from . import helpers


def create_default_block(block_id="01"):
    "Create the content for a new session"
    config = helpers.read_config()

    block_default = {"running": True,
                     "started_on": helpers.now_as_str(),
                     "date": helpers.today_as_str(),
                     "data_folder": config["data_folder"],
                     "block_id": block_id}
    return block_default


def create_session_folder(session_path: Path):
    "Create a session folder architecture"
    pass


def create_block_folder(block_path: Path):
    "Create a block folder architecture"
    pass

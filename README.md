# Web application for IMU data acquisition
## Setup
### Prerequisites
Require Python 3.6+

Clone the repository and install the requirements:
```shell
$ git clone https://github.com/rfayat/IMU_setup.git
$ cd IMU_setup/software/IMU_app
$ pip install -r requirements
```

Install [IC_trigger](https://github.com/rfayat/IMU_setup/tree/master/software/camera_trigger/windows) for windows.


### Configuration
#### Configuration file
A configuration file, needs to be filled following the model of [config_template.json](config_template.json). The path to this configuration file must match the `PATH_CONFIG` variable in [database.py](IMU_app/database.py) (default: `./config.json`).

#### TIS cameras for windows
The parameters of each camera must be saved in an independent **state file**, cf `IC_scripts.live_steam` and its `--output` option.

#### RPI (PWM)
**Warning** for now only one rpi (for pwm) is handled, this will be changed in a future iteration when needed.

On the raspberry pi, clone the `IMU_setup` repository. The path to the [run_pwm.py](https://github.com/rfayat/IMU_setup/blob/master/software/camera_trigger/rpi/run_pwm.py) script must match the one provided in the configuration file.

For instance, with `Documents/IMU_setup/software/camera_trigger/rpi/run_pwm.py` in the configuration file:
```bash
# On the recording computer
$ ssh fayat@XXX.XXX.XX.XXX  # ssh to the RPI
# On the remote RPI
$ cd Documents
$ git clone https://github.com/rfayat/IMU_setup.git
```
### Start the app
Using uvicorn:
```bash
uvicorn IMU_app.main:app --reload
```

## User guide
### Data storage
TBD
### Database structure
TBD

## Todo list
- [ ] Launch the app as a python script and take the path to the configuration file as an argument
- [ ] Make the code more modular to make adding new recording devices more straightforward E.G. create subclasses to handle the different tables of the database.
- [ ] A more extensive use of models in particular when it comes to forms wouldn't hurt
- [ ] Create a table dedicated to recent actions and the associated UI in the dashboard

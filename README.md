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

Install [IC_trigger]() for windows.


### Start the app
Using uvicorn:
```bash
uvicorn IMU_app.main:app --reload
```

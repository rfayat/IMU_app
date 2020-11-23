"""Helpers for connecting to a remote raspberry pi

Author: Romain Fayat, November 2020
"""
import paramiko


class RPI_connector(paramiko.SSHClient):
    "Handle a raspberry pi remotely"

    @classmethod
    def from_credentials(cls, host, port, username, password):
        "Instanciate a SSH connexion from the login credentials"
        self = cls()
        self.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connect(host, port, username, password)
        return self

    def exec_command(self, command):
        "Run a command and return the output"
        _, stdout, _ = super().exec_command(command)
        out = stdout.readlines()
        out = [i.rstrip("\n") for i in out]  # remove trailing \n
        return out

    def run_script(self, path, parameters):
        """Run a python script and return the corresponding PID

        Input
        -----
        path, str
            The path to the script on the remote RPI

        parameters, dict
            A dictionary of parameters that will be passed to the script

        Example:
        -------
        ssh_connection.run_script("~/main.py", {"option": 0})
        Will run:
            nohup python "~/main.py --option 0 >/dev/null 2>&1 & echo $!

        """
        # Reformat the parameters and use them to obtain the command
        params_str = ""
        for k, v in parameters.items():
            params_str = params_str + f"--{k} {v} "
        command = f"nohup python {path} {params_str} >/dev/null 2>&1 & echo $!"
        # Return the PID of the script as an integer
        out = self.exec_command(command)
        return int(out[0])

    def kill(self, pid):
        "Kill a process by pid"
        self.exec_command(f"kill {pid}")


if __name__ == '__main__':
    import time
    from .helpers import config

    # Read the parameter JSON and parse its values
    config_ssh = config["pwm"]["ssh"]
    config_pwm = config["pwm"]["parameters"]
    pwm_path = config["pwm"]["path"]

    ssh = RPI_connector.from_credentials(**config_ssh)
    pid = ssh.run_script(pwm_path, config_pwm)

    time.sleep(3)
    ssh.kill(pid)

import os
def read_config():
    config_path = "/etc/myapp/config.json"
    with open(config_path) as f:
        return f.read()

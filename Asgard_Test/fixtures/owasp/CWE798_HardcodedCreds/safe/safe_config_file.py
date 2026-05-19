import configparser
config = configparser.ConfigParser()
config.read("/etc/myapp/config.ini")
password = config["database"]["password"]

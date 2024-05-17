"""Default values for the wifi_connect module."""
import os.path

DEFAULT_GATEWAY = "192.168.42.1"
DEFAULT_PREFIX = 24
DEFAULT_INTERFACE = "wlan0" # use 'ip link show' to see list of interfaces

DEFAULT_HOTSPOT_SSID = 'Python-Wifi-Connect'
HOTSPOT_CONNECTION_NAME = 'hotspot'
GENERIC_CONNECTION_NAME = 'python-wifi-connect'

DEFAULT_PORT = 80
DEFAULT_UI_PATH = os.path.join(os.path.dirname(__file__), 'ui')

"""Default values for the wifi_connect module."""

DEFAULT_GATEWAY = "192.168.42.1"
DEFAULT_DHCP_RANGE = "192.168.42.2,192.168.42.254"
DEFAULT_PREFIX = 24  # must match with the DHCP range
DEFAULT_INTERFACE = "wlan0" # use 'ip link show' to see list of interfaces

HOTSPOT_CONNECTION_NAME = 'hotspot'
GENERIC_CONNECTION_NAME = 'python-wifi-connect'

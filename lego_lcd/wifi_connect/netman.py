# Start a local hotspot using NetworkManager.

# You must use https://developer.gnome.org/NetworkManager/1.2/spec.html
# to see the DBUS API that the python-NetworkManager module is communicating
# over (the module documentation is scant).

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4
from time import sleep

import NetworkManager

from .defaults import HOTSPOT_CONNECTION_NAME, GENERIC_CONNECTION_NAME
from .defaults import DEFAULT_GATEWAY, DEFAULT_PREFIX, DEFAULT_INTERFACE


class SecurityType(Enum):
    """Enum for the different types of security an AP can have."""
    NONE = 0
    WEP = 1
    WPA = 2
    WPA2 = 4
    ENTERPRISE = 8
    HIDDEN = 16


def delete_all_wifi_connections() -> None:
    """
    Remove ALL wifi connections - to start clean or before running the hotspot.
    """
    # Get all known connections
    connections = NetworkManager.Settings.ListConnections()

    # Delete the '802-11-wireless' connections
    for connection in connections:
        if connection.GetSettings()["connection"]["type"] == "802-11-wireless":
            connection.Delete()
    sleep(2)


def __find_connection(name: str) -> object|None:
    connections = NetworkManager.Settings.ListConnections()
    return next((conn for conn in connections
                 if conn.GetSettings()['connection']['id'] == name), None)


def stop_connection(name: str = GENERIC_CONNECTION_NAME) -> bool:
    """Generic connection stopper / deleter."""
    conn = __find_connection(name)
    if conn is None:
        return False
    conn.Delete()
    sleep(2)
    return True


def get_list_of_access_points() -> dict[str, SecurityType]:
    """
    Return a dictionary of available SSIDs and their security type, or {} for none available or error.
    """
    aps = {}
    for dev in NetworkManager.NetworkManager.GetDevices():
        if dev.DeviceType != NetworkManager.NM_DEVICE_TYPE_WIFI:
            continue
        for ap in dev.GetAccessPoints():
            aps[ap.Ssid] = __get_security_type(ap)
    return aps


def __get_security_type(ap) -> SecurityType:
    """
    Return the security type of the given SSID, or None if not found.
    """
    # Get Flags, WpaFlags and RsnFlags, all are bit OR'd combinations 
    # of the NM_802_11_AP_SEC_* bit flags.
    # https://developer.gnome.org/NetworkManager/1.2/nm-dbus-types.html#NM80211ApSecurityFlags

    security = SecurityType.NONE

    # Based on a subset of the flag settings we can determine which
    # type of security this AP uses.  
    # We can also determine what input we need from the user to connect to
    # any given AP (required for our dynamic UI form).
    if (ap.Flags & NetworkManager.NM_802_11_AP_FLAGS_PRIVACY and
            ap.WpaFlags == NetworkManager.NM_802_11_AP_SEC_NONE and
            ap.RsnFlags == NetworkManager.NM_802_11_AP_SEC_NONE):
        security = SecurityType.WEP

    if ap.WpaFlags != NetworkManager.NM_802_11_AP_SEC_NONE:
        security = SecurityType.WPA

    if ap.RsnFlags != NetworkManager.NM_802_11_AP_SEC_NONE:
        security = SecurityType.WPA2

    if (ap.WpaFlags & NetworkManager.NM_802_11_AP_SEC_KEY_MGMT_802_1X or 
            ap.RsnFlags & NetworkManager.NM_802_11_AP_SEC_KEY_MGMT_802_1X):
        security = SecurityType.ENTERPRISE

    #print(f'{ap.Ssid:15} Flags=0x{ap.Flags:X} WpaFlags=0x{ap.WpaFlags:X} RsnFlags=0x{ap.RsnFlags:X}')

    return security


def connect_to_ap(ssid: str, password: str|None = None, username: str|None = None,
                  conn_name: str = GENERIC_CONNECTION_NAME) -> None:
    """
    Connect to the given SSID with the given optional username and password.
    """
    conn_dict = __generic_connection_dict(conn_name, ssid)
    if password is None:
        # No auth, 'open' connection
        pass

    elif username is None:
        # Hidden, WEP, WPA, WPA2, password required
        conn_dict['802-11-wireless']['security'] = '802-11-wireless-security'
        conn_dict['802-11-wireless-security'] = {'key-mgmt': 'wpa-psk', 'psk': password}

    else:
        # Enterprise, WPA-EAP, username and password required
        conn_dict['802-11-wireless']['security'] = '802-11-wireless-security'
        conn_dict['802-11-wireless-security'] = {'auth-alg': 'open', 'key-mgmt': 'wpa-eap'}
        conn_dict['802-1x'] = {'eap': ['peap'], 'identity': username, 'password': password, 'phase2-auth': 'mschapv2'}
    
    connect_wifi(conn_dict)



def connect_wifi(connection_info: dict) -> None:
    """Create and activate a wifi connection using NetworkManager."""

    name = connection_info['connection']['id']

    # Add and activate the connection
    NetworkManager.Settings.AddConnection(connection_info)
    conn = __find_connection(name)
    dev = next(dev for dev in NetworkManager.NetworkManager.GetDevices()
               if dev.DeviceType == NetworkManager.NM_DEVICE_TYPE_WIFI)
    NetworkManager.NetworkManager.ActivateConnection(conn, dev, "/")

    # Wait for ADDRCONF(NETDEV_CHANGE): wlan0: link becomes ready
    print(f'Waiting for connection to become active...')
    loop_count = 0
    while dev.State != NetworkManager.NM_DEVICE_STATE_ACTIVATED:
        sleep(1)
        loop_count += 1
        if loop_count > 30: # only wait 30 seconds max
            raise TimeoutError(f"Connection {name} failed to activate.")


def __generic_connection_dict(name: str, ssid: str) -> dict:
    return {
        '802-11-wireless': {'mode': 'infrastructure', 'ssid': ssid},
        'connection': {'id': name, 'type': '802-11-wireless', 'uuid': str(uuid4())},
        'ipv4': {'method': 'auto'},
        'ipv6': {'method': 'auto'},
    }


def start_hotspot(ssid: str,
                  address: str = DEFAULT_GATEWAY, prefix: int = DEFAULT_PREFIX,
                  interface: str = DEFAULT_INTERFACE, name: str = HOTSPOT_CONNECTION_NAME) -> None:
    """Start a local hotspot on the wifi interface."""
    conn = __generic_connection_dict(name, ssid)
    conn['802-11-wireless'] |= {'band': 'bg', 'mode': 'ap'}
    conn['connection'] |= {'autoconnect': False, 'interface-name': interface}
    conn['ipv4'] = {'address-data': [{'address': 'address', 'prefix': prefix}],
                    'addresses': [[address, prefix, '0.0.0.0']],
                    'method': 'manual'}
    connect_wifi(conn)


def stop_hotspot(name: str = HOTSPOT_CONNECTION_NAME) -> bool:
    """
    Stop and delete the hotspot.
    Returns True for success or False (for hotspot not found or error).
    """
    return stop_connection(name)


@contextmanager
def hotspot(ssid: str, address: str = DEFAULT_GATEWAY, prefix: int = DEFAULT_PREFIX,
            interface: str = DEFAULT_INTERFACE, name: str = HOTSPOT_CONNECTION_NAME):
    """
    Context manager that starts a hotspot with the given ssid, address, prefix, and interface, and then
    stops it when the context is exited.
    """
    start_hotspot(ssid, address, prefix, interface, name)
    try:
        yield
    finally:
        stop_hotspot(name)

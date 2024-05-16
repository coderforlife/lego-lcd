# Start a local hotspot using NetworkManager.
# Uses the NetworkManager D-Bus API to communicate with NetworkManager.

from contextlib import contextmanager
from enum import Enum
from uuid import uuid4
from time import sleep
from ipaddress import ip_address

import sdbus
from sdbus_block.networkmanager import (
    NetworkManager, NetworkManagerSettings,
    NetworkConnectionSettings, NetworkDeviceGeneric, NetworkDeviceWireless, AccessPoint
)
from sdbus_block.networkmanager.settings import ConnectionProfile
from sdbus_block.networkmanager.enums import DeviceType, DeviceState
try:
    from sdbus_block.networkmanager.enums import (
        WifiAccessPointCapabilitiesFlags, WifiAccessPointSecurityFlags
    )
except ImportError:
    # For older versions of sdbus_block.networkmanager
    from sdbus_block.networkmanager.enums import (
        AccessPointCapabilities as WifiAccessPointCapabilitiesFlags,
        WpaSecurityFlags as WifiAccessPointSecurityFlags
    )

from .defaults import HOTSPOT_CONNECTION_NAME, GENERIC_CONNECTION_NAME
from .defaults import DEFAULT_GATEWAY, DEFAULT_PREFIX, DEFAULT_INTERFACE


# Set the default bus to the system bus - recommended for NetworkManager
sdbus.set_default_bus(sdbus.sd_bus_open_system())


class SecurityType(Enum):
    """Enum for the different types of security an AP can have."""
    NONE = 0
    WEP = 1
    WPA = 2
    WPA2 = 4
    ENTERPRISE = 8
    HIDDEN = 16


def __all_connections() -> list[NetworkConnectionSettings]:
    """Return a list of all known connections."""
    return [NetworkConnectionSettings(path) for path in NetworkManagerSettings().connections]


def __filter_connections(key: str, value) -> list[NetworkConnectionSettings]:
    """Return a list of connections that have the given key and value."""
    return [conn for conn in __all_connections()
            if conn.get_settings()["connection"][key][1] == value]


def __find_connection(name: str) -> NetworkConnectionSettings|None:
    connections = __filter_connections("id", name)
    return connections[0] if connections else None


def __all_wifi_devices() -> list[NetworkDeviceWireless]:
    """Return a list of all known wifi devices."""
    all_devices = [(path, NetworkDeviceGeneric(path)) for path in NetworkManager().devices]
    return [NetworkDeviceWireless(path) for (path, dev) in all_devices
            if dev.device_type == DeviceType.WIFI]


def __first_wifi_device_path() -> str|None:
    """Returns the first known wifi device path."""
    return next((path for path in NetworkManager().devices
                 if NetworkDeviceGeneric(path).device_type == DeviceType.WIFI), None)


def delete_all_wifi_connections() -> None:
    """
    Remove ALL wifi connections - to start clean or before running the hotspot.
    """
    # Delete the '802-11-wireless' connections
    for connection in __filter_connections("type", "802-11-wireless"):
        connection.delete()
    sleep(2)


def stop_connection(name: str = GENERIC_CONNECTION_NAME) -> bool:
    """Generic connection stopper / deleter."""
    conn = __find_connection(name)
    if conn is None:
        return False
    conn.delete()
    sleep(2)
    return True


def get_all_access_points() -> dict[str, SecurityType]:
    """Return a dictionary of available SSIDs and their security type."""
    # Ignores duplicate SSIDs, only keeps the last one found
    aps = {}
    for dev in __all_wifi_devices():
        for ap in (AccessPoint(ap) for ap in dev.access_points):
            # TODO: save max(ap.strength)?
            aps[ap.ssid] = __get_security_type(ap)
    return aps


def __get_security_type(ap: AccessPoint) -> SecurityType:
    """
    Return the security type of the given SSID, or None if not found.
    """
    # The wpa and rsn (i.e. WPA2) flags can be used to determine the general security type
    if (ap.wpa_flags | ap.rsn_flags) & WifiAccessPointSecurityFlags.KEY_MGMT_802_1X:
        return SecurityType.ENTERPRISE
    if ap.rsn_flags != WifiAccessPointSecurityFlags.NONE:
        return SecurityType.WPA2
    if ap.wpa_flags != WifiAccessPointSecurityFlags.NONE:
        return SecurityType.WPA
    if ap.flags & WifiAccessPointCapabilitiesFlags.PRIVACY:
        return SecurityType.WEP
    return SecurityType.NONE


def connect_wifi(conn_info: dict) -> None:
    """Create and activate a wifi connection using NetworkManager."""
    # Add and activate the connection
    dev_path = __first_wifi_device_path()
    profile = ConnectionProfile.from_settings_dict(conn_info)
    NetworkManager().add_and_activate_connection(profile.to_dbus(), dev_path, "/")
    # Wait for the connection to activate
    loop_count = 0
    dev = NetworkDeviceWireless(dev_path)
    while dev.state != DeviceState.ACTIVATED:
        sleep(1)
        loop_count += 1
        if loop_count > 30: # only wait 30 seconds max
            raise TimeoutError(f"Connection {conn_info['connection']['id']} failed to activate.")


def connect_to_ap(ssid: str, password: str|None = None, username: str|None = None,
                  hidden: bool = False, conn_name: str = GENERIC_CONNECTION_NAME) -> None:
    """
    Connect to the given SSID with the given optional username and password.
    """
    conn_dict = __generic_connection_profile(conn_name, ssid, hidden)
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
        conn_dict['802-1x'] = {'eap': ['peap'], 'phase2-auth': 'mschapv2',
                               'identity': username, 'password': password,}

    connect_wifi(conn_dict)


def __get_ip_address_int(ip: str) -> int:
    # the bytes are reversed for NetworkManager...
    return int(ip_address('.'.join(ip.split('.')[::-1])))


def __generic_connection_profile(name: str, ssid: str, hidden: bool = False) -> dict:
    """Return a generic connection profile for the given name and ssid. Has no security."""
    wifi = {'mode': 'infrastructure', 'ssid': ssid}
    if hidden: wifi['hidden'] = True
    return {
        '802-11-wireless': hidden,
        'connection': {'id': name, 'type': '802-11-wireless', 'uuid': str(uuid4())},
        'ipv4': {'method': 'auto'}, 'ipv6': {'method': 'auto'},
    }


def start_hotspot(ssid: str,
                  address: str = DEFAULT_GATEWAY, prefix: int = DEFAULT_PREFIX,
                  interface: str = DEFAULT_INTERFACE, name: str = HOTSPOT_CONNECTION_NAME) -> None:
    """Start a local hotspot on the wifi interface."""
    conn = __generic_connection_profile(name, ssid)
    conn['802-11-wireless'] |= {'band': 'bg', 'mode': 'ap'}
    conn['connection'] |= {'autoconnect': False, 'interface-name': interface}
    conn['ipv4'] = {'address-data': [{'address': address, 'prefix': prefix}], 'gateway': '0.0.0.0',
                    #'addresses': [[__get_ip_address_int(address), prefix, 0]], # 0 == '0.0.0.0'
                    'method': 'manual'}
    connect_wifi(conn)


def stop_hotspot(name: str = HOTSPOT_CONNECTION_NAME) -> bool:
    """Stop and delete the hotspot. Returns True for success or False (for not found)."""
    return stop_connection(name)


@contextmanager
def hotspot(ssid: str, address: str = DEFAULT_GATEWAY, prefix: int = DEFAULT_PREFIX,
            interface: str = DEFAULT_INTERFACE, name: str = HOTSPOT_CONNECTION_NAME):
    """Context manager that runs a hotspot with the given ssid."""
    start_hotspot(ssid, address, prefix, interface, name)
    try:
        yield
    finally:
        stop_hotspot(name)
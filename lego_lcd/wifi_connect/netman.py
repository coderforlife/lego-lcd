# Start a local hotspot using NetworkManager.
# Uses the NetworkManager D-Bus API to communicate with NetworkManager.

from contextlib import contextmanager
from enum import Enum
from dataclasses import dataclass
from uuid import uuid4
from time import sleep
from ipaddress import ip_address
import threading

import sdbus
from sdbus_block.networkmanager import (
    NetworkManager, NetworkManagerSettings, NetworkConnectionSettings,
    NetworkDeviceGeneric, NetworkDeviceWireless, AccessPoint as NMAccessPoint
)
from sdbus_block.networkmanager.settings import ConnectionProfile
from sdbus_block.networkmanager.enums import (
    DeviceType, DeviceState, AccessPointCapabilities, WpaSecurityFlags
)

from .defaults import DEFAULT_HOTSPOT_SSID, HOTSPOT_CONNECTION_NAME, GENERIC_CONNECTION_NAME
from .defaults import DEFAULT_GATEWAY, DEFAULT_PREFIX, DEFAULT_INTERFACE


# We need to use a thread-local variable to store the system bus for NetworkManager
__system_bus = threading.local()


def __ensure_system_bus():
    """Ensure the system bus is set for NetworkManager."""
    if not hasattr(__system_bus, 'bus'):
        __system_bus.bus = sdbus.sd_bus_open_system()
        sdbus.set_default_bus(__system_bus.bus)
    return __system_bus.bus


class SecurityType(Enum):
    """Enum for the different types of security an AP can have."""
    NONE = 0
    WEP = 1
    WPA = 2
    WPA2 = 4
    ENTERPRISE = 8
    HIDDEN = 16


@dataclass
class AccessPoint:
    """An access point with ssid, strength, and security type."""
    ssid: str
    strength: int  # 0-100
    security: SecurityType


def __filter_connections(key: str, value) -> list[NetworkConnectionSettings]:
    """Return a list of connections that have the given key and value."""
    all_conns = [NetworkConnectionSettings(path) for path in NetworkManagerSettings().connections]
    return [conn for conn in all_conns
            if conn.get_settings()["connection"][key][1] == value]


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
    """Remove ALL wifi connections."""
    # Delete the '802-11-wireless' connections
    __ensure_system_bus()
    for connection in __filter_connections("type", "802-11-wireless"):
        connection.delete()
    sleep(2)


def stop_connection(name: str = GENERIC_CONNECTION_NAME) -> str|None:
    """Stop (delete) a connection. Retruns the SSID of the connection if found, otherwise None."""
    __ensure_system_bus()
    conns = __filter_connections("id", name)
    if not conns: return None
    try:
        ssid = conns[0].get_settings()["802-11-wireless"]["ssid"][1].decode('ascii')
    except KeyError:
        ssid = ''
    conns[0].delete()
    sleep(2)
    return ssid


def get_access_point_path(ssid: str) -> str|None:
    """Get the specific object path for an access point with the given SSID."""
    __ensure_system_bus()
    ssid = ssid.encode('ascii')
    options = {'ssids': ('aay', [ssid])}
    devices = __all_wifi_devices()
    for dev in devices: dev.request_scan(options)
    sleep(0.5)  # right after the scan wait a little longer
    for tries in range(9):  # up to ~5 seconds of trying
        sleep(0.5)
        found_path = None
        found_strength = -1
        for dev in devices:
            for ap_path in dev.get_all_access_points():
                ap = NMAccessPoint(ap_path)
                # If the SSID matches and the strength is greater than the last found, update the path
                if ap.ssid == ssid and found_strength < ap.strength:
                    found_path = ap_path
                    found_strength = ap.strength
        if found_path is not None:
            return found_path  # found one - stop trying
    return "/"  # never found one, return the "no specific path"


def get_all_access_points(scan: bool = False) -> list[AccessPoint]:
    """
    Return a list of available and unique access points. The list is sorted by strength.
    The list never includes empty SSIDs. If `scan` is True, this will force a scan of APs.
    """
    __ensure_system_bus()
    devices = __all_wifi_devices()
    if scan:
        # Force a scan of all wifi devices
        for dev in devices: dev.request_scan({})
        sleep(1)  # wait for the scan to complete
    aps = {}
    for dev in devices:
        for ap in (NMAccessPoint(ap) for ap in dev.access_points):
            ssid, strength = ap.ssid.decode('ascii'), ap.strength
            if not ssid: continue  # skip empty SSIDs
            if ssid not in aps or aps[ssid].strength < strength:  # keep the strongest signal
                aps[ap.ssid] = AccessPoint(ssid, strength, __get_security_type(ap))
    return sorted(aps.values(), key=lambda ap: ap.strength, reverse=True)


def __get_security_type(ap: NMAccessPoint) -> SecurityType:
    """
    Return the security type of the given SSID, or None if not found.
    """
    # The wpa and rsn (i.e. WPA2) flags can be used to determine the general security type
    if (ap.wpa_flags | ap.rsn_flags) & WpaSecurityFlags.AUTH_802_1X:  # WifiAccessPointSecurityFlags.KEY_MGMT_802_1X
        return SecurityType.ENTERPRISE
    if ap.rsn_flags != WpaSecurityFlags.NONE:  # WifiAccessPointSecurityFlags.NONE
        return SecurityType.WPA2
    if ap.wpa_flags != WpaSecurityFlags.NONE:  # WifiAccessPointSecurityFlags.NONE
        return SecurityType.WPA
    if ap.flags & AccessPointCapabilities.PRIVACY:  # WifiAccessPointCapabilitiesFlags.PRIVACY
        return SecurityType.WEP
    return SecurityType.NONE


def connect_wifi(conn_info: dict, ap_path: str = "/") -> None:
    """Create and activate a wifi connection using NetworkManager."""
    __ensure_system_bus()

    # Add and activate the connection
    dev_path = __first_wifi_device_path()
    profile = ConnectionProfile.from_settings_dict(conn_info)
    NetworkManager().add_and_activate_connection(profile.to_dbus(), dev_path, ap_path)
    
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
    ap_path = get_access_point_path(ssid)
    conn = __generic_connection_profile(conn_name, ssid)
    if hidden: conn['802-11-wireless']['hidden'] = True

    if password is None:
        # No auth, 'open' connection
        pass

    elif username is None:
        # Hidden, WEP, WPA, WPA2, password required
        conn['802-11-wireless']['security'] = '802-11-wireless-security'
        sec = conn.setdefault('802-11-wireless-security', {})
        sec['key-mgmt'] = 'wpa-psk'
        sec['psk'] = password

    else:
        # Enterprise, WPA-EAP, username and password required
        conn['802-11-wireless']['security'] = '802-11-wireless-security'
        conn['802-1x'] = {'identity': username, 'password': password}
        if ap_path == "/":
            conn['802-11-wireless-security'] = {'auth-alg': 'open', 'key-mgmt': 'wpa-eap'}
            conn['802-1x'] |= {'eap': ['peap'], 'phase2-auth': 'mschapv2'}

    print(conn)
    print(ap_path)
    print(NMAccessPoint(ap_path).ssid)

    connect_wifi(conn, ap_path)


def __generic_connection_profile(name: str, ssid: str) -> dict:
    """Return a generic connection profile for the given name and ssid. Has no security."""
    return {
        '802-11-wireless': {'mode': 'infrastructure', 'ssid': ssid.encode('ascii')},
        'connection': {'id': name, 'type': '802-11-wireless', 'uuid': str(uuid4())},
        'ipv4': {'method': 'auto'}, 'ipv6': {'method': 'auto'},
    }


def start_hotspot(ssid: str = DEFAULT_HOTSPOT_SSID,
                  address: str = DEFAULT_GATEWAY, prefix: int = DEFAULT_PREFIX,
                  interface: str = DEFAULT_INTERFACE, name: str = HOTSPOT_CONNECTION_NAME) -> None:
    """Start a local hotspot on the wifi interface."""
    conn = __generic_connection_profile(name, ssid)
    conn['802-11-wireless'] |= {'band': 'bg', 'mode': 'ap'}
    conn['connection'] |= {'autoconnect': False, 'interface-name': interface}
    conn['ipv4'] = {'address-data': [{'address': address, 'prefix': prefix}], 'gateway': '0.0.0.0',
                    'method': 'manual'}
    connect_wifi(conn)


def stop_hotspot(name: str = HOTSPOT_CONNECTION_NAME) -> str|None:
    """Stop and delete the hotspot. Returns the SSID of the connection if found, otherwise None."""
    return stop_connection(name)


@contextmanager
def hotspot(ssid: str = DEFAULT_HOTSPOT_SSID,
            address: str = DEFAULT_GATEWAY, prefix: int = DEFAULT_PREFIX,
            interface: str = DEFAULT_INTERFACE, name: str = HOTSPOT_CONNECTION_NAME):
    """Context manager that runs a hotspot with the given ssid."""
    start_hotspot(ssid, address, prefix, interface, name)
    try:
        yield
    finally:
        stop_hotspot(name)

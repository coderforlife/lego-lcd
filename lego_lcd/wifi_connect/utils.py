import socket
from urllib.request import urlopen


def local_ip() -> str|None:
    """Returns the local IP of the machine or None it not on the Internet"""
    try:
        socket.setdefaulttimeout(1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 53))
            return s.getsockname()[0].decode('ascii')
    except Exception: return None


def external_ip() -> str|None:
    """Returns the external IP of the machine or None it not on the Internet"""
    try:
        with urlopen('https://checkip.amazonaws.com') as page:
            return page.read().decode('ascii')
    except Exception: return None


def have_internet():
    """Returns True if on the Internet"""
    return local_ip() is not None


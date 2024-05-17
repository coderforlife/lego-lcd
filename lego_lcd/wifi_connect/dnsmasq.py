# start / stop the dnsmasq process

from contextlib import contextmanager
import subprocess, time
from ipaddress import IPv4Address
from typing import Optional

from .defaults import DEFAULT_INTERFACE, DEFAULT_GATEWAY, DEFAULT_PREFIX


def stop(pid: Optional[int] = None) -> None:
    """
    Stop the dnsmasq process. If pid is not provided, it will attempt to find the PID of the
    dnsmasq process by running 'ps -e' and grepping for ' dnsmasq'. If it fails to find the PID,
    it will return without doing anything.
    """
    if pid is None:
        try:
            pid = int(subprocess.run("ps -e | grep ' dnsmasq' | cut -c 1-6",
                                     shell=True, capture_output=True, text=True,
                                     check=True).stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return
    subprocess.run(["kill", "-9", str(pid)])


def start(interface: str = DEFAULT_INTERFACE, gateway: str = DEFAULT_GATEWAY,
          prefix: int = DEFAULT_PREFIX) -> int:
    """
    Start the dnsmasq process with the given interface, gateway, and prefix. Returns the PID of
    the dnsmasq process started.
    """
    # first kill any existing dnsmasq
    stop()

    # create the dhcp range string
    dhcp_range = __create_DHCP_range(gateway, prefix)

    # run dnsmasq in the background and save a reference to the object
    args = ["/usr/sbin/dnsmasq", f"--address=/#/{gateway}", f"--dhcp-range={dhcp_range}",
            f"--dhcp-option=option:router,{gateway}", f"--interface={interface}",
            "--keep-in-foreground", "--bind-interfaces", "--except-interface=lo",
            "--conf-file", "--no-hosts"]
    ps = subprocess.Popen(args)
    # don't wait here, proc runs in background until we kill it.

    # give a few seconds for the proc to start
    time.sleep(2)
    return ps.pid


@contextmanager
def dnsmasq(interface: str = DEFAULT_INTERFACE, gateway: str = DEFAULT_GATEWAY,
            prefix: int = DEFAULT_PREFIX):
    """
    Context manager that starts dnsmasq with the given interface, gateway, and prefix, and then
    stops it when the context is exited.
    """
    pid = start(interface, gateway, prefix)
    try:
        yield
    finally:
        stop(pid)


def __create_DHCP_range(gateway: str, prefix: int) -> str:
    """
    Create a DHCP range string for the given gateway and prefix. The range will be from the first
    available IP address to the last available IP address, excluding the gateway and broadcast
    addresses.
    """
    ip = IPv4Address(gateway)
    ip_int = int(ip)
    lower_bits = (1 << (32 - prefix)) - 1
    ip_prefix = ip_int & ~lower_bits
    first = IPv4Address(ip_prefix)
    if first.packed[-1] == 0: first = __inc_ip(first)
    middle = IPv4Address(ip_int)
    last = IPv4Address(ip_prefix + lower_bits)
    if last.packed[-1] == 255: last = __dec_ip(last)
    range_a = int(middle) - int(first)
    range_b = int(last) - int(middle)
    return f"{first},{__dec_ip(middle)}" if range_a > range_b else f"{__inc_ip(middle)},{last}"
    

def __inc_ip(ip: IPv4Address) -> IPv4Address:
    """Increment the IP address by one."""
    return IPv4Address(int(ip) + 1)


def __dec_ip(ip: IPv4Address) -> IPv4Address:
    """Decrement the IP address by one."""
    return IPv4Address(int(ip) - 1)

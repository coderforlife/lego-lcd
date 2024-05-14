# start / stop the dnsmasq process

from contextlib import contextmanager
import subprocess, time
from typing import Optional

from .defaults import DEFAULT_INTERFACE, DEFAULT_GATEWAY, DEFAULT_DHCP_RANGE


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
          dhcp_range: str = DEFAULT_DHCP_RANGE) -> int:
    """
    Start the dnsmasq process with the given interface, gateway, and dhcp_range. Returns the PID of
    the dnsmasq process started.
    """
    # first kill any existing dnsmasq
    stop()

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
            dhcp_range: str = DEFAULT_DHCP_RANGE):
    """
    Context manager that starts dnsmasq with the given interface, gateway, and dhcp_range, and then
    stops it when the context is exited.
    """
    pid = start(interface, gateway, dhcp_range)
    try:
        yield
    finally:
        stop(pid)

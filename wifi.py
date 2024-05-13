#!/usr/bin/env python
"""
Perform a scan for wireless access points and prints them out.
Root access is required to issue a scan request to the kernel.

This is a significantly modified version of the example from the libnp package:
    https://github.com/Robpol86/libnl/blob/master/example_scan_access_points.py

Debug messages by settings the NLCB env var to either 'verbose' or 'debug':
    NLCB=debug ./wifi.py ...
"""

# requires: libnl

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

__ALL__ = ("WifiNetwork", "NLError", "wifi_scan")

class WifiNetwork(object):
    """
    Represents a Wifi Network including the SSID, BSSID, channel, signal, quality, and
    encryption.
    """
    def __init__(self, ssid, bssid, channel, signal, quality, encryption):
        self.ssid = ssid
        self.bssid = bssid
        self.channel = channel
        self.signal = signal
        if quality is None and signal is not None:
            quality = max(min((signal + 110) / 70, 1.0), 0.0)
        self.quality = quality
        self.encryption = encryption
    @property
    def encrypted(self): return self.encryption not in (None, 'open') 
    @property
    def needs_key(self): return self.encrypted and not self.needs_user_passwd
    @property
    def needs_user_passwd(self): return self.encrypted and '-802.1X' in self.encryption
    def __str__(self):
        return 'WIFI: "%s", %s, Ch. %d, %.1f dBm, %.0f%%, %s'%(self.ssid, self.bssid,
            self.channel, self.signal, self.quality*100, self.encryption)
    def __repr__(self):
        return 'WifiNetwork(%r, %r, %r, %r, %r, %r)'%(self.ssid, self.bssid,
            self.channel, self.signal, self.quality, self.encryption)

class NLError(OSError):
    """An error in the libnl library."""
    def __init__(self, err, func=None):
        from libnl.error import errmsg
        msg = errmsg[abs(err)]
        super(NLError, self).__init__(err, msg)
        self.func = func
        if func: self.message = '%s() returned %d (%s)' % (func, err, msg)

def __check(func, *args, **kwargs):
    """Raise an error if func(*args, **kwargs) returns a negative number."""
    ret = func(*args, **kwargs)
    if ret < 0: raise NLError(ret, func.__name__)
    return ret

def __create_ifidx_msg(sk, flags, cmd, if_index):
    """Creates am nl_msg with the given IFINDEX attribute."""
    from libnl.msg import nlmsg_alloc
    from libnl.genl.ctrl import genl_ctrl_resolve
    from libnl.genl.genl import genlmsg_put
    from libnl.attr import nla_put_u32
    from libnl.nl80211.nl80211 import NL80211_ATTR_IFINDEX
    msg = nlmsg_alloc()
    driver_id = __check(genl_ctrl_resolve, sk, b'nl80211')
    genlmsg_put(msg, 0, 0, driver_id, 0, flags, cmd, 0)
    nla_put_u32(msg, NL80211_ATTR_IFINDEX, if_index)
    return msg
    
def __create_callback(cb, arg):
    """Creates a callback setting VALID to the given function."""
    from libnl.handlers import nl_cb_alloc, nl_cb_set
    from libnl.handlers import NL_CB_DEFAULT, NL_CB_VALID, NL_CB_CUSTOM
    nlcb = nl_cb_alloc(NL_CB_DEFAULT)
    nl_cb_set(nlcb, NL_CB_VALID, NL_CB_CUSTOM, cb, arg)
    return nlcb

def __cb_trigger(msg, arg):
    """Called when the kernel is done scanning. Only signals if it was successful or if it failed. No other data.
    Positional arguments:
    msg -- nl_msg class instance containing the data sent by the kernel.
    arg -- mutable integer (ctypes.c_int()) to update with results.
    Returns:
    An integer, value of NL_SKIP. It tells libnl to stop calling other callbacks for this message and proceed with
    processing the next kernel message.
    """
    from libnl.linux_private.genetlink import genlmsghdr
    from libnl.msg import nlmsg_data, nlmsg_hdr
    from libnl.nl80211.nl80211 import NL80211_CMD_SCAN_ABORTED, NL80211_CMD_NEW_SCAN_RESULTS
    from libnl.handlers import NL_SKIP
    hdr = genlmsghdr(nlmsg_data(nlmsg_hdr(msg)))
    # also recieves NL80211_CMD_TRIGGER_SCAN when first initiated
    if hdr.cmd == NL80211_CMD_SCAN_ABORTED: arg[0] = False # scan was aborted for some reason
    elif hdr.cmd == NL80211_CMD_NEW_SCAN_RESULTS: arg[0] = True # scan completed successfully
    return NL_SKIP

def __wifi_scan_trigger(sk, if_index):
    """
    Issue a scan request to the kernel and wait for it to reply with a signal.
    This function issues NL80211_CMD_TRIGGER_SCAN which requires root privileges.
    The way NL80211 works is first you issue NL80211_CMD_TRIGGER_SCAN and wait for the kernel to
    signal that the scan is done. When that signal occurs, data is not yet available. The signal
    tells us if the scan was aborted or if it was successful (if new scan results are waiting).
    This function handles that simple signal.
    """
    from libnl.genl.ctrl import genl_ctrl_resolve_grp
    from libnl.socket_ import nl_socket_add_membership, nl_socket_drop_membership
    from libnl.msg import nlmsg_alloc
    from libnl.attr import nla_put, nla_put_nested
    from libnl.handlers import nl_cb_set, nl_cb_err
    from libnl.nl import nl_send_auto, nl_recvmsgs
    from libnl.nl80211.nl80211 import NL80211_CMD_TRIGGER_SCAN, NL80211_ATTR_SCAN_SSIDS
    from libnl.handlers import NL_CB_CUSTOM, NL_CB_ACK, NL_CB_SEQ_CHECK, NL_OK, NL_STOP

    # First get the "scan" membership group ID and join the socket to the group
    mcid = __check(genl_ctrl_resolve_grp, sk, b'nl80211', b'scan')
    __check(nl_socket_add_membership, sk, mcid) # Listen for results of scan requests

    # Setup which command to run and which interface to use
    msg = __create_ifidx_msg(sk, 0, NL80211_CMD_TRIGGER_SCAN, if_index)
    ssids_to_scan = nlmsg_alloc()
    nla_put(ssids_to_scan, 1, 0, b'') # Scan all SSIDs
    nla_put_nested(msg, NL80211_ATTR_SCAN_SSIDS, ssids_to_scan) # Setup what kind of scan to perform

    # Setup the callbacks to be used for triggering the scan only
    res,ack,err = [None],[False],[False]
    cb = __create_callback(__cb_trigger, res)
    def err_cb(msg, err, arg): arg[0] = err.error; return NL_STOP # update the arg with the error code
    def ack_cb(msg, arg): arg[0] = True; return NL_STOP # update the arg with 0 as acknowledgement
    def seq_cb(msg, arg): return NL_OK # ignore sequence checking
    nl_cb_err(cb, NL_CB_CUSTOM, err_cb, err)
    nl_cb_set(cb, NL_CB_ACK, NL_CB_CUSTOM, ack_cb, ack)
    nl_cb_set(cb, NL_CB_SEQ_CHECK, NL_CB_CUSTOM, seq_cb, None)

    # Now we send the message to the kernel and retrieve the acknowledgement. The kernel takes a
    # few seconds to finish scanning for access points.
    __check(nl_send_auto, sk, msg)
    while not ack[0]: __check(nl_recvmsgs, sk, cb)
    if err[0]: raise NLError(err[0])

    # Block until the kernel is done scanning or aborted the scan
    while res[0] is None: __check(nl_recvmsgs, sk, cb)
    if not res[0]: raise RuntimeError('the kernel aborted the scan')

    # Clean up
    __check(nl_socket_drop_membership, sk, mcid) # No longer receive multicast messages

def __nla_data(data):
    from libnl.attr import nla_data, nla_len
    return nla_data(data)[:nla_len(data)]
    
def __merge(d, u):
    from collections import Mapping
    for k, v in u.iteritems():
        v2 = d.get(k)
        d[k] = __merge(v2, v) if isinstance(v, Mapping) and isinstance(v2, Mapping) else v
    return d

def __cb_dump(msg, results):
    """
    Here is where SSIDs and their data is decoded from the binary data sent by the kernel.
    This function is called once per SSID. Everything in `msg` pertains to just one SSID.
    
    msg     nl_msg class instance containing the data sent by the kernel
    results dictionary to populate with parsed data
    """
    from libnl.linux_private.genetlink import genlmsghdr
    from libnl.msg import nlmsg_data, nlmsg_hdr
    from libnl.attr import nla_parse, nla_parse_nested, nla_get_u8, nla_get_u16, nla_get_u32
    from libnl.genl.genl import genlmsg_attrdata, genlmsg_attrlen
    from libnl.nl80211.iw_scan import bss_policy, get_ies, WLAN_CAPABILITY_PRIVACY
    from libnl.nl80211.nl80211 import (NL80211_ATTR_MAX, NL80211_ATTR_BSS, NL80211_BSS_MAX,
        NL80211_BSS_BSSID, NL80211_BSS_CAPABILITY, NL80211_BSS_INFORMATION_ELEMENTS,
        NL80211_BSS_BEACON_IES, NL80211_BSS_SIGNAL_MBM, NL80211_BSS_SIGNAL_UNSPEC,
        NL80211_BSS_STATUS, NL80211_BSS_STATUS_AUTHENTICATED, NL80211_BSS_STATUS_ASSOCIATED, NL80211_BSS_STATUS_IBSS_JOINED)
    from libnl.handlers import NL_SKIP

    # Parse perform initial parsing of message and check for errors
    hdr = genlmsghdr(nlmsg_data(nlmsg_hdr(msg)))
    tb = {} #i:None for i in xrange(NL80211_ATTR_MAX + 1)}
    nla_parse(tb, NL80211_ATTR_MAX, genlmsg_attrdata(hdr, 0), genlmsg_attrlen(hdr, 0), None)
    if NL80211_ATTR_BSS not in tb: return NL_SKIP
    bss = {}
    if nla_parse_nested(bss, NL80211_BSS_MAX, tb[NL80211_ATTR_BSS], bss_policy): return NL_SKIP
    if NL80211_BSS_BSSID not in bss or NL80211_BSS_INFORMATION_ELEMENTS not in bss: return NL_SKIP

    # Gather all of the important information directly in BSS data
    bssid = '%02x:%02x:%02x:%02x:%02x:%02x'%tuple(__nla_data(bss[NL80211_BSS_BSSID])[:6])
    cap = nla_get_u16(bss[NL80211_BSS_CAPABILITY]) if NL80211_BSS_CAPABILITY in bss else 0
    signal,quality,status = None,None,None
    if NL80211_BSS_SIGNAL_UNSPEC in bss:
        quality = nla_get_u8(bss[NL80211_BSS_SIGNAL_UNSPEC]) / 100 # 0.0 to 1.0
    if NL80211_BSS_SIGNAL_MBM in bss:
        u32 = nla_get_u32(bss[NL80211_BSS_SIGNAL_MBM])
        signal = (-(u32 & 0x80000000) + (u32 & 0x7fffffff)) / 100 # dBm
    if NL80211_BSS_STATUS in bss:
        statuses = { NL80211_BSS_STATUS_AUTHENTICATED : 'authenticated',
                     NL80211_BSS_STATUS_ASSOCIATED    : 'associated',
                     NL80211_BSS_STATUS_IBSS_JOINED   : 'joined' }
        status = nla_get_u32(bss[NL80211_BSS_STATUS])
        status = statuses.get(status, '0x%x'%status)
    
    # Gather all of the important information from the BSS Information Elements (ies)
    ies = __merge(get_ies(__nla_data(bss[NL80211_BSS_BEACON_IES])) if NL80211_BSS_BEACON_IES in bss else {},
                  get_ies(__nla_data(bss[NL80211_BSS_INFORMATION_ELEMENTS])))
    ssid,channel = ies.get('SSID') or ies.get('MESH ID') or '', ies.get('DS Parameter set')
    if bool(cap & WLAN_CAPABILITY_PRIVACY):
        if 'RSN' in ies or 'WPA' in ies:
            wpa2 = 'RSN' in ies
            encryption = 'WPA2' if wpa2 else 'WPA'
            auth = ies['RSN' if wpa2 else 'WPA'].get('authentication_suites', 'IEEE 802.1X')
            if 'IEEE 802.1X' in auth: encryption += '-802.1X'
            elif 'PSK' not in auth: pass # TODO: auth suite unknown, how to handle it? e.g. TDLS/TPK
        else: encryption = 'WEP'
    else: encryption = 'open'
    
    # Save the information gathered
    results[bssid] = WifiNetwork(ssid, bssid, channel, signal, quality, encryption)
    return NL_SKIP

def __wifi_scan_results(sk, if_index):
    """
    Retrieve the results of a successful scan (SSIDs and data about them).
    This function does not require root privileges. Returns a list.
    """
    from libnl.nl import nl_send_auto, nl_recvmsgs
    from libnl.nl80211.nl80211 import NL80211_CMD_GET_SCAN
    from libnl.linux_private.netlink import NLM_F_DUMP
    results = {}
    msg = __create_ifidx_msg(sk, NLM_F_DUMP, NL80211_CMD_GET_SCAN, if_index)
    cb = __create_callback(__cb_dump, results)
    __check(nl_send_auto, sk, msg)
    __check(nl_recvmsgs, sk, cb)
    return results.values()

def __get_wlan0_idx():
    """Gets the interface index (IFINDEX) of the wlan0 interface."""
    from socket import socket, AF_INET, SOCK_DGRAM
    from struct import pack, unpack
    from fcntl import ioctl
    from contextlib import closing
    with closing(socket(AF_INET, SOCK_DGRAM)) as s:
        return unpack('16sI', ioctl(s.fileno(), 0x8933, pack('16sI', b'wlan0', 0)))[1]

def wifi_scan(sudo=True):
    """Scan for wifi networks and return a list of networks."""
    from libnl.socket_ import nl_socket_alloc
    from libnl.genl.genl import genl_connect
    
    # Get the index of the wlan0 interface
    if_index = __get_wlan0_idx()

    # Open a socket to the kernel and bind to it
    sk = nl_socket_alloc() # creates an `nl_sock` instance
    __check(genl_connect, sk) # create file descriptor and bind socket

    # Scan for access points
    if sudo: __wifi_scan_trigger(sk, if_index)
    return __wifi_scan_results(sk, if_index)
    
if __name__ == '__main__':
    wifis = wifi_scan()
    print('Found %d access points:'%len(wifis))
    for row in wifis: print(row)
    # TODO: row.ssid.replace('\0', '')?
 
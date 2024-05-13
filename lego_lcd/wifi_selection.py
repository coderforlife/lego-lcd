#!/usr/bin/env python

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

# requires: Cython, <wifi>, <kbd>, <lcd>, <lcd_helper>

__all__ = ["has_internet", "local_ip", "external_ip", "run_select_wifi", "select_wifi"]

WIFI_CUSTOM_CHARS = (
    # Wifi Signal Strength Bars
    b'\x00\x00\x00\x00\x00\x00\x00\x1B',
    b'\x00\x00\x00\x00\x00\x00\x18\x1B',
    b'\x00\x00\x00\x00\x03\x03\x1B\x1B',
    b'\x00\x00\x18\x18\x18\x18\x18\x1B',
    b'\x03\x03\x1B\x1B\x1B\x1B\x1B\x1B',
    # Ellipsis
    b'\x00\x00\x00\x00\x00\x00\x00\x15',
    # Lock
    b'\x04\x0A\x0A\x1F\x11\x15\x11\x1F',
)
WIFI_BARS = ( b'\x00\x00', b'\x01\x00', b'\x02\x00', b'\x02\x03', b'\x02\x04' )
ELLIPSIS = b'\x05'
LOCKED,UNLOCKED = b'\x06 '
UP,DOWN = b'\xC5\xC6'

from lcd_helper import LCD_DIM

# Keyboard helpers
from kbd import KEY_F1, KEY_HELP, KEY_H, KEY_ESC, KEY_Q, KEY_ENTER, KEY_KPENTER, KEY_BACKSPACE, KEY_DELETE
from kbd import KEY_UP, KEY_DOWN, KEY_F5
HELP_KEYS = (KEY_F1, KEY_HELP, KEY_H, b'h', b'H', b'?')
QUIT_KEYS = (KEY_ESC, KEY_Q, b'q', b'Q')
ENTER_KEYS = (KEY_ENTER, KEY_KPENTER, b'\n')
def __unwrap(x): return x[0] if isinstance(x, tuple) else x


def get_wifi_cell_ssid(cell, width):
    """Gets a wifi cell's SSID to display on the LCD using the ELLIPSIS character if necessary."""
    # TODO: sometimes I get \x00\x00\x00\x00\x00\x00\x00... - unclear if this is the actual name of it or not
    from lcd_helper import as_bytes
    ssid = as_bytes(cell.ssid)
    if len(ssid) == 0: ssid = b'{' + cell.bssid + b'}'
    return ssid if len(ssid) <= width else (ssid[:(width-1)]+ELLIPSIS)
    
def get_wifi_cell_info(cell):
    """Gets the wifi cell's information to display on the LCD when selecting a network."""
    bars = int(round(cell.quality * len(WIFI_BARS)))
    lock = LOCKED if cell.encrypted else UNLOCKED
    return b'%s %s %s' % (WIFI_BARS[bars], lock, cell.encryption)

def get_wifi_cells():
    """
    Gets a list of available wifi cells, each item has at least the following properties:
        ssid        string
        bssid       bytes like XX:XX:XX:XX:XX:XX
        encrypted   True or False
        encryption  one of b'open', b'WEP', b'WPA', b'WPA2', b'WPA-802.1X', ...
        quality     float from 0.0 to 1.0
    The list will be sorted from highest quality to lowest quality.
    """
    from wifi import wifi_scan
    
    # Get all available wifi cells and convert some fields to bytes and sort them by quality
    cells = wifi_scan()
    for cell in cells:
        cell.bssid = cell.bssid.encode('ascii')
        cell.encryption = cell.encryption.encode('ascii')
    cells.sort(key=lambda c:c.quality, reverse=True)
    
    # Filter out duplicate SSIDs (keeping higher quality one)
    dups = set()
    cells_out = []
    for cell in cells:
        id = cell.ssid,cell.encryption
        if id in dups: continue
        dups.add(id)
        cells_out.append(cell)

    # Returns a sorted list of cells with duplicated removed
    return cells_out
    
def show_select_wifi_help(kbd, lcd):
    """Shows a help screen about selecting the network and waits for any key."""
    lcd.write_all(UP+DOWN+b' Choose \xC4   Select', b'F5 Reload ESC Cancel')
    kbd.get() # wait for any key

def show_read_key_help(kbd, lcd):
    """Shows a help screen about typing in a wifi key and waits for any key."""
    state = lcd.state
    lcd.blink = False
    lcd.write_all(b'\xC4 Okay ESC Cancel', b'\xF9 Delete DEL Clear')
    kbd.get() # wait for any key
    lcd.state = state
    
def show_connected_wifi(kbd, lcd, cell, success=True):
    """Show message that we succeeded or failed to connect."""
    from lcd_helper import beep
    if not success: beep()
    msg = b'Success! Connected to ' if success else b'Failed to connect to '
    lcd.write_text(msg +  get_wifi_cell_ssid(cell, LCD_DIM[0]), 'center', ELLIPSIS)
    kbd.get() # wait for any key

def show_invalid_wifi_entry(kbd, lcd, cell, name):
    """Show message that the key/username/password is invalid."""
    from lcd_helper import beep
    beep()
    lcd.write_text(b'Invalid %s for %s' % (name, cell.encryption), 'center', ELLIPSIS)
    kbd.get() # wait for any key

def __read_text(kbd, lcd, max_len, display):
    """Internal function for read_text and read_password."""
    from lcd_helper import beep
    text = b''
    while True:
        display(text)
        ch = __unwrap(kbd.get())
        if isinstance(ch, bytes) and b' ' <= ch <= b'~':
            if len(text) < max_len: text += ch
            else: beep()
        elif ch in HELP_KEYS: show_read_key_help(kbd, lcd)
        elif ch in QUIT_KEYS: text = None; break
        elif ch in ENTER_KEYS: break
        elif ch == KEY_BACKSPACE: text = text[:len(text)-1]
        elif ch == KEY_DELETE: text = b''
        else: beep()
    return text

def read_text(kbd, lcd, loc, max_len=64):
    """
    Reads some text from the keyboard displaying the results on the LCD and scrolling as necessary.
    The start of the text is from loc. The text is only allowed to be max_len characters, after
    which a beep is emmited. Special, non-printing, keys also produce a beep.
    
    The ESC key cancels and returns None. The Enter causes the text to be returned. F1 shows a
    help screen. Backspace deletes the last character. Delete clears the text.
    """
    max_width = LCD_DIM[0] - loc[1]
    clear = b' '*max_width
    def __display(text):
        lcd.write_at(loc, clear)
        out = text if max_width > len(text) else (ELLIPSIS + text[-max_width+2:])
        lcd.write_at(loc, out)
    orig_blink = lcd.blink
    lcd.blink = True
    text = __read_text(kbd, lcd, max_len, __display)
    lcd.blink = orig_blink
    return text
    
def read_password(kbd, lcd, loc, max_len=64):
    """
    Reads a key or password from the keyboard displaying the number of characters typed on the LCD
    at the location given. The key is only allowed to be max_len characters, after which a beep is
    emmited. Special, non-printing, keys also produce a beep.
    
    The ESC key cancels and returns None. The Enter causes the key to be returned. F1 shows a
    help screen. Backspace deletes the last character. Delete clears the key.
    """
    def __display(key): lcd.write_at(loc, b'%2d'%len(key))
    return __read_text(kbd, lcd, max_len, __display)
    
def is_hex(s):
    """Checks if a string only has hex digits in it"""
    from string import hexdigits
    return all(c in hexdigits for c in s)

def create_wpa_suplicant_entry(cell, key=None):
    """Creates a network entry for the wpa_supplicant.conf file and returns it as a string."""
    # see https://www.daemon-systems.org/man/wpa_supplicant.conf.5.html for details on format
    # more details available at http://www.cs.upc.edu/lclsi/Manuales/wireless/files/wpa_supplicant.conf
    s = '\nnetwork={\n'
    s += '  ssid="%s"\n'%cell.ssid
    if len(cell.ssid) == 0: s += '  bssid=%s\n'%cell.bssid
    if not cell.encrypted:
        # Open
        s += '  key_mgmt=NONE\n'
    elif cell.encryption == b'WEP':
        # WEP
        s += '  key_mgmt=NONE\n'
        s += '  wep_key0=%s\n'%key
        s += '  wep_tx_keyidx=0\n'
    elif cell.needs_key:
        # WPA and WPA2 with PSK
        # could use proto=WPA or proto=WPA2 to force one or the other (default is either)
        s += '  key_mgmt=WPA-PSK\n'
        s += '  psk="%s"\n'%key
    else:
        # WPA and WPA2 with login information
        user,pword = key
        s += '  key_mgmt=WPA-EAP\n'
        s += '  identity="%s"\n'%user
        s += '  anonymous_identity="anonymous%s"'%(user[user.rindex('@'):] if '@' in user else "")
        s += '  password="%s"\n'%pword
        # TODO: ca_cert="/etc/cert/ca.pem"
        # TODO: needs phase2="auth=MSCHAPV2" ?
    s += '}\n'
    return s
    
def add_wpa_suplicant_entry(kbd, lcd, cell, key=None, interface='wlan0'):
    """
    Adds a network entry to the wpa_supplicant.conf file and restarts the wlan interface. This
    requires root access. After connecting a message is shown on the LCD.
    """
    from subprocess import check_call, CalledProcessError
    from time import sleep

    lcd.write_text(b'Connecting...', 'center')

    # Add the entry to the wpa_supplicant network list
    entry = create_wpa_suplicant_entry(cell, key)
    with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'a') as f:
        f.write(entry)

    # Restart the wireless
    try: check_call(['ifdown',interface])
    except CalledProcessError as ex: pass
    sleep(0.1)
    success = True
    try: check_call(['ifup',interface])
    except CalledProcessError as ex: success = False

        
    # Check if we actually have internet acccess
    if success:
        niters = 0
        success = False
        while not success and niters < 100:
            niters += 1
            sleep(0.25)
            success = has_internet()
        print("tries: ", niters)

    # Show success or failure message on LCD
    show_connected_wifi(kbd, lcd, cell, success)
    return success

def connect_wifi(kbd, lcd, cell):
    """Connect to the given wifi cell."""
    # Open network - no encryption
    if not cell.encrypted: return add_wpa_suplicant_entry(kbd, lcd, cell)

    # Some form of encryption, will need to type a key
    # TODO: if there is already a key for this SSID use it
    lcd.write_all(get_wifi_cell_ssid(cell, LCD_DIM[0]),
                  b'Key:    chars' if cell.needs_key else b'User: ')

    if cell.encryption == b'WEP':
        # WEP - simple PSK of either hex or ASCII chars of certain lengths
        key = read_password(kbd, lcd, (1, 5), 58)
        if key is None or len(key) == 0: return False
        if len(key) in (10,26,32,58) and is_hex(key) or len(key) in (5,13,16,29):
            return add_wpa_suplicant_entry(kbd, lcd, cell, key)
        show_invalid_wifi_entry(kbd, lcd, cell, b'key')
        return False
        
    if cell.needs_key:
        # WPA and WPA2 with PSK - either 64 hex characters or 8-63 ASCII characters
        key = read_password(kbd, lcd, (1, 5), 64)
        if key is None or len(key) == 0: return False
        if len(key) == 64 and is_hex(key) or 8 <= len(key) <= 63:
            return add_wpa_suplicant_entry(kbd, lcd, cell, key)
        show_invalid_wifi_entry(kbd, lcd, cell, b'key')
        return False
        
    # WPA and WPA IEEE 802.1X has a username and password
    user = read_text(kbd, lcd, (1, 6), 64)
    if user is None or len(user) == 0: return False
    lcd.write_at((1, 0), b'Password:    chars  ')
    pword = read_password(kbd, lcd, (1, 10), 64)
    if pword is None or len(pword) == 0: return False
    return add_wpa_suplicant_entry(kbd, lcd, cell, (user,pword))
    
def select_wifi(kbd, lcd):
    """Presents a list of available wifi networks, allowing one to be selected and connected to."""
    from lcd_helper import beep
    lcd.set_custom_chars(*WIFI_CUSTOM_CHARS)

    # Load Wifi Network List
    lcd.write_text(b'Scanning...', 'center')
    cur = 0
    cells = get_wifi_cells()
    
    while True:
        # Update the LCD screen
        if len(cells) == 0:
            lcd.write_all(b'   No Wifis Found   ', b'F5 Reload ESC Cancel')
        else:
            lcd.write_all(get_wifi_cell_ssid(cells[cur], LCD_DIM[0]-1),
                          get_wifi_cell_info(cells[cur]))
            if cur != 0:            lcd.write_at((0, LCD_DIM[0]-1), UP)
            if cur != len(cells)-1: lcd.write_at((1, LCD_DIM[0]-1), DOWN)

        # Wait for a key to be typed
        ch = __unwrap(kbd.get())
        if ch == KEY_UP:
            if cur == 0: beep()
            else: cur -= 1
        elif ch == KEY_DOWN:
            if cur >= len(cells)-1: beep()
            else: cur += 1
        elif ch == KEY_F5:
            # Reload/Refresh
            lcd.write_text(b'Scanning...', 'center')
            cur = 0
            cells = get_wifi_cells()
        elif ch in HELP_KEYS: show_select_wifi_help(kbd, lcd)
        elif ch in QUIT_KEYS: break
        elif ch in ENTER_KEYS:
            if len(cells) != 0 and connect_wifi(kbd, lcd, cells[cur]): break
        else: beep()

class HasInternet(RuntimeError):
    pass
        
def kbd_setup(lcd, skip_if_have_internet=True):
    """
    Create a keyboard reading object. There may be no keyboard attached to the system so we
    may display a message and periodically check for one.
    """
    from kbd import KeyboardInputReader
    from time import sleep
    displayed = False
    while not (skip_if_have_internet and has_internet()):
        devs = KeyboardInputReader.devices()
        if len(devs) != 0: return KeyboardInputReader(devs[0])
        if not displayed:
            lcd.write_all(b'    No Internet', b'Plug in keyboard...')
            displayed = True
        sleep(1)
    raise HasInternet()

def run_select_wifi(lcd, skip_if_have_internet=True):
    """Acquire a keyboard and call select_wifi with it."""
    if has_internet(): return
    try:
        with kbd_setup(lcd, skip_if_have_internet) as kbd:
            select_wifi(kbd, lcd)
    except HasInternet: return

def local_ip():
    """Returns the local IP of the machine or None it not on the Internet"""
    import socket
    from contextlib import closing
    try:
        socket.setdefaulttimeout(1)
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
            s.connect(("8.8.8.8", 53))
            return s.getsockname()[0].encode('ascii')
    except Exception: return None

def external_ip():
    """Returns the external IP of the machine or None it not on the Internet"""
    import urllib2
    from contextlib import closing
    try:
        with closing(urllib2.urlopen('https://api.ipify.org')) as page:
            return page.read().encode('ascii')
    except Exception: return None

def has_internet():
    """Returns True if on the Internet"""
    return local_ip() is not None

if __name__ == "__main__":
    from lcd_helper import lcd_setup
    run_select_wifi(lcd_setup(1.0, 0.4))

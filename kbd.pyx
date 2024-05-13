from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

# requires: Cython, linux

from posix.unistd cimport read
from posix.time cimport timeval
from posix.ioctl cimport ioctl
from libc.errno cimport errno, EINTR, EIO, EMFILE, EAGAIN, EWOULDBLOCK
from libc.stdlib cimport memset

from select import POLLIN as PyPOLLIN
cdef int POLLIN = PyPOLLIN

cdef extern from "<linux/input.h>" nogil:
    # Information needed for reading data from the /dev/input/event# devices on Linux
    ctypedef unsigned short __u16
    ctypedef signed int __s32
    int EVIOCGKEY(int) nogil # macro for use with ioctl to get keymap
    int EVIOCGLED(int) nogil # macro for use with ioctl to get LEDs
    enum: LED_NUML, LED_CAPSL, LED_SCROLLL # LED bits for use with EVIOCGLED
    struct input_event: # the /dev/input/event# devices produce these when being read
        timeval time
        __u16 type
        __u16 code
        __s32 value
    enum: # the value of input_event.type
        EV_SYN, EV_KEY, EV_REL, EV_ABS, EV_MSC, EV_SW,
        EV_LED, EV_SND, EV_REP, EV_FF, EV_PWR
    enum: # the value of input_event.code
        KEY_MAX, # the maximum key value - needed for ioctl-EVIOCGKEY
        
        # These are not quite ordered numerically like they are in "input-event-codes.h"
        # Instead more organzied like US keyboard
        KEY_ESC,
        
        # Main section
        KEY_GRAVE, KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9, KEY_0, KEY_MINUS, KEY_EQUAL, KEY_BACKSPACE,
        KEY_TAB, KEY_Q, KEY_W, KEY_E, KEY_R, KEY_T, KEY_Y, KEY_U, KEY_I, KEY_O, KEY_P, KEY_LEFTBRACE, KEY_RIGHTBRACE, KEY_BACKSLASH,
        KEY_CAPSLOCK, KEY_A, KEY_S, KEY_D, KEY_F, KEY_G, KEY_H, KEY_J, KEY_K, KEY_L, KEY_SEMICOLON, KEY_APOSTROPHE, KEY_ENTER,
        KEY_LEFTSHIFT, KEY_Z, KEY_X, KEY_C, KEY_V, KEY_B, KEY_N, KEY_M, KEY_COMMA, KEY_DOT, KEY_SLASH, KEY_RIGHTSHIFT,
        KEY_LEFTCTRL, KEY_LEFTMETA, KEY_LEFTALT, KEY_SPACE, KEY_RIGHTALT, KEY_COMPOSE, KEY_RIGHTMETA, KEY_RIGHTCTRL,

        # Function keys
        KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5, KEY_F6, KEY_F7, KEY_F8, KEY_F9, KEY_F10, KEY_F11, KEY_F12,
        KEY_F13, KEY_F14, KEY_F15, KEY_F16, KEY_F17, KEY_F18, KEY_F19, KEY_F20, KEY_F21, KEY_F22, KEY_F23, KEY_F24,

        # Middle section
        KEY_SYSRQ, KEY_SCROLLLOCK, KEY_PAUSE, # SYSRQ is PRINT SCREEN
        KEY_INSERT, KEY_HOME, KEY_PAGEUP,
        KEY_DELETE, KEY_END, KEY_PAGEDOWN,
        KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN,
        
        # Numpad
        KEY_NUMLOCK, KEY_KPSLASH, KEY_KPASTERISK, KEY_KPMINUS, 
        KEY_KP7, KEY_KP8, KEY_KP9, KEY_KPPLUS, 
        KEY_KP4, KEY_KP5, KEY_KP6,
        KEY_KP1, KEY_KP2, KEY_KP3, KEY_KPENTER,
        KEY_KP0, KEY_KPDOT, KEY_CLEAR,
        
        # There are a ton of other ones as well... here are some of them
        KEY_HELP

# The possible values of input_event.value
DEF RELEASE    = 0
DEF PRESS      = 1
DEF AUTOREPEAT = 2

# Modifier flags for use by the class
DEF SHIFT     = 0x01
DEF CTRL      = 0x02
DEF ALT       = 0x04
DEF META      = 0x08 # e.g. Windows
DEF CAPS      = 0x10
DEF SCROLL    = 0x20
DEF NUM       = 0x40

cdef int EV_REQUIRED   = (1 << EV_SYN) | (1 << EV_KEY) | (1 << EV_LED) | (1 << EV_REP)
cdef int EV_DISALLOWED = (1 << EV_REL) | (1 << EV_ABS) | (1 << EV_SND) | (1 << EV_FF)

# Expose these constants to Python uses of module
ACTION_RELEASE    = RELEASE
ACTION_PRESS      = PRESS
ACTION_AUTOREPEAT = AUTOREPEAT

cdef dict keymap = {
    # key -> unshifted key, shifted key
    KEY_GRAVE : (b'`', b'~'),
    KEY_1 : (b'1', b'!'),
    KEY_2 : (b'2', b'@'),
    KEY_3 : (b'3', b'#'),
    KEY_4 : (b'4', b'$'),
    KEY_5 : (b'5', b'%'),
    KEY_6 : (b'6', b'^'),
    KEY_7 : (b'7', b'&'),
    KEY_8 : (b'8', b'*'),
    KEY_9 : (b'9', b'('),
    KEY_0 : (b'0', b')'),
    KEY_MINUS : (b'-', b'_'),
    KEY_EQUAL : (b'=', b'+'),

    KEY_TAB : (b'\t', None),
    KEY_Q : (b'q', b'Q'),
    KEY_W : (b'w', b'W'),
    KEY_E : (b'e', b'E'),
    KEY_R : (b'r', b'R'),
    KEY_T : (b't', b'T'),
    KEY_Y : (b'y', b'Y'),
    KEY_U : (b'u', b'U'),
    KEY_I : (b'i', b'I'),
    KEY_O : (b'o', b'O'),
    KEY_P : (b'p', b'P'),
    KEY_LEFTBRACE : (b'[', b'{'),
    KEY_RIGHTBRACE : (b']', b'}'),
    KEY_BACKSLASH : (b'\\', b'|'),

    KEY_A : (b'a', b'A'),
    KEY_S : (b's', b'S'),
    KEY_D : (b'd', b'D'),
    KEY_F : (b'f', b'F'),
    KEY_G : (b'g', b'G'),
    KEY_H : (b'h', b'H'),
    KEY_J : (b'j', b'J'),
    KEY_K : (b'k', b'K'),
    KEY_L : (b'l', b'L'),
    KEY_SEMICOLON : (b';', b':'),
    KEY_APOSTROPHE : (b'\'', b'"'),
    KEY_ENTER : (b'\n', None),

    KEY_Z : (b'z', b'Z'),
    KEY_X : (b'x', b'X'),
    KEY_C : (b'c', b'C'),
    KEY_V : (b'v', b'V'),
    KEY_B : (b'b', b'B'),
    KEY_N : (b'n', b'N'),
    KEY_M : (b'm', b'M'),
    KEY_COMMA : (b',', b'<'),
    KEY_DOT : (b'.', b'>'),
    KEY_SLASH : (b'/', b'?'),

    KEY_SPACE : (b' ', None),
    
    # Numpad keys that don't change with numlock
    KEY_KPSLASH: ('/', None),
    KEY_KPASTERISK: ('*', None),
    KEY_KPMINUS: ('-', None),
    KEY_KPPLUS: ('+', None), 
    KEY_KPENTER: ('\n', None),
}

cdef dict numpad = {
    # key -> key is unlock, key if locked
    KEY_KP7 : (KEY_HOME, KEY_7),
    KEY_KP8 : (KEY_UP, KEY_8),
    KEY_KP9 : (KEY_PAGEUP, KEY_9),
    KEY_KP4 : (KEY_LEFT, KEY_4),
    KEY_KP5 : (KEY_CLEAR, KEY_5),
    KEY_KP6 : (KEY_RIGHT, KEY_6),
    KEY_KP1 : (KEY_END, KEY_1),
    KEY_KP2 : (KEY_DOWN, KEY_2),
    KEY_KP3 : (KEY_PAGEDOWN, KEY_3),
    KEY_KP0 : (KEY_INSERT, KEY_0),
    KEY_KPDOT : (KEY_DELETE, KEY_DOT),
}

cdef frozenset modifier_keys = {
    # set of keys that are modifiers that are not returned by the get() function
    KEY_LEFTSHIFT, KEY_RIGHTSHIFT, KEY_LEFTCTRL, KEY_RIGHTCTRL,
    KEY_LEFTALT, KEY_RIGHTALT, KEY_LEFTMETA, KEY_RIGHTMETA,
    KEY_CAPSLOCK, KEY_SCROLLLOCK, KEY_NUMLOCK,
}

cdef inline char __get_modifiers(int fd) nogil:
    """Gets the current modifiers pressed and the lock keys that are on for the given keyboard."""
    cdef char keys[KEY_MAX//8 + 1]
    memset(keys, 0, sizeof(keys))
	cdef char leds = 0
    if (ioctl(fd, EVIOCGKEY(sizeof(keys)),  keys) == -1 or
        ioctl(fd, EVIOCGLED(sizeof(leds)), &leds) == -1): __OSError(errno)
    return (
        (SHIFT if __has_key(keys, KEY_LEFTSHIFT) or __has_key(keys, KEY_RIGHTSHIFT) else 0) |
        (CTRL  if __has_key(keys, KEY_LEFTCTRL ) or __has_key(keys, KEY_RIGHTCTRL ) else 0) |
        (ALT   if __has_key(keys, KEY_LEFTALT  ) or __has_key(keys, KEY_RIGHTALT  ) else 0) |
        (META  if __has_key(keys, KEY_LEFTMETA ) or __has_key(keys, KEY_RIGHTMETA ) else 0) |
        (CAPS   if (leds & (1 << LED_CAPSL  )) != 0 else 0) |
        (SCROLL if (leds & (1 << LED_SCROLLL)) != 0 else 0) |
        (NUM    if (leds & (1 << LED_NUML   )) != 0 else 0))

cdef inline bint __has_key(const char* keymap, int key) nogil:
    """Checks if a key is pressed in the given keymap"""
    return (keymap[key//8] & (1 << (key%8))) != 0

cdef inline __OSError(int errno, filename=None):
    """Create an OSError for the given errno and possibly filename, does not raise it"""
    from os import strerror
    msg = strerror(errno)
    return OSError(errno, msg, filename) if filename else OSError(errno, msg)

cdef inline possibly_add_device(list handlers, int ev, list devices):
    """
    If the ev and handlers match up with being a keyboard the device path will be added to the
    device list.
    """
    if ev & EV_REQUIRED == EV_REQUIRED and ev & EV_DISALLOWED == 0:
        evnt = next((h for h in handlers if h.startswith('event') and h[5:].isdigit()), None)
        if evnt is not None:
            devices.append('/dev/input/'+evnt)
    
cdef class KeyboardInputReader:
    """
    Reads keyboard events from an input device on Linux. Normal use has this performming some
    processing to handle things like shift keys and caps lock. This supports the context manager
    protocol.
    """
    
    @staticmethod
    def devices():
        """
        Static method for finding keyboard devices on the system, returning a list of devices like
        /dev/input/event#. This may easily return no items if there are no keyboards.
        """
        cdef list devices = []
        cdef list handlers = []
        cdef int ev = 0
        
        # Get all the possible devices
        with open('/proc/bus/input/devices', 'r') as f:
            for line in f:
                line = line.strip()
                if line == '':
                    # separator between devices
                    possibly_add_device(handlers, ev, devices)
                    handlers = []
                    ev = 0
                else:
                    # information about the current device
                    name,value = (x.strip() for x in line.split('=', 1))
                    if name == 'H: Handlers':
                        if len(handlers) != 0: raise OSError('misformed device data')
                        handlers = value.split()
                    elif name == 'B: EV':
                        if ev != 0: raise OSError('misformed device data')
                        ev = int(value, 16)
        possibly_add_device(handlers, ev, devices)
        return devices

    cdef dict fds

    def __cinit__(self, *args, **kargs):
        from threading import Lock
        from select import poll
        self.fds = {}
        self.lock = Lock()
        self.poll = poll()

    def __init__(self, *devs):
        """
        Create a new reader for the given device(s) that should be string(s) like
        '/dev/input/event0'. To search for possible devices see the 'devices()' static method.
        """
        from os import open, O_RDONLY, O_NONBLOCK
        with self.lock:
            try:
                for dev in devs:
                    if dev in self.fds: continue
                    fd = open(dev, O_RDONLY|O_NONBLOCK)
                    self.fds[dev] = fd
                    self.poll.register(fd, PyPOLLIN)
            except: self.close()

    cdef input_event __get(self, int* _fd):
        """
        Get the next key from any device that is being monitored and return it. The only processing
        this does it to make sure it is a keyboard event. All over events are skipped. OSErrors are
        raised on errors. The input_event is returned and the _fd paramater is filled in.
        """
        # we use C read function directly for advanced usage
        cdef input_event ev
        cdef ssize_t n
        cdef int fd, evnt
        while len(self.fds) != 0:
            # Find an input device to read from
            # TODO: needs to be notified if self.poll has a new FD registered in another thread
            # closing/removing a FD is already handled since it will cause a POLLHUP or POLLNVAL event
            # Note that this DOES support interrupts but it doesn't update the internal 'UFD' data, but possibly if I raise/catch an exception from the signal handler than I could catch it here and do my own reset
            # Will also need to get a lock for the poller, save the current thread it (however Python may no allow this?)
            ready = self.poll.poll()
            # Cycle through all devices to find the one(s) that are ready to read from
            with self.lock:
                for fd,evnt in ready:
                    if evnt&POLLIN: # others may be POLLHUP, POLLERR, POLLNVAL which all indicate errors or closed file descriptors so we shouldn't read from those
                        # Found a device to read from
                        while True:
                            n = read(fd, &ev, sizeof(ev))
                            if n == -1:
                                if errno == EINTR: continue # retry if signal interrupts operation
                                if errno == EAGAIN or errno == EWOULDBLOCK: break # not ready any more
                                raise __OSError(errno) # another error we aren't prepared to handle
                            elif n != sizeof(ev): raise __OSError(EIO) # not enough data read, bad I/O
                            elif ev.type != EV_KEY or ev.value < 0 or ev.value > 2: continue # not the right type, try another device or waiting again
                            # Right type - good to go!
                            _fd[0] = fd
                            return ev
        raise LookupError("no keyboards to read from") # TODO: something else instead? option to always block?

    def get_raw(self):
        """
        Gets the next raw event. Returns a tuple of fd (file descriptor integer), time (as a
        double in seconds), the action of event (one of ACTION_* constants), and the integer for
        the keyboard key which was pressed.
        """
        cdef int fd
        cdef input_event ev = self.__get(&fd)
        return (fd, ev.time.tv_sec + ev.time.tv_usec / 1000000, int(ev.value), int(ev.code))

    def get(self):
        """
        Get the next key press from the keyboard, blocking if necessary. This automatically
        handles the Shift, CTRL, ALT, Meta/Windows, Caps Lock, Scroll Lock, and Num Lock and auto
        repeats.
        
        If the keyboard key (along with any modifies/locks) is a simple ASCII character then this
        returns a 1-character byte string. The following are returned this way:
            \t \n <space> !"#$%&'()*+,-./ 0-9 :;<=>?@ A-Z [\]^_` a-z {|}~

        All other keys return a tuple like (code, modifiers). This value can be looked up against
        the set of KEY_* values in this module. The modifiers are a bitmask of values from MOD_*
        and *_LOCK values in this module. This will include codes that normally return a
        byte-string but due to a modifier are not printable (e.g. meta+R or shift+Enter).
        """
        # TODO: does this need to acquire the lock?
        
        # Get the next usable input event
        cdef int fd
        cdef input_event ev
        while True:
            ev = self.__get(&fd)
            if ev.code not in modifier_keys and ev.value != RELEASE: break

        # Get the current modifiers and lock keys of the keyboard
        cdef int mods = __get_modifiers(fd), code = ev.code
        
        # Translate numpad keys to their respective keys
        if code in numpad: code = numpad[code][1 if (mods & NUM) else 0]
        
        # If CTRL, ALT, or Meta is down then always return a tuple
        # If we do not have a mapping for the key return a tuple
        if mods & (CTRL | ALT | META) or code not in keymap: return (code, mods)

        # Get the characters for unshifted and shifted versions and return the right one
        u,s = keymap[code]
        if mods & SHIFT and s is None: return (code, mods) # no shifted character version
        if mods & CAPS and b'a' <= u <= b'z': return u if mods & SHIFT else s # CAPS reverses SHIFT logic for letters
        return s if mods & SHIFT else u

    def add(dev):
        """Add a device to the devices being monitored."""
        from os import open, O_RDONLY, O_NONBLOCK
        with self.lock:
            if dev in self.fds: return
            fd = open(dev, O_RDONLY|O_NONBLOCK)
            self.fds[dev] = fd
            self.poll.register(fd, PyPOLLIN)
            
    def remove(dev):
        """Remove a device to the devices being monitored."""
        from os import close
        with self.lock:
            fd = self.fds[dev]
            self.poll.unregister(fd)
            close(fd)
            del self.fds[dev]

    cpdef close(self):
        """
        Close all currently open devices. This leaves the object in a reusable state and devices
        can be re-added.
        """
        from os import close
        from select import poll
        with self.lock:
            self.poll = poll()
            for fd in self.fds.itervalues():
                try: close(fd)
                except: pass
            self.fds.clear()
    def __dealloc__(self): self.close()
    def __enter__(self): return self
    def __exit__(self, type, value, tb): self.close()

# The remainder is just mapping the key values to modules attributes that can be used in Python
# Generated from the extern definitions about with the regex:
#     s/(KEY_[A-Z0-9]+),\s*/m.\1 = \1\n/g
import sys
m = sys.modules[__name__]
m.KEY_ESC = KEY_ESC
m.KEY_GRAVE = KEY_GRAVE
m.KEY_1 = KEY_1
m.KEY_2 = KEY_2
m.KEY_3 = KEY_3
m.KEY_4 = KEY_4
m.KEY_5 = KEY_5
m.KEY_6 = KEY_6
m.KEY_7 = KEY_7
m.KEY_8 = KEY_8
m.KEY_9 = KEY_9
m.KEY_0 = KEY_0
m.KEY_MINUS = KEY_MINUS
m.KEY_EQUAL = KEY_EQUAL
m.KEY_BACKSPACE = KEY_BACKSPACE
m.KEY_TAB = KEY_TAB
m.KEY_Q = KEY_Q
m.KEY_W = KEY_W
m.KEY_E = KEY_E
m.KEY_R = KEY_R
m.KEY_T = KEY_T
m.KEY_Y = KEY_Y
m.KEY_U = KEY_U
m.KEY_I = KEY_I
m.KEY_O = KEY_O
m.KEY_P = KEY_P
m.KEY_LEFTBRACE = KEY_LEFTBRACE
m.KEY_RIGHTBRACE = KEY_RIGHTBRACE
m.KEY_BACKSLASH = KEY_BACKSLASH
m.KEY_CAPSLOCK = KEY_CAPSLOCK
m.KEY_A = KEY_A
m.KEY_S = KEY_S
m.KEY_D = KEY_D
m.KEY_F = KEY_F
m.KEY_G = KEY_G
m.KEY_H = KEY_H
m.KEY_J = KEY_J
m.KEY_K = KEY_K
m.KEY_L = KEY_L
m.KEY_SEMICOLON = KEY_SEMICOLON
m.KEY_APOSTROPHE = KEY_APOSTROPHE
m.KEY_ENTER = KEY_ENTER
m.KEY_LEFTSHIFT = KEY_LEFTSHIFT
m.KEY_Z = KEY_Z
m.KEY_X = KEY_X
m.KEY_C = KEY_C
m.KEY_V = KEY_V
m.KEY_B = KEY_B
m.KEY_N = KEY_N
m.KEY_M = KEY_M
m.KEY_COMMA = KEY_COMMA
m.KEY_DOT = KEY_DOT
m.KEY_SLASH = KEY_SLASH
m.KEY_RIGHTSHIFT = KEY_RIGHTSHIFT
m.KEY_LEFTCTRL = KEY_LEFTCTRL
m.KEY_LEFTMETA = KEY_LEFTMETA
m.KEY_LEFTALT = KEY_LEFTALT
m.KEY_SPACE = KEY_SPACE
m.KEY_RIGHTALT = KEY_RIGHTALT
m.KEY_COMPOSE = KEY_COMPOSE
m.KEY_RIGHTMETA = KEY_RIGHTMETA
m.KEY_RIGHTCTRL = KEY_RIGHTCTRL
m.KEY_F1 = KEY_F1
m.KEY_F2 = KEY_F2
m.KEY_F3 = KEY_F3
m.KEY_F4 = KEY_F4
m.KEY_F5 = KEY_F5
m.KEY_F6 = KEY_F6
m.KEY_F7 = KEY_F7
m.KEY_F8 = KEY_F8
m.KEY_F9 = KEY_F9
m.KEY_F10 = KEY_F10
m.KEY_F11 = KEY_F11
m.KEY_F12 = KEY_F12
m.KEY_F13 = KEY_F13
m.KEY_F14 = KEY_F14
m.KEY_F15 = KEY_F15
m.KEY_F16 = KEY_F16
m.KEY_F17 = KEY_F17
m.KEY_F18 = KEY_F18
m.KEY_F19 = KEY_F19
m.KEY_F20 = KEY_F20
m.KEY_F21 = KEY_F21
m.KEY_F22 = KEY_F22
m.KEY_F23 = KEY_F23
m.KEY_F24 = KEY_F24
m.KEY_SYSRQ = KEY_SYSRQ
m.KEY_SCROLLLOCK = KEY_SCROLLLOCK
m.KEY_PAUSE = KEY_PAUSE
m.KEY_INSERT = KEY_INSERT
m.KEY_HOME = KEY_HOME
m.KEY_PAGEUP = KEY_PAGEUP
m.KEY_DELETE = KEY_DELETE
m.KEY_END = KEY_END
m.KEY_PAGEDOWN = KEY_PAGEDOWN
m.KEY_UP = KEY_UP
m.KEY_LEFT = KEY_LEFT
m.KEY_RIGHT = KEY_RIGHT
m.KEY_DOWN = KEY_DOWN
m.KEY_NUMLOCK = KEY_NUMLOCK
m.KEY_KPSLASH = KEY_KPSLASH
m.KEY_KPASTERISK = KEY_KPASTERISK
m.KEY_KPMINUS = KEY_KPMINUS
m.KEY_KP7 = KEY_KP7
m.KEY_KP8 = KEY_KP8
m.KEY_KP9 = KEY_KP9
m.KEY_KPPLUS = KEY_KPPLUS
m.KEY_KP4 = KEY_KP4
m.KEY_KP5 = KEY_KP5
m.KEY_KP6 = KEY_KP6
m.KEY_KP1 = KEY_KP1
m.KEY_KP2 = KEY_KP2
m.KEY_KP3 = KEY_KP3
m.KEY_KPENTER = KEY_KPENTER
m.KEY_KP0 = KEY_KP0
m.KEY_KPDOT = KEY_KPDOT
m.KEY_CLEAR = KEY_CLEAR
m.KEY_HELP = KEY_HELP
del m, sys

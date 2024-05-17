#cython: language_level=3

from cpython.bytes cimport PyBytes_FromStringAndSize
from . cimport wiringpi as wp


# Wiring-PI Wrapper Functions
# The official Wiring-PI python library is abandoned and mixing it with a separate wiring pi library
# causes issues.
INPUT = wp.INPUT
OUTPUT = wp.OUTPUT
PWM_OUTPUT = wp.PWM_OUTPUT
def wiringPiSetup(): return wp.wiringPiSetup()
def wiringPiSetupGpio(): return wp.wiringPiSetupGpio()
def wiringPiSetupPhys(): return wp.wiringPiSetupPhys()
def wiringPiSetupSys(): return wp.wiringPiSetupSys()
def pinMode(int pin, int mode): wp.pinMode(pin, mode)
def digitalWrite(int pin, int value): wp.digitalWrite(pin, value)
def pwmWrite(int pin, int value): wp.pwmWrite(pin, value)
def digitalRead(int pin): return wp.digitalRead(pin)
def millis(): return wp.millis()
def micros(): return wp.micros()
def delay(unsigned int howLong): wp.delay(howLong)
def delayMicroseconds(unsigned int howLong): wp.delayMicroseconds(howLong)


# Simple utility that should be in C code to be accurate and uses the above Wiring-PI definitions
def beep(int pin, double freq=1000, double dur=0.1):
    """
    Generate a square wave on the given pin of the approximate frequency (in Hz) and duration in
    seconds. If a simple beeper is attached it will make a beep. It is likely the actual frequency
    will be slightly lower than the given value.
    """
    cdef unsigned int delay, niter, i
    with nogil:
        wp.pinMode(pin, wp.OUTPUT)    
        delay = <unsigned int>(1000000 // (2 * freq)) # Hz -> microseconds (halfed)
        niter = <unsigned int>(2*dur*freq + 0.5)
        for i in range(niter):
            wp.digitalWrite(pin, i & 1)
            wp.delayMicroseconds(delay)
        wp.digitalWrite(pin, 0)
    
cdef int[4] LCD_row_offs = [ 0x00, 0x40, 0x14, 0x54 ]

cdef class LCD:
    cdef int RS, RW, EN
    cdef int[8] DB
    cdef int bits
    cdef int nc, nr
    cdef bint inc, shft, on, cur, blnk
    
    def __init__(self, int RS, int RW, int EN, DB, dims):
        """
        Connect to the LCD using the pins RS, RW, EN, and 4 or 8 pins as DB and a width and height
        in dims (e.g. (20,2)). The LCD is started, cleared, and set to no shift, blink, or show the
        cursor. The pin numbers must be given to be compatible with whatever wiringPi setup
        function was called previously.
        """
        self.RS = RS; self.RW = RW; self.EN = EN
        self.inc = True; self.shft = False; self.on = True; self.cur = False; self.blnk = False
        self.nc, self.nr = dims
        if (self.nr <= 0 or self.nr > 4 or
            self.nc <= 0 or self.nc*self.nr > 80): raise ValueError("Invalid dimensions")
        cdef int bits = len(DB)
        self.bits = bits
        if bits != 4 and bits != 8: raise ValueError("Number of data pins must be 4 or 8")
        self.DB[0] = DB[0]; self.DB[1] = DB[1]; self.DB[2] = DB[2]; self.DB[3] = DB[3]
        if bits == 8:
            self.DB[4] = DB[4]; self.DB[5] = DB[5]; self.DB[6] = DB[6]; self.DB[7] = DB[7]

        
        # We don't need the GIL from here to the end and there is a lot of waiting
        # Function Set Command - 001(DL)NF00
        cdef int por = 40 - wp.millis()
        with nogil:
            
            # All pins start as outputs and low
            wp.digitalWrite(EN, 0); wp.pinMode(EN, wp.OUTPUT)
            wp.digitalWrite(RS, 0); wp.pinMode(RS, wp.OUTPUT)
            wp.pinMode(RW, wp.OUTPUT)

            if bits == 4:
                self._read = self.read4; self._read_data = self.readData4
                self._write = self.write4; self._write_data = self.writeData4

                # Need to wait 40 ms since the LCD received power
                self.writing4()
                self.set4(0)
                if por > 0: wp.delay(por)
                self.set4(0x3); self.clock(); wp.delayMicroseconds(4100)
                self.set4(0x3); self.clock(); wp.delayMicroseconds(100)
                self.set4(0x3); self.clock(); wp.delayMicroseconds(100)
                self.set4(0x2); self.clock()

                # Set default state to reading and send "Function Set Command"
                self.reading4()
                self.write4(0x20 | (0x08 if self.nr != 1 else 0))

                # Setup display
                self.write4(0x08) # Display off
                self.write4(0x01) # Clear display
                self.write4(0x06) # Set entry mode: increment and no shift
                self.write4(0x80) # Set DDRAM address to 0
                self.write4(0x0C) # Display on

            else:
                self._read = self.read8; self._read_data = self.readData8
                self._write = self.write8; self._write_data = self.writeData8

                # Need to wait 40 ms since the LCD recieved power
                self.writing8()
                self.set8(0)
                if por > 0: wp.delay(por)
                self.set8(0x30); self.clock(); wp.delayMicroseconds(4100)
                self.set8(0x30); self.clock(); wp.delayMicroseconds(100)
                self.set8(0x30); self.clock()

                # Set default state to reading and send "Function Set Command"
                self.reading8()
                self.write8(0x30 | (0x08 if self.nr != 1 else 0))

                # Setup display
                self.write8(0x08) # Display off
                self.write8(0x01) # Clear display
                self.write8(0x06) # Set entry mode: increment and no shift
                self.write8(0x80) # Set DDRAM address to 0
                self.write8(0x0C) # Display on

    @property
    def dims(self): return (self.nc, self.nr)

    ########## CORE INTERFACE ##########
    # These are written different for the 4 and 8 bit interfaces and are properly mapped
    # in the __init__ function.
    cdef int (*_read)(LCD) noexcept nogil
    cdef int (*_read_data)(LCD) noexcept nogil
    cdef void (*_write)(LCD, unsigned char x) noexcept nogil
    cdef void (*_write_data)(LCD, unsigned char x) noexcept nogil

    cdef inline void clock(self) noexcept nogil:
        """Clocks a command in (EN pin high then low)"""
        wp.digitalWrite(self.EN, 1); wp.delayMicroseconds(1); wp.digitalWrite(self.EN, 0)
    cdef inline void set8(self, unsigned char x) noexcept nogil:
        """Sets 8 bits to the DB pins"""
        wp.digitalWrite(self.DB[7], x&0x80)
        wp.digitalWrite(self.DB[6], x&0x40)
        wp.digitalWrite(self.DB[5], x&0x20)
        wp.digitalWrite(self.DB[4], x&0x10)
        wp.digitalWrite(self.DB[3], x&0x08)
        wp.digitalWrite(self.DB[2], x&0x04)
        wp.digitalWrite(self.DB[1], x&0x02)
        wp.digitalWrite(self.DB[0], x&0x01)
    cdef inline void set4(self, unsigned char x) noexcept nogil:
        """Sets 4 bits to the DB pins"""
        wp.digitalWrite(self.DB[3], x&0x08)
        wp.digitalWrite(self.DB[2], x&0x04)
        wp.digitalWrite(self.DB[1], x&0x02)
        wp.digitalWrite(self.DB[0], x&0x01)

        
    cdef inline void writing8(self) noexcept nogil:
        """Set the interface into writing mode (RW=0 and all DBs as outputs) (8-bit interface)"""
        wp.digitalWrite(self.RW, 0)
        wp.pinMode(self.DB[0], wp.OUTPUT); wp.pinMode(self.DB[1], wp.OUTPUT)
        wp.pinMode(self.DB[2], wp.OUTPUT); wp.pinMode(self.DB[3], wp.OUTPUT)
        wp.pinMode(self.DB[4], wp.OUTPUT); wp.pinMode(self.DB[5], wp.OUTPUT)
        wp.pinMode(self.DB[6], wp.OUTPUT); wp.pinMode(self.DB[7], wp.OUTPUT)
    cdef inline void writing4(self) noexcept nogil:
        """Set the interface into writing mode (RW=0 and all DBs as outputs) (4-bit interface)"""
        wp.digitalWrite(self.RW, 0)
        wp.pinMode(self.DB[0], wp.OUTPUT); wp.pinMode(self.DB[1], wp.OUTPUT)
        wp.pinMode(self.DB[2], wp.OUTPUT); wp.pinMode(self.DB[3], wp.OUTPUT)

    cdef inline void reading8(self) noexcept nogil:
        """Set the interface into reading mode (RW=1 and all DBs as inputs) (8-bit interface)"""
        wp.digitalWrite(self.RW, 1)
        wp.pinMode(self.DB[0], wp.INPUT); wp.pinMode(self.DB[1], wp.INPUT)
        wp.pinMode(self.DB[2], wp.INPUT); wp.pinMode(self.DB[3], wp.INPUT)
        wp.pinMode(self.DB[4], wp.INPUT); wp.pinMode(self.DB[5], wp.INPUT)
        wp.pinMode(self.DB[6], wp.INPUT); wp.pinMode(self.DB[7], wp.INPUT)
    cdef inline void reading4(self) noexcept nogil:
        """Set the interface into reading mode (RW=1 and all DBs as inputs) (4-bit interface)"""
        wp.digitalWrite(self.RW, 1)
        wp.pinMode(self.DB[0], wp.INPUT); wp.pinMode(self.DB[1], wp.INPUT)
        wp.pinMode(self.DB[2], wp.INPUT); wp.pinMode(self.DB[3], wp.INPUT)
        
    cdef inline bint busy8(self) noexcept nogil:
        """Checks if the LCD is busy or not (8-bit interface)"""
        # RS, RW = 0, 1
        wp.digitalWrite(self.EN, 1)
        wp.delayMicroseconds(1)
        cdef bint busy = wp.digitalRead(self.DB[7])
        wp.digitalWrite(self.EN, 0)
        return busy
    cdef inline bint busy4(self) noexcept nogil:
        """Checks if the LCD is busy or not (4-bit interface)"""
        # RS, RW = 0, 1
        wp.digitalWrite(self.EN, 1)
        wp.delayMicroseconds(1)
        cdef bint busy = wp.digitalRead(self.DB[3])
        wp.digitalWrite(self.EN, 0)
        wp.digitalWrite(self.EN, 1)
        wp.digitalWrite(self.EN, 0)
        return busy
    @property
    def busy(self): return self.busy8() if self.bits == 8 else self.busy4()
    
    cdef inline void wait8(self) noexcept nogil:
        """Waits for the LCD to not be busy (8-bit interface)"""
        # RS, RW = 0, 1
        cdef int EN = self.EN, DB = self.DB[7]
        cdef bint busy = True
        while busy:
            wp.delayMicroseconds(1); wp.digitalWrite(EN, 1)
            wp.delayMicroseconds(1); busy = wp.digitalRead(DB); wp.digitalWrite(EN, 0)
    cdef inline void wait4(self) noexcept nogil:
        """Waits for the LCD to not be busy (4-bit interface)"""
        # RS, RW = 0, 1
        cdef int EN = self.EN, DB = self.DB[3]
        cdef bint busy = True
        while busy:
            wp.delayMicroseconds(1); wp.digitalWrite(EN, 1)
            wp.delayMicroseconds(1); busy = wp.digitalRead(DB); wp.digitalWrite(EN, 0)
            wp.delayMicroseconds(1); wp.digitalWrite(EN, 1)
            wp.delayMicroseconds(1); wp.digitalWrite(EN, 0)

    cdef inline int __read8(self) noexcept nogil:
        """Read a single byte from the LCD, which must not be busy and RS set properly (8-bit interface)"""
        # RW = 1
        wp.delayMicroseconds(1); wp.digitalWrite(self.EN, 1); wp.delayMicroseconds(1)
        cdef int out = (
            wp.digitalRead(self.DB[7]) << 7 | wp.digitalRead(self.DB[6]) << 6 |
            wp.digitalRead(self.DB[5]) << 5 | wp.digitalRead(self.DB[4]) << 4 |
            wp.digitalRead(self.DB[3]) << 3 | wp.digitalRead(self.DB[2]) << 2 |
            wp.digitalRead(self.DB[1]) << 1 | wp.digitalRead(self.DB[0]) << 0)
        wp.digitalWrite(self.EN, 0)
        return out
    cdef inline int __read4(self) noexcept nogil:
        """Read a single byte from the LCD, which must not be busy and RS set properly (4-bit interface)"""
        # RW = 1
        wp.delayMicroseconds(1); wp.digitalWrite(self.EN, 1); wp.delayMicroseconds(1)
        cdef int out = (
            wp.digitalRead(self.DB[3]) << 7 | wp.digitalRead(self.DB[2]) << 6 |
            wp.digitalRead(self.DB[1]) << 5 | wp.digitalRead(self.DB[0]) << 4)
        wp.digitalWrite(self.EN, 0)
        wp.delayMicroseconds(1); wp.digitalWrite(self.EN, 1); wp.delayMicroseconds(1)
        out |= (wp.digitalRead(self.DB[3]) << 3 | wp.digitalRead(self.DB[2]) << 2 |
                wp.digitalRead(self.DB[1]) << 1 | wp.digitalRead(self.DB[0]) << 0)
        wp.digitalWrite(self.EN, 0)
        return out
    cdef int read8(self) noexcept nogil:
        """Read a single byte from the LCD, the character address (8-bit interface)"""
        # RW = 1
        self.wait8()
        return self.__read8()
    cdef int read4(self) noexcept nogil:
        """Read a single byte from the LCD, the character address (4-bit interface)"""
        # RW = 1
        self.wait4()
        return self.__read4()
    cdef int readData8(self) noexcept nogil:
        """Read a single byte from the LCD, the data (8-bit interface)"""
        # RW = 1
        self.wait8()
        wp.digitalWrite(self.RS, 1)
        cdef int x = self.__read8()
        wp.digitalWrite(self.RS, 0)
        return x
    cdef int readData4(self) noexcept nogil:
        """Read a single byte from the LCD, the data (4-bit interface)"""
        # RW = 1
        self.wait4()
        wp.digitalWrite(self.RS, 1)
        cdef int x = self.__read4()
        wp.digitalWrite(self.RS, 0)
        return x

    cdef inline void __write8(self, unsigned char x) noexcept nogil:
        """Writes a single byte to the LCD, which must not be busy and RS set properly (8-bit interface)"""
        self.writing8()
        self.set8(x)
        self.clock()
        self.reading8()

    cdef inline void __write4(self, unsigned char x) noexcept nogil:
        """Writes a single byte to the LCD, which must not be busy and RS set properly (4-bit interface)"""
        self.writing4()
        self.set4(x >> 4)
        self.clock()
        self.set4(x)
        self.clock()
        self.reading4()
        
    cdef void write8(self, unsigned char x) noexcept nogil:
        """Writes a single byte to the LCD either as a command (8-bit interface)"""
        #assert(0 <= x <= 0xFF)
        self.wait8()
        self.__write8(x)
    cdef void write4(self, unsigned char x) noexcept nogil:
        """Writes a single byte to the LCD either as a command (default) or data (4-bit interface)"""
        #assert(0 <= x <= 0xFF)
        self.wait4()
        self.__write4(x)
        
    cdef void writeData8(self, unsigned char x) noexcept nogil:
        """Writes a single byte to the LCD either as data (8-bit interface)"""
        #assert(0 <= x <= 0xFF)
        self.wait8()
        wp.digitalWrite(self.RS, 1)
        self.__write8(x)
        wp.digitalWrite(self.RS, 0)
    cdef void writeData4(self, unsigned char x) noexcept nogil:
        """Writes a single byte to the LCD either as data (4-bit interface)"""
        #assert(0 <= x <= 0xFF)
        self.wait4()
        wp.digitalWrite(self.RS, 1)
        self.__write4(x)
        wp.digitalWrite(self.RS, 0)

    ########## COMMANDS ##########
    def clear(self):
        """
        Sets all display data to spaces, sets the display address to 0, resets the shift to the
        initial position, and sets the increment to True.
        """
        self._write(self, 0x01)
        self.inc = True
    def return_home(self):
        """Sets the display address to 0 and resets the shift to the initial position."""
        self._write(self, 0x02)
    
    # Entry mode - 000001(I/D)S
    @property
    def increment(self): return self.inc
    @increment.setter
    def increment(self, bint value):
        value = 1 if value else 0
        if self.inc != value:
            self._write(self, 0x04 | (value << 1) | self.shft)
            self.inc = value
    @property
    def shift(self): return self.shift
    @shift.setter
    def shift(self, bint value):
        value = 1 if value else 0
        if self.shft != value:
            self._write(self, 0x04 | (self.inc << 1) | value)
            self.shft = value

    # Display Mode - 00001DCB
    @property
    def on(self): return self.on
    @on.setter
    def on(self, bint value):
        value = 1 if value else 0
        if self.on != value:
            self._write(self, 0x08 | (value << 2) | (self.cur << 1) | self.blnk)
            self.on = value
    @property
    def cursor(self): return self.cur
    @cursor.setter
    def cursor(self, bint value):
        value = 1 if value else 0
        if self.cur != value:
            self._write(self, 0x08 | (self.on << 2) | (value << 1) | self.blnk)
            self.cur = value
    @property
    def blink(self): return self.blnk
    @blink.setter
    def blink(self, bint value):
        value = 1 if value else 0
        if self.blnk != value:
            self._write(self, 0x08 | (self.on << 2) | (self.cur << 1) | value)
            self.blnk = value
    
    # Cursor or Display Shift - 0001(S/C)(R/L)xx
    def left(self):
        """Moves the cursor to the left as if a character was written to the display."""
        self._write(self, 0x10)
    def right(self):
        """Moves the cursor to the right."""
        self._write(self, 0x14)
    def shift_left(self):
        """Shifts the entire display to the left along with shifting the cursor."""
        self._write(self, 0x18)
    def shift_right(self):
        """Shifts the entire display to the right along with shifting the cursor."""
        self._write(self, 0x1C)
    
    # Get/Set the DDRAM/CGRAM Address
    cdef void set_cgram_addr(self, int x) noexcept nogil:
        """Sets the raw CGRAM address"""
        #assert(0 <= x < 0x40)
        self._write(self, 0x40 | x)
    cdef void set_ddram_addr(self, int x) noexcept nogil:
        """Sets the raw DDRAM address"""
        #assert(0 <= x < 0x80)
        self._write(self, 0x80 | x)
    cdef int get_addr(self) noexcept nogil:
        """
        Gets the current raw address, unknown if it is CGRAM or DDRAM though. However we keep this
        at DDRAM unless actively working with the character data.
        """
        return self._read(self) & 0x7F
    @property
    def position(self):
        """Gets/sets the current position on the screen in row,col coordinates."""
        cdef int ac = self.get_addr()
        if self.nr == 1: return (ac, 0)
        if self.nr == 2: return (ac & 0x3F, 0 if ac < 0x40 else 1)
        if ac < 0x14: return (ac, 0)
        if ac < 0x40: return (ac-0x14, 2)
        return (ac&0x3F, 1) if ac < 0x54 else (ac-0x54, 3)
    @position.setter
    def position(self, value):
        cdef int r,c
        r,c = value
        if r < 0 or r >= self.nr or c < 0 or c >= self.nc: raise ValueError('Invalid position')
        self.set_ddram_addr(c + LCD_row_offs[r])
        
    ##### SAVE / RESTORE STATE #####
    @property
    def state(self):
        """
        The acquires or restores the current entire state of the LCD screen. Retrieving and
        settings the state is an expensive operation. The state object returned should not be
        modified.
        """
        entry = (self.inc << 1) | self.shft
        display = (self.on << 2) | (self.cur << 1) | self.blnk
        chars = self.get_custom_chars()
        ddram_addr = self.get_addr()
        self.set_ddram_addr(0)
        self._write(self, 0x06)
        text = self.read(80)
        self.set_ddram_addr(ddram_addr)
        self._write(self, 0x04 | entry)
        return entry, display, chars, ddram_addr, text
    @state.setter
    def state(self, state):
        entry, display, chars, ddram_addr, text = state
        self._write(self, 0x06)
        self.set_custom_chars(*chars)
        self.set_ddram_addr(0)
        self.write(text)
        self.set_ddram_addr(ddram_addr)
        self._write(self, 0x04 | (entry & 0x3))
        self._write(self, 0x08 | (display & 0x7))
    
    ##### WRITING / READING #####
    cdef inline void write_raw(self, unsigned char* s, Py_ssize_t n) nogil:
        cdef Py_ssize_t i
        for i in range(n): self._write_data(self, s[i])
    def write(self, bytes s):
        """
        Writes the string s to the LCD screen at the current cursor position. s must be a bytes or
        bytearray object. The cursor will be advanced by the length of the string (or reversed if
        increment is False). The screen will possibly be shifted if shift is True.
        """
        self.write_raw(<unsigned char*><char*>s, len(s))
    def write_at(self, pos, bytes s):
        """Equivilent to `lcd.position = pos; lcd.write(s)`"""
        self.position = pos
        self.write_raw(<unsigned char*><char*>s, len(s))
    cdef inline void read_raw(self, unsigned char* s, Py_ssize_t n) nogil:
        cdef Py_ssize_t i
        for i in range(n): s[i] = self._read_data(self)
    def read(self, int n=1):
        """
        Reads n values from the LCD screen at the current cursor position. The cursor will be
        advanced by the length of the string (or reversed if increment is False). The screen will
        possibly be shifted if shift is True.
        """
        cdef bytes s = PyBytes_FromStringAndSize(NULL, n)
        self.read_raw(<unsigned char*><char*>s, n)
        return s
    def read_from(self, pos, int n=1):
        """Equivilent to `lcd.position = pos; lcd.read(n)`"""
        self.position = pos
        cdef bytes s = PyBytes_FromStringAndSize(NULL, n)
        self.read_raw(<unsigned char*><char*>s, n)
        return s
        
    ##### ADVANCED WRITING / READING #####
    def read_all(self):
        """Reads all lines from the LCD into a list using read_from."""
        return [self.read_from((i, 0), self.nc) for i in range(self.nr)]

    def write_all(self, *lines):
        """Writes many lines to the LCD using write_at after clearing the screen."""
        from itertools import izip
        self.clear()
        for i, line in izip(range(self.nr), lines): # don't use enumerate as we want to stop when either of them is finished
            self.write_at((i, 0), line)

    def write_lines(self, lines, justify='left', bytes ellipsis=b'_'):
        """
        Writes lines to the LCD. See write_text() for more information. This function is a bit
        different in that the text is already split into lines when calling this function.
        """
        if len(lines) == 0: self.clear(); return
        if isinstance(lines[0], unicode): lines = [line.encode('ascii') for line in lines]
        justify = bytes.center if justify == 'center' else (bytes.rjust if justify == 'right' else bytes.ljust)
        trunc = len(lines) > self.nr
        lines = lines[:self.nr]
        for i,line in enumerate(lines):
            if len(line) > self.nc or trunc and i == len(lines) -1:
                line = line[:self.nc-1] + ellipsis
            lines[i] = justify(line, self.nc)
        self.write_all(*lines)

    def write_text(self, text, justify='left', bytes ellipsis=b'_'):
        """
        Writes text to the LCD, breaking it into lines that will fit on the screen and justifying
        each line as specified (default 'left' with 'center' and 'right' acceptable options). If
        a single word is longer than the width of the LCD than it is truncated and the given
        ellipsis character is appended (default is b'_' but the caller may want to define a
        custom character that makes more sense). If there are more lines than the height of the
        LCD the extras are dropped and the ellipsis character is added to the last line.
        """
        from textwrap import wrap
        self.write_lines(wrap(text, self.nc, break_long_words=False))
    
    ##### CUSTOM CHARACTERS #####
    def __execute_char(self, int i, f):
        """
        Runs an action for a specific character and making sure the shifting and incrementing
        is 'standard'. This remembers the data address and restores the shift and incrementing
        back.
        """
        cdef int ac = self.get_addr()
        self.set_cgram_addr(i*8)
        if self.inc and not self.shft:
            x = f()
        else:
            self._write(self, 0x06)
            x = f()
            self._write(self, 0x04 | (self.inc << 1) | self.shft)
        self.set_ddram_addr(ac)
        return x

    def set_custom_char(self, int i, data):
        """
        Set the i-th custom character with the given data. i must be an integer from 0 to 7.
        The data must be a length-8 bytes or bytearray with each value specifying one row of the
        character data (typically a value from 0x00 to 0x1F).
        """
        if i < 0: i += 8
        if i < 0 or i > 7: raise IndexError('Character number must be from 0 to 7')
        if not isinstance(data, (bytes, bytearray)): raise TypeError('data must be bytes or bytearray')
        if len(data) != 8: raise ValueError('Character data must be 8 bytes long')
        self.__execute_char(i, lambda:self.write(data))

    def set_custom_chars(self, *data, int off=0):
        """
        Sets many custom characters, starting at character off (default 0). The data is given as
        a squence of bytes or bytearrays as per set_custom_char.
        """
        if off < 0: off += 8
        if off < 0 or len(data) + off > 8: raise IndexError('Character number must be from 0 to 7')
        if not all(isinstance(c, (bytes, bytearray)) for c in data): raise TypeError('data must be a sequence of bytes or bytearray')
        if any(len(c) != 8 for c in data): raise ValueError('Character data must be 8 bytes long each')
        self.__execute_char(off, lambda:self.write(b''.join(bytes(c) for c in data)))

    def get_custom_char(self, int i):
        """Gets the i-th custom character from the LCD. i must be an integer from 0 to 7."""
        if i < 0: i += 8
        if i < 0 or i > 7: raise IndexError('Character number must be from 0 to 7')
        return self.__execute_char(i, lambda:self.read(8))
        
    def get_custom_chars(self, int start=0, int stop=8):
        """
        Gets the custom characters from the LCD. By default this gets all characters, however the
        arguments start and stop can be used to specify other ranges of characters.
        """
        if start < 0: start += 8
        if stop  < 0: stop  += 8
        if start < 0 or start > 7 or stop < 0 or stop > 8: raise IndexError('Character number must be from 0 to 7')
        cdef int n = stop - start, i
        if n <= 0: return []
        data = self.__execute_char(start, lambda:self.read(8*n))
        return [data[i:i+8] for i in range(0, 8*n, 8)]

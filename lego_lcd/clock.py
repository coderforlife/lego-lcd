#!/usr/bin/env python

from time import time, sleep
from datetime import datetime

show24h = False
weekdays = (b'Mon', b'Tue', b'Wed', b'Thu', b'Fri', b'Sat', b'Sun')
months = (b'Jan', b'Feb', b'Mar', b'Apr', b'May', b'Jun',
          b'Jul', b'Aug', b'Sep', b'Oct', b'Nov', b'Dec')

def write_day(lcd, dt: datetime, bignum_digits: tuple[bytes]):
    """Write the day of the week and the date to the LCD."""
    lcd.write_at((0,1), b'%3s %02d'%(weekdays[dt.weekday()], dt.day))
    lcd.write_at((1,0), b'%3s %4d'%(months[dt.month-1], dt.year))


def write_hour(lcd, h: int, bignum_digits: tuple[bytes]):
    """Write the hour to the LCD along with am/pm."""
    write_2_digit(lcd, 10, h if show24h else (12 if h == 0 else (h-12*(h>12))), bignum_digits, False)
    lcd.write_at((1,18), (b'  ' if show24h else (b'am' if h < 12 else b'pm')))


def write_min(lcd, m: int, bignum_digits: tuple[bytes]):
    """Write the minutes to the LCD."""
    write_2_digit(lcd, 13, m, bignum_digits)


def write_sec(lcd, s: int, bignum_digits: tuple[bytes]):
    """Write the seconds to the LCD."""
    write_2_digit(lcd, 16, s, bignum_digits)


def write_2_digit(lcd, column: int, value: int, bignum_digits: tuple[bytes],
                  leading_zero: bool = True):
    """Write a 2-digit number to the LCD using big numbers."""
    q, r = divmod(value, 10)
    leading_space = q == 0 and not leading_zero
    for i in range(len(bignum_digits)):
        s = (b' ' if leading_space else bignum_digits[i][q:q+1]) + bignum_digits[i][r:r+1]
        lcd.write_at((i, column), s)


def run_clock(lcd = None):
    """Run the clock on the LCD."""
    if lcd is None:
        from .lcd_helper import lcd_setup
        lcd = lcd_setup(1.0, 0.4)

    bignums = load_bignum(lcd)

    lcd.clear()
    lcd.write_at((0,12), b'\xCD'); lcd.write_at((1,12), b'\xCD')
    lcd.write_at((0,15), b'\xCD'); lcd.write_at((1,15), b'\xCD')

    old = datetime.now()
    write_day(lcd, old, bignums)
    write_hour(lcd, old.hour, bignums)
    write_min(lcd, old.minute, bignums)
    while True:
        x = datetime.now()
        if old.day != x.day or old.month != x.month or old.year != x.year: write_day(lcd, x, bignums)
        if old.hour != x.hour: write_hour(lcd, x.hour, bignums)
        if old.minute != x.minute: write_min(lcd, x.minute, bignums)
        write_sec(lcd, x.second, bignums)
        old = x
        slp = 0.999-time()%1 # not 1.0 - x since it seems it takes ~1 ms to just get to the top of the loop
        if slp > 0: sleep(slp)


def load_bignum(lcd) -> tuple[bytes]:
    """Load the big numbers into the LCD and return the digits."""
    lcd.set_custom_chars(
        b'\x03\x03\x03\x03\x03\x03\x03\x03', #   |
        b'\x1F\x1F\x1B\x1B\x1B\x1B\x1B\x1B', # |^|
        b'\x1B\x1B\x1B\x1B\x1B\x1B\x1F\x1F', # |_|
        b'\x1F\x1F\x03\x03\x03\x03\x03\x03', #  ^|
        b'\x1F\x1F\x18\x18\x18\x18\x18\x18', # |^
        b'\x1F\x1F\x18\x18\x18\x18\x1F\x1F', # |^_
        b'\x1F\x1F\x1B\x1B\x1B\x1B\x1F\x1F', # |^_|
        b'\x1F\x1F\x03\x03\x03\x03\x1F\x1F'  #  _^|
    )
    return (
        b'\x01\x00\x03\x03\x02\x04\x04\x03\x06\x06',
        b'\x02\x00\x05\x07\x00\x07\x06\x00\x02\x00',
    )


def main():
    from .lcd_helper import lcd_setup
    from .wifi_connect import local_ip, run_captive_portal
    lcd = lcd_setup(1.0, 0.4)
    
    def callback(msg: str, detail: str = None):
        """
        Callback from the captive portal. The message and detail is one of:
        - 'ready' and the SSID of the hotspot
        - 'connecting' and the SSID of the network being connected to
        - 'failed' and None
        """
        if msg == 'ready':
            lcd.write_lines(['Connect to', detail], 'center')
        elif msg == 'connecting':
            lcd.write_lines(['Connecting to', detail], 'center')
        elif msg == 'failed':
            lcd.write_lines(['Failed to connect', 'Try again'], 'center')

    # Wait for network to connect
    lcd.write_lines(['Network', 'connecting...'], 'center')
    for _ in range(15):
        ip = local_ip()
        if ip: break
        sleep(1)
    else:
        run_captive_portal("Lego Clock Hotspot", callback=callback)
        sleep(1)
        ip = local_ip()
    
    # Show the local IP address
    lcd.write_lines(['Local IP:', str(ip)], 'center')
    sleep(10)

    # Run the clock
    run_clock(lcd)


if __name__ == "__main__":
    main()

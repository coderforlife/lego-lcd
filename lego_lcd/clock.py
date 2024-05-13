#!/usr/bin/env python

from time import time, sleep
from datetime import datetime

# requires: <wifi_selection>, <lcd_helper>

show24h = False
weekdays = (b'Mon', b'Tue', b'Wed', b'Thu', b'Fri', b'Sat', b'Sun')
months = (b'Jan', b'Feb', b'Mar', b'Apr', b'May', b'Jun',
          b'Jul', b'Aug', b'Sep', b'Oct', b'Nov', b'Dec')

def write_day(lcd, dt, bignum_digits):
    lcd.write_at((0,1), b'%3s %02d'%(weekdays[dt.weekday()], dt.day))
    lcd.write_at((1,0), b'%3s %4d'%(months[dt.month-1], dt.year))

def write_hour(lcd, h, bignum_digits):
    q, r = divmod(h if show24h else (12 if h == 0 else (h-12*(h>12))), 10)
    lcd.write_at((0,10), (b' ' if q == 0 else bignum_digits[0][q]) + bignum_digits[0][r])
    lcd.write_at((1,10), (b' ' if q == 0 else bignum_digits[1][q]) + bignum_digits[1][r])
    lcd.write_at((1,18), (b'  ' if show24h else (b'am' if h < 12 else b'pm')))

def write_min(lcd, m, bignum_digits):
    q, r = divmod(m, 10)
    lcd.write_at((0,13), bignum_digits[0][q] + bignum_digits[0][r])
    lcd.write_at((1,13), bignum_digits[1][q] + bignum_digits[1][r])

def write_sec(lcd, s, bignum_digits):
    q, r = divmod(s, 10)
    lcd.write_at((0,16), bignum_digits[0][q] + bignum_digits[0][r])
    lcd.write_at((1,16), bignum_digits[1][q] + bignum_digits[1][r])

def run_clock(lcd = None):
    if lcd is None:
        from lcd_helper import lcd_setup
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

def load_bignum(lcd):
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
    lcd = lcd_setup(1.0, 0.4)

    #from .wifi_selection import run_select_wifi
    #run_select_wifi(lcd)

    run_clock(lcd)


if __name__ == "__main__":
    main()


# Button on pin 24
#def onpress(pin):
#    if RPi.GPIO.input(pin): print("up")
#    else: print("down")
#RPi.GPIO.setup(24, RPi.GPIO.IN, RPi.GPIO.PUD_UP)
#RPi.GPIO.add_event_detect(24, RPi.GPIO.BOTH, onpress, 1)
# #RPi.GPIO.remove_event_detect(24)

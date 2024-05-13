# -*- coding: utf-8 -*-
"""
Helpers for useing the LCD library. In general these are all specific to my setup and devices.
"""

import RPi.GPIO, lcd

__all__ = ["lcd_setup", "set_contrast", "set_backlight", "beep", "as_bytes"]

# BCM #:      # wiringPi #:
BEEP_PIN = 27 # 2
CT_PIN = 13   # 23
BL_PIN = 12   # 26
RS_PIN = 2    # 8
RW_PIN = 3    # 9
EN_PIN = 4    # 7
DB_PINS = (17, 18, 15, 14) # (0, 1, 16, 15)
LCD_DIM = (20, 2) # several parts in the code still assume 20x2
ASCII_TRANS = {
    # Pass-through of custom characters
    '\x00':'\x00', '\x01':b'\x01', '\x02':b'\x02', '\x03':b'\x03', '\x04':b'\x04', '\x05':b'\x05', '\x06':b'\x06', '\x07':b'\x07',
    # Pass-through of special characters to be handled specialy
    '\t':b'\t','\n':b'\n','\r':b'\r',
    # Whitespace that maps to space or nothing
    ' ':b' ',' ':b' ','​':b'',
    # Standard ASCII table from here on with some special additions for alternative quotes, hyphens, and tildes
    '!':b'!', '"':b'"', '#':b'#', '$':b'$', '%':b'%', '&':b'&', '\'':b'\'', '(':b'(', ')':b')',
    '*':b'*', '∗':b'*', '+':b'+', ',':b',', '-':b'-', '‐':b'-', '‑':b'-', '‒':b'-', '–':b'-', '⁃':b'-', '−':b'-', '.':b'.', '/':b'/',
    '0':b'0', '1':b'1', '2':b'2', '3':b'3', '4':b'4', '5':b'5', '6':b'6', '7':b'7', '8':b'8', '9':b'9',
    ':':b':', ';':b';', '<':b'<', '‹':b'<', '〈':b'<', '⟨':b'<', '〈':b'<', '=':b'=', '>':b'>', '›':b'>', '〉':b'>', '⟩':b'>', '〉':b'>', '?':b'?', '@':b'@',
    'A':b'A', 'B':b'B', 'C':b'C', 'D':b'D', 'E':b'E', 'F':b'F', 'G':b'G', 'H':b'H', 'I':b'I', 'J':b'J', 'K':b'K', 'L':b'L', 'M':b'M',
    'N':b'N', 'O':b'O', 'P':b'P', 'Q':b'Q', 'R':b'R', 'S':b'S', 'T':b'T', 'U':b'U', 'V':b'V', 'W':b'W', 'X':b'X', 'Y':b'Y', 'Z':b'Z',
    '[':b'[', '\\':b'\\', ']':b']', '^':b'^', '_':b'_', '`':b'`',
    'a':b'a', 'b':b'b', 'c':b'c', 'd':b'd', 'e':b'e', 'f':b'f', 'g':b'g', 'h':b'h', 'i':b'i', 'j':b'j', 'k':b'k', 'l':b'l', 'm':b'm',
    'n':b'n', 'o':b'o', 'p':b'p', 'q':b'q', 'r':b'r', 's':b's', 't':b't', 'u':b'u', 'v':b'v', 'w':b'w', 'x':b'x', 'y':b'y', 'z':b'z',
    '{':b'{', '|':b'|', '}':b'}', '~':b'~', '˜':b'~', '̃':b'~'
}
LCD_TRANS = {
    # Math pt 1 (pre-ASCII values)
    '±':b'\x10', '≡':b'\x11', '⎲':b'\x12', '⎳':b'\x13', '⎛':b'\x14', '⎝':b'\x15', '⎞':b'\x16', '⎠':b'\x17', '⎰':b'\x18', '⎱':b'\x19',
    '≈':b'\x1A', '∫':b'\x1B', '‗':b'\x1C', '͇':b'\x1C', '̳':b'\x1C', '∼':b'\x1D', '²':b'\x1E', '³':b'\x1F',

    # Latin symbols with grave, acute, circumflex, dieresis, cedilla, tildes, and dots/rings
    # The order is all jumbled (presented here in a bit more logical order)
    # Some letters only had the lower-case version so the uppercase letter maps to the lowercase version
    'à':b'\x85', 'À':b'\x85', 'á':b'\xA0', 'Á':b'\xA0', 'â':b'\x83', 'Â':b'\x8F', 'ä':b'\x84', 'Ä':b'\x8E',
    'ã':b'\xAB', 'Ã':b'\xAA', 'å':b'\x86', 'Å':b'\x86', 'ȧ':b'\x86', 'Ȧ':b'\x86',
    'æ':b'\x91', 'Æ':b'\x92',
    'ç':b'\x87', 'Ç':b'\x80',
    'è':b'\x8A', 'È':b'\x8A', 'é':b'\x82', 'É':b'\x90', 'ê':b'\x88', 'Ê':b'\x88', 'ë':b'\x89', 'Ë':b'\x89',
    'ì':b'\x8D', 'Ì':b'\x8D', 'í':b'\xA1', 'Í':b'\xA1', 'î':b'\x8C', 'Î':b'\x8C', 'ï':b'\x8B', 'Ï':b'\x8B',
    'ñ':b'\x9B', 'Ñ':b'\x9C',
    'ò':b'\x95', 'Ò':b'\x95', 'ó':b'\xA2', 'Ó':b'\xA2', 'ô':b'\x93', 'Ô':b'\x93', 'ö':b'\x94', 'Ö':b'\x99',
    'õ':b'\xAD', 'Õ':b'\xAC',
    'ù':b'\x97', 'Ù':b'\x97', 'ú':b'\xA3', 'Ú':b'\xA3', 'û':b'\x96', 'Û':b'\x96', 'ü':b'\x81', 'Ü':b'\x9A',
    'ÿ':b'\x98', 'Ÿ':b'\x98', 'Ÿ':b'\x98', # the last version is actually "APPLICATION PROGRAM COMMAND" in unicode
    '̲a':b'\x9D', '̲o':b'\x9E', # these won't actually work since they use combining characters

    # Special punctuation, diactrics, and currency symbols
    '¿':b'\x9F', '¡':b'\xA9',
    '¢':b'\xA4', '£':b'\xA5', '¥':b'\xA6', '₧':b'\xA7', 'ƒ':b'\xA8',
    'Ø':b'\xAE', '∅':b'\xAE', 'ø':b'\xAE', '⌀':b'\xAF',
    '˙':b'\xB0', '̇':b'\xB0',
    '¨':b'\xB1', '̈':b'\xB1',
    '°':b'\xB2', '˚':b'\xB2', '̊':b'\xB2', '⁰':b'\xB2',
    '‘':b'\xB3', '‚':b'\xB3', '‛':b'\xB3', '‵':b'\xB3', '`':b'\xB3', 'ˋ':b'\xB3', '̀':b'\xB3', # grave accent
    '’':b'\xB4', 'ʹ':b'\xB4', '′':b'\xB4', 'ˊ':b'\xB4', '´':b'\xB4', 'ʹ':b'\xB4', '́':b'\xB4', # accute accent
    '″':b'"', '‶':b'"', '〃':b'"', '“':b'"', '”':b'"', '‟':b'"', '„':b'"', # double quotes (not actually here, but makes sense)

    # Math pt 2
    '½':b'\xB5', '¼':b'\xB6', '×':b'\xB7', '✕':b'\xB7', '÷':b'\xB8', '≤':b'\xB9', '≥':b'\xBA',
    '≪':b'\xBB', '«':b'\xBB', '《':b'\xBB', '≫':b'\xBC', '»':b'\xBC', '》':b'\xBC',
    '≠':b'\xBD', '√':b'\xBE', '¯':b'\xBF', '‾':b'\xBF',
    '⌠':b'\xC0', '⌡':b'\xC1', '∞':b'\xC2',

    # Arrows and boxes pt 1
    '◸':b'\xC3', # upper-left corner - nabla?
    '↲':b'\xC4', '↩':b'\xC4', '⏎':b'\xC4', '⮐':b'\xC4',
    '↑':b'\xC5', '↓':b'\xC6', '→':b'\xC7', '←':b'\xC8',
    '┌':b'\xC9', '┍':b'\xC9', '┎':b'\xC9', '┏':b'\xC9', '╔':b'\xC9', '╓':b'\xC8', '╒':b'\xC9',
    '┐':b'\xCA', '┑':b'\xCA', '┒':b'\xCA', '┓':b'\xCA', '╗':b'\xCA', '╕':b'\xC8', '╖':b'\xCA',
    '└':b'\xCB', '┕':b'\xCB', '┖':b'\xCB', '┗':b'\xCB', '╚':b'\xCB', '╘':b'\xC8', '╙':b'\xCB',
    '┘':b'\xCC', '┙':b'\xCC', '┚':b'\xCC', '┛':b'\xCC', '╝':b'\xCC', '╛':b'\xC8', '╜':b'\xCC',
    '◿':b'\xD5', '⊿':b'\xD5', # lower-right corner - in place of delta in Greek Uppercase

    # Typography symbols
    '∙':b'\xCD', '·':b'\xCD', '•':b'\xCD', '⋅':b'\xCD',
    '®':b'\xCE', 'Ⓡ':b'\xCE', 'ⓡ':b'\xCE',
    '©':b'\xCF', 'Ⓒ':b'\xCF', 'ⓒ':b'\xCF',
    '™':b'\xD0',
    '†':b'\xD1', '†':b'\xD1', # the last version is actually "START OF SELECTED AREA" in unicode
    '§':b'\xD2', '¶':b'\xD3',

    # Greek Uppercase
    # Many of these do not have dedicated symbols and are mapped to the latin capital letters
    # Delta is out-of-order and is mapped to increment and white-upwards-triangle
    # Upsilon is oddly drawn (double-hooked)
    # Sigma and Pi also map from the mathemetical operators
    'Α':'A', 'Β':'B', 'Γ':b'\xD4',
    'Δ':b'\x7F', '∆':b'\x7F', '△':b'\x7F', 'Ε':'E', 'Ζ':'Z', 'Η':'H', 
    'Θ':b'\xD6', 'Ι':'I', 'Κ':'K', 'Λ':b'\xD7', 'Μ':'M', 'Ν':'N', 'Ξ':b'\xD8', 
    'Ο':'O', 'Π':b'\xD9', '∏':b'\xD9', 'Ρ':'P', 'Σ':b'\xDA', 'Ʃ':b'\xDA', '∑':b'\xDA',
    'Τ':'T', 'Υ':'\xDB', 'ϒ':'\xDB', '⥾':'\xDB', 'Φ':b'\xDC', 'Χ':'X', 'Ψ':b'\xDD', 'Ω':b'\xDE',

    # Greek Lowercase
    # Missing dedicated omicron (mapped to o), missing φ (phi) and ς (final sigma)
    # Also maps proportional-to to alpha and micro to mu
    'α':b'\xDF', '∝':b'\xDF', 'β':b'\xE0', 'γ':b'\xE1', 'δ':b'\xE2', 'ε':b'\xE3', '∈':b'\xE3', 'ζ':b'\xE4', 'η':b'\xE5',
    'θ':b'\xE6', 'ι':b'\xE7', 'κ':b'\xE8', 'λ':b'\xE9', 'μ':b'\xEA', 'µ':b'\xEA', 'ν':b'\xEB', 'ξ':b'\xEC', 'ο':b'o',
    'π':b'\xED', 'ρ':b'\xEE', 'σ':b'\xEF', 'τ':b'\xF0', 'υ':b'\xF1', 'χ':b'\xF2', 'ψ':b'\xF3', 'ω':b'\xF4',

    # Arrows and Boxes pt 2 and misc letters
    '▼':b'\xF5', '⯆':b'\xF5', '⏷':b'\xF5', '🞃':b'\xF5', '▾':b'\xF5',
    '▶':b'\xF6', '⏵':b'\xF6', '🞂':b'\xF6', '▸':b'\xF6',
    '◀':b'\xF7', '◄':b'\xF7', '⏴':b'\xF7', '⯇':b'\xF7', '◂':b'\xF7',
    '𝐑':b'\xF8', '𝗥':b'\xF8', '𝓡':b'\xF8', '𝕽':b'\xF8',
    '↤':b'\xF9', '⟻':b'\xF9',
    '𝐅':b'\xFA', '𝗙':b'\xFA', '𝔽':b'\xFA', '𝓕':b'\xFA', '𝕱':b'\xFA',
    '⇥':b'\xFB',
    '□':b'\xFC', '▯':b'\xFC', '◻':b'\xFC', '⬜':b'\xFC', '◽':b'\xFC', # actually a white box
    '━':b'\xFD', '─':b'\xFD', '⏤':b'\xFD', '▬':b'\xFD',
    '🆂':b'\xFE', '🅢':b'\xFE', '🅿':b'\xFF', '🅟':b'\xFF',
}
LCD_TRANS.update(ASCII_TRANS)


def lcd_setup(ct=None, bl=None):
    """Setup the LCD and other GPIO items. Returns the LCD object."""
    lcd.wiringPiSetupGpio()
    RPi.GPIO.setmode(RPi.GPIO.BCM)  # TODO: remove
    lcd.pinMode(CT_PIN, lcd.PWM_OUTPUT)
    if ct is not None: set_contrast(ct)
    lcd.pinMode(BL_PIN, lcd.PWM_OUTPUT)
    if bl is not None: set_backlight(bl)
    return lcd.LCD(RS_PIN, RW_PIN, EN_PIN, DB_PINS, LCD_DIM)

def set_contrast(ct):
    """Sets the LCD contrast amount, ct is a value from 0.0 to 1.0"""
    lcd.pwmWrite(CT_PIN, int(max(min(ct, 1.0), 0.0)*512))

def set_backlight(bl):
    """Sets the LCD backlight amount, bl is a value from 0.0 to 1.0"""
    lcd.pwmWrite(BL_PIN, int(max(min(bl, 1.0), 0.0)*1024))

def beep(freq=1000, dur=0.1):
    """Emit a beep"""
    lcd.beep(BEEP_PIN, freq, dur)

def as_bytes(s, trans=None):
    """
    Ensure a string is in bytes for suitable use with the LCD. If it is given as unicode it is
    converted to bytes using the given translation (or the global LCD_TRANS if not provided).
    Characters not available in the translation are replaced with ?.

    The translation should be a dictionary which has single unicode characters as keys and
    byte characters or strings as values. This conversion is not performed if it is already
    bytes.
    """
    if isinstance(s, bytes): return s
    if trans is None: trans = LCD_TRANS
    return b''.join(trans.get(ch, b'?') for ch in s)

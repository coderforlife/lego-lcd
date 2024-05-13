from setuptools import setup, Extension
from Cython.Build import cythonize

# Modules to be compiled and include_dirs when necessary
extensions = [
    Extension("lego_lcd.lcd", ["lego_lcd/lcd.pyx"], libraries=["wiringPi"], library_dirs=["/usr/local/lib"], include_dirs=["/usr/local/include"]),
    #Extension("lego_lcd.kbd", ["lego_lcd/kbd.pyx"]),
]

# This is the function that is executed
setup(
    name='lego_lcd',
    ext_modules = cythonize(extensions, compiler_directives={"language_level": 3, "profile": False}),
)

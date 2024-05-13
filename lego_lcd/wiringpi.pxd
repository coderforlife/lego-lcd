#cython: language_level=3

# Define the wiringPi functions we want to use

cdef extern from "wiringPi.h":
    cdef enum:
        INPUT = 0
        OUTPUT = 1
        PWM_OUTPUT = 2

    int wiringPiSetup() nogil
    int wiringPiSetupGpio() nogil
    int wiringPiSetupPhys() nogil
    int wiringPiSetupSys() nogil

    void pinMode(int pin, int mode) nogil
    void digitalWrite(int pin, int value) nogil
    void pwmWrite(int pin, int value) nogil
    int digitalRead(int pin) nogil

    unsigned int millis() nogil
    unsigned int micros() nogil
    void delay(unsigned int howLong) nogil
    void delayMicroseconds(unsigned int howLong) nogil

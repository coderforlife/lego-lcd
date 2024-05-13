#!/usr/bin/env bash

# We need to be in the gpio group (but this won't take effect until we log out and back in)
sudo usermod -a -G gpio $USER

# Installs the system-wide dependencies for the project
sudo apt install python3-dev

# TODO: wiringPi C library

#!/usr/bin/env bash

# We need to be in the gpio group (but this won't take effect until we log out and back in)
sudo usermod -a -G gpio $USER

# Installs the system-wide dependencies for the project
sudo apt install python3-dev

# Install wiringPi C library
version="3.4"
arch=$(dpkg --print-architecture)
name="wiringpi_${version}_${arch}.deb"
wget "https://github.com/WiringPi/WiringPi/releases/download/$version/$name"
sudo dpkg -i "$name"
rm "$name"


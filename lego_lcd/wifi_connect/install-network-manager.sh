#!/usr/bin/env bash

echo "This script is optional."
echo "It verifies NetworkManager is installed."
echo ""
echo "Modern Raspberry Pi (starting with Bookworm in Oct 2023) uses NetworkManager by default."
echo "On Raspbian Bullseye you should select it with raspi-config instead."
echo "On older versions of Raspbian you may need to install it manually with this script."

if which nmcli > /dev/null; then
    echo "NetworkManager is already installed."
    exit 0
fi

# Confirm the user wants to install...
read -r -p "Do you want to install? [y/N]: " response
response=${response,,}  # convert to lowercase
if [[ ! $response =~ ^(yes|y)$ ]]; then
    exit 0
fi

# Update packages and install
install_network_manager

echo "Updating package list..."
apt-get update

echo "Downloading NetworkManager..."
apt-get install -y -d network-manager

echo "Stopping dhcpcd..."
systemctl stop dhcpcd
systemctl disable dhcpcd

echo "Installing NetworkManager..."
apt-get install -y network-manager
apt-get clean

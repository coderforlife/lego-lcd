wifi-connect
============

Library for connecting a Raspberry Pi to a wifi network without a screen or keyboard. This works by creating a temporary hotspot using the Raspberry Pi that the user then connects to with the phone or other wifi-capable device. The user enters the details and the Raspberry Pi connects to the wifi. Requires to "sdbus-networkmanager" Python package along with a system setup to use NetworkManager to manage network connections and has the program `dnsmasq` available.

This module has heavy inspiration from [OpenAg](https://www.media.mit.edu/groups/open-agriculture-openag/overview/)'s [python-wifi-connect](https://github.com/OpenAgricultureFoundation/python-wifi-connect/tree/master) which itself was inspired by the [wifi-connect](https://github.com/balena-io/wifi-connect) project written by [balena.io](https://www.balena.io/).

Unlike the above though, this is designed to be used from Python and not just on the CLI. This allows for hooks into the code so that messages can be displayed when desired (e.g. to an LCD screen).

The module has the following functions exposed:

* `has_internet` - checks if there is a current active internet connection
* `local_ip` - gets the local IP of the machine
* `external_ip` - gets the external IP of the machine
* `get_all_access_points` - gets a dict of all access points
* `delete_all_wifi_connections` - remove all existing remembered wifi connections
* `connect_to_ap` - connect to an access point
* `run_server` - run the webserver (and only the webserver)
* `run_captive_portal` - run the hotspot, dnsmasq service, and webserver

The dnsmasq library provides wrapper around the `dnsmasq` program to start and stop a basic DNS/DHCP server.

The netman library provides utilities for workign with the NetworkManager tool to discover and connect to wifi networks.

The http_server library provides the HTTP server along with a command-line program for running it.

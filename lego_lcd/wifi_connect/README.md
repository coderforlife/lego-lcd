wifi-connect
============

This module has heavy inspiration from [OpenAg](https://www.media.mit.edu/groups/open-agriculture-openag/overview/)'s [python-wifi-connect](https://github.com/OpenAgricultureFoundation/python-wifi-connect/tree/master) which itself was inspired by the [wifi-connect](https://github.com/balena-io/wifi-connect) project written by [balena.io](https://www.balena.io/).

Unlike the above though, this is designed to be used from Python and not just on the CLI. This allows for hooks into the code so that messages can be displayed when desired (e.g. to an LCD screen).

The module has the following functions exposed:

* `has_internet` - checks if there is a current active internet connection
* `local_ip` - gets the local IP of the machine
* `external_ip` - gets the external IP of the machine
* `get_all_access_points` - gets a dict of all access points
* `delete_all_wifi_connections` - remove all existing wifi connections
* `connect_to_ap` - connect to an access point
* `run_server` - run the webserver (and only the webserver)
* `run_captive_portal` - run the hotspot, dnsmasq service, and webserver

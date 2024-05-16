# Our main wifi-connect application, which is based around an HTTP server.

import os, getopt, sys, json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs

from .defaults import DEFAULT_GATEWAY
from .utils import have_internet
from .netman import get_all_access_points, hotspot, start_hotspot, stop_hotspot, connect_to_ap, delete_all_wifi_connections
from .dnsmasq import dnsmasq

# Defaults
ADDRESS = DEFAULT_GATEWAY
PORT = 80
UI_PATH = '../ui'


class CaptiveHTTPReqHandler(SimpleHTTPRequestHandler):
    """
    Custom request handler for our HTTP server.
    Handles the GET and POST requests from the UI form and JS.
    """
    def do_GET(self):
        """Handle specific requests, otherwise let the server handle it."""

        print(f'do_GET {self.path}')

        # Not sure if this is just OSX hitting the captured portal,
        # but we need to exit if we get it.
        if self.path == '/bag': self.server.shutdown()  # TODO: deadlocks unless in a different thread?

        # Handle the hotspot starting and a computer connecting to it,
        # we have to return a redirect to the gateway to get the 
        # captured portal to show up.
        elif self.path in ('/hotspot-detect.html', '/generate_204'):
            self.send_response(301) # redirect
            address, port = self.server.server_address
            url = f'http://{address}/' if port == 80 else f'http://{address}:{port}/'
            self.send_header('Location', url)
            self.end_headers()

        # Handle a REST API request to return the list of APs
        elif self.path == '/networks':
            aps = get_all_access_points(scan=True)
            data = json.dumps([
                (ap.ssid, ap.strength, ap.security.name) for ap in aps
                if ap.ssid and ap.strength > 0  # strength == 0 is the hotspot itself
            ]).encode('utf-8')
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        else:
            # All other requests are handled by the server which sends files
            # from the ui_path we were initialized with.
            super().do_GET()

    def do_POST(self):
        """Handle the form post from the UI."""
        # test with: curl localhost:5000 -d "{'name':'value'}"
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))

        # Parse the form post
        if 'ssid' not in data:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"status":"Invalid Input"}\n')
            return
        ssid = data['ssid']
        hidden = data.get('hidden', False)
        username = data.get('identity', None)
        password = data.get('passphrase', None)
        # TODO: Could check 'security' for appropriate security type and validate username/password

        # Stop the hotspot
        stop_hotspot()

        try:
            # Connect to the user's selected AP
            connect_to_ap(ssid, username, password, hidden)

            # Report success
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"Success"}\n')
            self.server.shutdown()  # TODO: deadlocks unless in a different thread?
        except Exception as e:
            print(f'Failed to connect to {ssid}: {e}')
            # Start the hotspot again
            start_hotspot()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"status":"Unable to connect wi-fi"}\n')


def main(address, port, ui_path):
    # Check if we are already connected, if so we are done.
    if have_internet():
        return

    # Find the ui directory which is up one from where this file is located.
    web_dir = os.path.join(os.path.dirname(__file__), ui_path)

    # Start the hotspot and dnsmasq (to advertise us as a router so captured portal pops up)
    with hotspot(), dnsmasq():
        # Start an HTTP server to serve the content in the ui dir and handle the 
        # POST request in the handler class.
        print(f'Waiting for a connection to our hotspot ...')
        with HTTPServer((address, port), CaptiveHTTPReqHandler, directory=web_dir) as httpd:
            httpd.serve_forever()


if __name__ == "__main__":
    address = ADDRESS
    port = PORT
    ui_path = UI_PATH

    usage = f"""Command line args:
  -a <HTTP server address>     Default: {address}
  -p <HTTP server port>        Default: {port}
  -u <UI directory to serve>   Default: "{ui_path}"
  -d Delete Connections First
  -h Show help."""

    try:
        opts, args = getopt.getopt(sys.argv[1:], "a:p:u:r:dh")
    except getopt.GetoptError:
        print(usage)
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print(usage)
            sys.exit()

        elif opt in ("-d"):
           delete_all_wifi_connections()

        elif opt in ("-a"):
            address = arg

        elif opt in ("-p"):
            port = int(arg)

        elif opt in ("-u"):
            ui_path = arg

    main(address, port, ui_path)

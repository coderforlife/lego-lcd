# Our main wifi-connect application, which is based around an HTTP server.

import os, argparse, json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

from .defaults import DEFAULT_HOTSPOT_SSID, DEFAULT_GATEWAY, DEFAULT_PORT, DEFAULT_UI_PATH
from .utils import have_internet
from .netman import (get_all_access_points, hotspot, start_hotspot, stop_hotspot,
                     connect_to_ap, delete_all_wifi_connections)
from .dnsmasq import dnsmasq


def __print_callback(msg: str, detail: str = None):
    """
    Callback from the captive portal. The message and detail is one of:
    - 'ready' and the SSID of the hotspot
    - 'connecting' and the SSID of the network being connected to
    - 'failed' and None
    """
    if msg == 'ready':
        print(f'Hotspot ready. Connect to {detail} to configure wifi.')
    elif msg == 'connecting':
        print(f'Connecting to wi-fi network {detail}.')
    elif msg == 'failed':
        print('Failed to connect. Try again')


class CaptiveHTTPReqHandler(SimpleHTTPRequestHandler):
    """
    Custom request handler for our HTTP server.
    Handles the GET and POST requests from the UI form and JS.
    """
    def __init__(self, *args, callback=__print_callback, **kwargs):
        self.callback = callback
        super().__init__(*args, **kwargs)


    def send_json(self, data: bytes, code: int = 200) -> None:
        """Send a JSON response with the given data."""
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


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
            self.send_json(data)

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
            self.send_json(b'{"status":"Invalid Input"}', 400)
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
            self.callback('connecting', ssid)
            connect_to_ap(ssid, username, password, hidden)

            # Report success
            self.send_json(b'{"status":"Success"}')
            self.server.shutdown()  # TODO: deadlocks unless in a different thread?
        except Exception as e:
            print(f'Failed to connect to {ssid}: {e}')
            self.callback('failed', None)

            # Start the hotspot again
            start_hotspot()
            self.send_json(b'{"status":"Unable to connect wi-fi"}', 500)


def run_server(address: str = DEFAULT_GATEWAY, port: int = DEFAULT_PORT,
               ui_path: str = DEFAULT_UI_PATH, callback = __print_callback) -> None:
    """Run the HTTP server with the given address, port and UI path."""
    directory = os.path.normpath(ui_path)
    class WebServer(ThreadingHTTPServer):
        def finish_request(self, request, client_address):
            self.RequestHandlerClass(request, client_address, self,
                                     directory=directory, callback=callback)

    with WebServer((address, port), CaptiveHTTPReqHandler) as httpd:
        httpd.serve_forever()


def run_captive_portal(hotspot_ssid: str = DEFAULT_HOTSPOT_SSID,
                       address: str = DEFAULT_GATEWAY, port: int = DEFAULT_PORT,
                       ui_path: str = DEFAULT_UI_PATH, callback = __print_callback) -> None:
    """Run the captive portal including the hotspot, dnsmasq service, and HTTP server."""
    # Start the hotspot and dnsmasq
    with dnsmasq(gateway=address), hotspot(hotspot_ssid, address):
        callback('ready', hotspot_ssid)

        # Start an HTTP server
        run_server(address, port, ui_path, callback)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=
                                     'Run a captive portal HTTP server, hotspot, and dnsmasq')
    parser.add_argument('--ssid', '-s', default=DEFAULT_HOTSPOT_SSID,
                        help=f'SSID of the hotspot to create (default: "{DEFAULT_HOTSPOT_SSID}")')
    parser.add_argument('--address', '-a', default=DEFAULT_GATEWAY,
                        help=f'HTTP server address (default: {DEFAULT_GATEWAY})')
    parser.add_argument('--port', '-p', type=int, default=DEFAULT_PORT,
                        help=f'HTTP server port (default: {DEFAULT_PORT})')
    parser.add_argument('--ui-path', '-u', default=DEFAULT_UI_PATH,
                        help=f'Path to the UI directory to serve (default: {DEFAULT_UI_PATH})')
    parser.add_argument('--delete', '-d', action='store_true',
                        help='Delete all wifi connections initially')
    args = parser.parse_args()

    # Delete all wifi connections if requested
    if args.delete: delete_all_wifi_connections()

    # Check if we are already connected
    if not have_internet():
        run_captive_portal(args.ssid, args.address, args.port, args.ui_path)

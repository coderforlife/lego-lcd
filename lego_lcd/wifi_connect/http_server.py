# Our main wifi-connect application, which is based around an HTTP server.

import os, getopt, sys, json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs

# Local modules
from . import netman
from .utils import have_internet
from .netman import SecurityType
from .dnsmasq import dnsmasq

# Defaults
ADDRESS = '192.168.42.1'
PORT = 80
UI_PATH = '../ui'


#------------------------------------------------------------------------------
# A custom http request handler class factory.
# Handle the GET and POST requests from the UI form and JS.
# The class factory allows us to pass custom arguments to the handler.
def RequestHandlerClassFactory(address, aps):

    class MyHTTPReqHandler(SimpleHTTPRequestHandler):

        def __init__(self, *args, **kwargs):
            self.address = address
            self.aps = aps
            super().__init__(*args, **kwargs)

        # See if this is a specific request, otherwise let the server handle it.
        def do_GET(self):

            print(f'do_GET {self.path}')

            # Handle the hotspot starting and a computer connecting to it,
            # we have to return a redirect to the gateway to get the 
            # captured portal to show up.
            if self.path == '/hotspot-detect.html':
                self.send_response(301) # redirect
                new_path = f'http://{self.address}/'
                print(f'redirecting to {new_path}')
                self.send_header('Location', new_path)
                self.end_headers()
                return

            elif self.path == '/generate_204':
                self.send_response(301) # redirect
                new_path = f'http://{self.address}/'
                print(f'redirecting to {new_path}')
                self.send_header('Location', new_path)
                self.end_headers()
                return

            # Handle a REST API request to return the list of APs
            elif self.path == '/networks':
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(
                    {ssid:str(security) for ssid, security in self.aps.items()}
                ).encode('utf-8'))
                return

            # Not sure if this is just OSX hitting the captured portal,
            # but we need to exit if we get it.
            if self.path == '/bag': sys.exit()

            # All other requests are handled by the server which sends files
            # from the ui_path we were initialized with.
            super().do_GET()


        # test with: curl localhost:5000 -d "{'name':'value'}"
        def do_POST(self):
            fields = parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))

            # Parse the form post
            if 'ssid' not in fields:
                self.send_response(400)
                self.end_headers()
                return

            ssid = fields['ssid'][0]
            hidden = False
            if 'hidden-ssid' in fields:
                ssid = fields['hidden-ssid'][0]
                hidden = True
            username = fields['identity'][0] if 'identity' in fields else None
            password = fields['passphrase'][0] if 'passphrase' in fields else None

            # Look up the ssid in the list we sent, to find out its security
            # type for the new connection we have to make
            if not hidden and ssid in self.aps:
                ap = self.aps.ssid[ssid]
                if ap.security_type == SecurityType.NONE:
                    username = password = None
                elif ap.security_type == SecurityType.ENTERPRISE:
                    if username is None or password is None:
                        self.send_response(400)
                        self.end_headers()
                        return
                elif password is None:
                    self.send_response(400)
                    self.end_headers()
                    return
                else:
                    username = None

            # Stop the hotspot
            netman.stop_hotspot()

            # Connect to the user's selected AP
            netman.connect_to_ap(ssid=ssid, username=username, password=password)

            # Report success
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK\n')
            sys.exit()

            # print(f'Connection failed, restarting the hotspot.')

            # # Update the list of APs since we are not connected
            # self.ap = netman.get_list_of_access_points()

            # # Start the hotspot again
            # netman.start_hotspot()

    return  MyHTTPReqHandler # the class our factory just created.


#------------------------------------------------------------------------------
# Create the hotspot, start dnsmasq, start the HTTP server.
def main(address, port, ui_path):
    # Check if we are already connected, if so we are done.
    if have_internet():
        sys.exit()

    # Get list of available AP from net man.  
    # Must do this AFTER deleting any existing connections (above),
    # and BEFORE starting our hotspot (or the hotspot will be the only thing
    # in the list).
    aps = netman.get_list_of_access_points()

    # Start the hotspot and dnsmasq (to advertise us as a router so captured portal pops up)
    with netman.hotspot(), dnsmasq():
        # Find the ui directory which is up one from where this file is located.
        web_dir = os.path.join(os.path.dirname(__file__), ui_path)

        # Host:Port our HTTP server listens on
        server_address = (address, port)

        # Custom request handler class (so we can pass in our own args)
        MyRequestHandlerClass = RequestHandlerClassFactory(address, aps)

        # Start an HTTP server to serve the content in the ui dir and handle the 
        # POST request in the handler class.
        print(f'Waiting for a connection to our hotspot {netman.get_hotspot_SSID()} ...')
        httpd = HTTPServer(server_address, MyRequestHandlerClass, directory=web_dir)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()


def string_to_int(s, default):
    """Util to convert a string to an int, or provide a default."""
    try:
        return int(s)
    except ValueError:
        return default


#------------------------------------------------------------------------------
# Entry point and command line argument processing.
if __name__ == "__main__":


    address = ADDRESS
    port = PORT
    ui_path = UI_PATH
    delete_connections = False

    usage = ''\
f'Command line args: \n'\
f'  -a <HTTP server address>     Default: {address} \n'\
f'  -p <HTTP server port>        Default: {port} \n'\
f'  -u <UI directory to serve>   Default: "{ui_path}" \n'\
f'  -d Delete Connections First  Default: {delete_connections} \n'\
f'  -h Show help.\n'

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
           delete_connections = True

        elif opt in ("-a"):
            address = arg

        elif opt in ("-p"):
            port = string_to_int(arg, port)

        elif opt in ("-u"):
            ui_path = arg

    print(f'Address={address}')
    print(f'Port={port}')
    print(f'UI path={ui_path}')
    print(f'Delete Connections={delete_connections}')

    # See if caller wants to delete all existing connections first
    if delete_connections:
        netman.delete_all_wifi_connections()

    main(address, port, ui_path)

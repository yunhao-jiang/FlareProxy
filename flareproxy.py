import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import select
import socket
from urllib.parse import urlparse, urlunparse
import requests, time

# Get FlareSolverr URL from environment variable or use default
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://flaresolverr:8191/v1")

# Global variable to store session ID
SESSION_ID = None
TUNNEL_BUFFER_SIZE = 8192


def create_session():
    """Create a session in FlareSolverr and return the session ID."""
    try:
        headers = {"Content-Type": "application/json"}
        data = {"cmd": "sessions.create"}
        
        response = requests.post(FLARESOLVERR_URL, headers=headers, json=data)
        json_response = response.json()
        
        if response.status_code == 200 and json_response.get("status") == "ok":
            session_id = json_response.get("session")
            print(f"Session created: {session_id}")
            return session_id
        else:
            print(f"Failed to create session: {json_response}")
            return None
    except Exception as e:
        print(f"Error creating session: {e}")
        return None


def list_sessions():
    """List all sessions in FlareSolverr."""
    try:
        headers = {"Content-Type": "application/json"}
        data = {"cmd": "sessions.list"}
        
        response = requests.post(FLARESOLVERR_URL, headers=headers, json=data)
        json_response = response.json()
        
        if response.status_code == 200 and json_response.get("status") == "ok":
            sessions = json_response.get("sessions", [])
            print(f"Active sessions: {sessions}")
            return sessions
        else:
            print(f"Failed to list sessions: {json_response}")
            return []
    except Exception as e:
        print(f"Error listing sessions: {e}")
        return []


class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):

    @staticmethod
    def _should_use_flaresolverr(url):
        parsed_url = urlparse(url)
        return parsed_url.path.lower().endswith(".html")

    @staticmethod
    def _get_target_url(url):
        parsed_url = urlparse(url)
        return urlunparse(parsed_url._replace(scheme="https"))

    def handle_request(self):
        """Handle the core logic for GET and CONNECT requests."""
        try:
            target_url = self._get_target_url(self.path)
            if self._should_use_flaresolverr(target_url):
                headers = {"Content-Type": "application/json"}
                data = {
                    "cmd": "request.get",
                    "url": target_url,
                    "maxTimeout": 60000
                }

                if SESSION_ID:
                    data["session"] = SESSION_ID

                response = requests.post(FLARESOLVERR_URL, headers=headers, json=data)
                json_response = response.json()

                self.send_response(response.status_code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(bytes(json_response.get("solution", {}).get("response", ""), "utf-8"))
            else:
                response = requests.get(target_url, timeout=60)
                self.send_response(response.status_code)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/octet-stream"))
                self.end_headers()
                self.wfile.write(response.content)

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_message = json.dumps({"error": str(e)})
            self.wfile.write(error_message.encode("utf-8"))

    def do_GET(self):
        """Handle GET requests."""
        self.handle_request()

    def do_CONNECT(self):
        """Handle CONNECT requests."""
        try:
            host, port = self.path.split(":", 1)
            port = int(port)
            if port < 1 or port > 65535:
                raise ValueError("Port out of range")
            with socket.create_connection((host, port)) as upstream_socket:
                self.send_response(200, "Connection Established")
                self.end_headers()
                self._tunnel_connection(upstream_socket)
        except ValueError as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_message = json.dumps({"error": f"Invalid CONNECT target: {e}"})
            self.wfile.write(error_message.encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_message = json.dumps({"error": str(e)})
            self.wfile.write(error_message.encode("utf-8"))

    def _tunnel_connection(self, upstream_socket):
        sockets = [self.connection, upstream_socket]
        while True:
            readable, _, exceptional = select.select(sockets, [], sockets)
            if exceptional:
                break
            for source in readable:
                data = source.recv(TUNNEL_BUFFER_SIZE)
                if not data:
                    return
                destination = upstream_socket if source is self.connection else self.connection
                destination.sendall(data)


if __name__ == "__main__":
    # Create a session before starting the server
    
    time.sleep(15) # this is to allow FlareSolverr boots up and ready to accept session creation
    SESSION_ID = create_session()
    
    # List sessions to print the created session
    # list_sessions()
    
    server_address = ("", 8080)
    httpd = HTTPServer(server_address, ProxyHTTPRequestHandler)
    print("FlareProxy adapter running on port 8080")
    httpd.serve_forever()

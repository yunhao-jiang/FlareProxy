import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# Get FlareSolverr URL from environment variable or use default
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://flaresolverr:8191/v1")

# Global variable to store session ID
SESSION_ID = None


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

    def handle_request(self):
        """Handle the core logic for GET and CONNECT requests."""
        try:
            # Prepare the payload
            headers = {"Content-Type": "application/json"}
            data = {
                "cmd": "request.get",
                "url": self.path.replace("http", "https"),
                "maxTimeout": 60000
            }
            
            # Add session ID if available
            if SESSION_ID:
                data["session"] = SESSION_ID

            # Send the POST request to FlareSolverr
            response = requests.post(FLARESOLVERR_URL, headers=headers, json=data)
            json_response = response.json()

            # Forward the response back to the client
            self.send_response(response.status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(bytes(json_response.get("solution", {}).get("response", ""), "utf-8"))

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
        self.handle_request()


if __name__ == "__main__":
    # Create a session before starting the server
    SESSION_ID = create_session()
    
    # List sessions to print the created session
    list_sessions()
    
    server_address = ("", 8080)
    httpd = HTTPServer(server_address, ProxyHTTPRequestHandler)
    print("FlareProxy adapter running on port 8080")
    httpd.serve_forever()

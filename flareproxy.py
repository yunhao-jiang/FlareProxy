import json
import os
import socket
import select
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import time

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


class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def build_target_url(self):
        """Construct the target URL from the request line and Host header when needed."""
        url = self.path
        # If the client sent an absolute URL, use it.
        if url.startswith("http://") or url.startswith("https://"):
            return url.replace("http://", "https://", 1) if url.startswith("http://") else url
        # Otherwise build from Host header and the path (assume HTTPS by default as in previous behavior)
        host = self.headers.get("Host")
        if not host:
            return url  # fallback, may be invalid
        # Keep scheme as https to route through FlareSolverr
        if self.path.startswith("/"):
            return f"https://{host}{self.path}"
        return f"https://{host}/{self.path}"

    def handle_request(self):
        """Handle GET and POST requests by forwarding them to FlareSolverr."""
        try:
            # Read request body if present (for POST)
            content_length = int(self.headers.get("Content-Length", 0) or 0)
            body = None
            if content_length > 0:
                body = self.rfile.read(content_length).decode("utf-8", errors="ignore")

            # Determine command based on incoming method (FlareSolverr supports request.get and request.post)
            if self.command == "GET":
                cmd = "request.get"
            elif self.command == "POST":
                cmd = "request.post"
            else:
                self.send_response(405)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Method {self.command} not supported by proxy"}).encode("utf-8"))
                return

            # Build target URL
            url = self.build_target_url()

            # Prepare FlareSolverr payload
            headers = {"Content-Type": "application/json"}
            data = {
                "cmd": cmd,
                "url": url,
                "maxTimeout": 60000,
            }

            # Attach session if available
            if SESSION_ID:
                data["session"] = SESSION_ID

            # Attach POST body and original headers for POST requests
            if cmd == "request.post":
                # FlareSolverr expects a postData field with body and optionally contentType.
                post_data = {"body": body or ""}
                content_type = self.headers.get("Content-Type")
                if content_type:
                    post_data["contentType"] = content_type
                data["postData"] = post_data

            # Send to FlareSolverr
            fs_response = requests.post(FLARESOLVERR_URL, headers=headers, json=data, timeout=65)
            json_response = {}
            try:
                json_response = fs_response.json()
            except Exception:
                # If FlareSolverr didn't return JSON, return raw text
                resp_text = fs_response.text
                self.send_response(fs_response.status_code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(resp_text.encode("utf-8", errors="ignore"))
                return

            # If FlareSolverr returned a solution, try to forward the inner response body
            solution = json_response.get("solution", {})
            response_body = ""
            if isinstance(solution, dict):
                # Some FlareSolverr responses embed the response body in solution.response (string)
                # or solution.response.body; try multiple locations.
                response_body = solution.get("response") or ""
                if isinstance(response_body, dict):
                    # sometimes response may be an object with 'body'
                    response_body = response_body.get("body", "")
            else:
                response_body = json_response.get("response", "")

            # Send back to the client
            self.send_response(fs_response.status_code if fs_response is not None else 200)
            # Try to set content-type if available in solution.headers
            content_type = "text/html; charset=utf-8"
            try:
                sol_headers = solution.get("headers", {}) if isinstance(solution, dict) else {}
                if sol_headers:
                    # Normalize lookup for content-type
                    for k, v in sol_headers.items():
                        if k.lower() == "content-type":
                            content_type = v
                            break
            except Exception:
                pass

            self.send_header("Content-Type", content_type)
            self.end_headers()

            if isinstance(response_body, str):
                self.wfile.write(response_body.encode("utf-8", errors="ignore"))
            elif isinstance(response_body, bytes):
                self.wfile.write(response_body)
            else:
                # fallback to JSON encode
                self.wfile.write(json.dumps(response_body).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_message = json.dumps({"error": str(e)})
            self.wfile.write(error_message.encode("utf-8"))

    def do_GET(self):
        """Handle GET requests."""
        self.handle_request()

    def do_POST(self):
        """Handle POST requests."""
        self.handle_request()

    def do_CONNECT(self):
        self.send_response(501, "Not Implemented")
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        error_message = (
            "CONNECT method is not supported by FlareProxy.\n\n"
            "Please use HTTP URLs instead of HTTPS URLs in your client configuration.\n"
            "Example: http://www.discogs.com/sell/release/265683\n\n"
            "The proxy will automatically convert HTTP requests to HTTPS when forwarding to FlareSolverr, "
            "so your requests will still be secure.\n"
        )
        self.wfile.write(error_message.encode("utf-8"))
    #     """Handle CONNECT requests by establishing a direct TCP tunnel (not routed through FlareSolverr)."""
    #     try:
    #         # The path for CONNECT is usually "host:port"
    #         host_port = self.path
    #         if ":" in host_port:
    #             host, port_str = host_port.split(":", 1)
    #             port = int(port_str)
    #         else:
    #             host = host_port
    #             port = 443  # default to 443 if not specified

    #         # Establish connection to target host directly
    #         remote = socket.create_connection((host, port), timeout=10)
    #         # Inform the client that the connection is established
    #         self.send_response(200, "Connection Established")
    #         self.send_header("Proxy-agent", "FlareProxy/1.0")
    #         self.end_headers()

    #         # Hijack the underlying sockets and forward data both ways
    #         try:
    #             self._tunnel(self.connection, remote)
    #         finally:
    #             try:
    #                 remote.close()
    #             except Exception:
    #                 pass
    #     except Exception as e:
    #         # If unable to CONNECT directly, return an error to client
    #         self.send_response(502)
    #         self.send_header("Content-Type", "application/json")
    #         self.end_headers()
    #         error_message = json.dumps({"error": f"CONNECT failure: {str(e)}"})
    #         self.wfile.write(error_message.encode("utf-8"))

    # def _tunnel(self, client_sock, remote_sock, timeout=60):
    #     """Bidirectionally forward data between client_sock and remote_sock until closed."""
    #     client_sock.setblocking(0)
    #     remote_sock.setblocking(0)
    #     sockets = [client_sock, remote_sock]
    #     max_idle = timeout
    #     while True:
    #         try:
    #             rlist, _, xlist = select.select(sockets, [], sockets, 1)
    #         except Exception:
    #             break

    #         if xlist:
    #             break

    #         if rlist:
    #             for r in rlist:
    #                 try:
    #                     data = r.recv(8192)
    #                     if not data:
    #                         return
    #                     if r is client_sock:
    #                         dest = remote_sock
    #                     else:
    #                         dest = client_sock
    #                     dest.sendall(data)
    #                     max_idle = timeout  # reset idle timer on activity
    #                 except Exception:
    #                     return
    #         else:
    #             # no activity, decrement idle timer and break if exceeded
    #             max_idle -= 1
    #             if max_idle <= 0:
    #                 return


if __name__ == "__main__":
    # Create a session before starting the server
    # give FlareSolverr a bit of time to come up if running alongside
    time.sleep(15)
    SESSION_ID = create_session()

    server_address = ("", 8080)
    httpd = HTTPServer(server_address, ProxyHTTPRequestHandler)
    print("FlareProxy adapter running on port 8080")
    httpd.serve_forever()

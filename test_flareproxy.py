import io
import unittest
from unittest.mock import MagicMock, patch

from flareproxy import ProxyHTTPRequestHandler


class DummyHandler:
    def __init__(self, path):
        self.path = path
        self.wfile = io.BytesIO()
        self.response_code = None
        self.headers = {}
        self.end_headers_called = False
        self._get_target_url = ProxyHTTPRequestHandler._get_target_url
        self._should_use_flaresolverr = ProxyHTTPRequestHandler._should_use_flaresolverr

    def send_response(self, code, *_):
        self.response_code = code

    def send_header(self, key, value):
        self.headers[key] = value

    def end_headers(self):
        self.end_headers_called = True


class ProxyHandlerTests(unittest.TestCase):
    @patch("flareproxy.requests.post")
    @patch("flareproxy.requests.get")
    def test_handle_request_uses_flare_proxy_for_html_only(self, mock_get, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "solution": {"response": "<html>hello</html>"}
        }
        handler = DummyHandler("http://example.com/index.html")

        ProxyHTTPRequestHandler.handle_request(handler)

        mock_post.assert_called_once()
        mock_get.assert_not_called()
        self.assertEqual(handler.response_code, 200)
        self.assertIn(b"<html>hello</html>", handler.wfile.getvalue())

    @patch("flareproxy.requests.post")
    @patch("flareproxy.requests.get")
    def test_handle_request_bypasses_flare_proxy_for_non_html(self, mock_get, mock_post):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b'{"ok": true}'
        mock_get.return_value.headers = {"Content-Type": "application/json"}
        handler = DummyHandler("http://example.com/api/status")

        ProxyHTTPRequestHandler.handle_request(handler)

        mock_get.assert_called_once_with("https://example.com/api/status", timeout=60)
        mock_post.assert_not_called()
        self.assertEqual(handler.response_code, 200)
        self.assertEqual(handler.headers["Content-Type"], "application/json")
        self.assertEqual(handler.wfile.getvalue(), b'{"ok": true}')

    @patch("flareproxy.socket.create_connection")
    def test_do_connect_creates_tunnel(self, mock_create_connection):
        upstream_socket = MagicMock()
        connection_context = MagicMock()
        connection_context.__enter__.return_value = upstream_socket
        connection_context.__exit__.return_value = False
        mock_create_connection.return_value = connection_context

        handler = DummyHandler("example.com:443")
        handler._tunnel_connection = MagicMock()
        handler.handle_request = MagicMock(side_effect=AssertionError("should not be called"))
        handler.wfile = io.BytesIO()

        ProxyHTTPRequestHandler.do_CONNECT(handler)

        mock_create_connection.assert_called_once_with(("example.com", 443))
        handler._tunnel_connection.assert_called_once_with(upstream_socket)
        handler.handle_request.assert_not_called()
        self.assertEqual(handler.response_code, 200)


if __name__ == "__main__":
    unittest.main()

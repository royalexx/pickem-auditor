import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from v2.nba_architecture.p1_capture_v1 import capture


class CaptureTests(unittest.TestCase):
    def test_http_denial_body_and_create_only(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(403); self.end_headers(); self.wfile.write(b'not available')
            def log_message(self, *args):
                pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with TemporaryDirectory() as tmp:
                dest=Path(tmp)/'capture';url='http://127.0.0.1:'+str(server.server_port)
                result=capture(url,dest)
                self.assertEqual(result['status'],403)
                self.assertEqual((dest/'body.raw').read_bytes(),b'not available')
                self.assertIsNone(result['source_published_at'])
                with self.assertRaises(FileExistsError):capture(url,dest)
        finally:
            server.shutdown();server.server_close();thread.join()

import http.server
import socketserver
import os

PORT = 8000
DIRECTORY = r"D:\Python Battery Simulation Model"
os.chdir(DIRECTORY)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    with ThreadingTCPServer(('', PORT), Handler) as httpd:
        print(f"Serving HTTP on 0.0.0.0:{PORT} (accessible at http://localhost:{PORT} and http://127.0.0.1:{PORT})...")
        httpd.serve_forever()

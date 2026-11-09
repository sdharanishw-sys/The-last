import socket
import base64
import os
import struct
import json
import urllib.parse

class SimpleWebSocket:
    def __init__(self, ws_url):
        parsed = urllib.parse.urlparse(ws_url)
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.path = parsed.path
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        self._handshake()

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode('utf-8'))
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed during WebSocket handshake")
            resp += chunk
        if b"101 " not in resp:
            raise ConnectionError(f"Handshake failed: {resp.decode('latin1', errors='replace')}")

    def send_json(self, obj):
        payload = json.dumps(obj).encode('utf-8')
        length = len(payload)
        header = bytearray([0x81]) # text frame, fin=1
        mask_key = os.urandom(4)
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack('>H', length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack('>Q', length))
        header.extend(mask_key)
        masked_payload = bytearray(payload[i] ^ mask_key[i % 4] for i in range(length))
        self.sock.sendall(header + masked_payload)

    def recv_json(self, timeout=5):
        self.sock.settimeout(timeout)
        data = self.sock.recv(2)
        if not data or len(data) < 2:
            return None
        b1, b2 = data[0], data[1]
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack('>H', self.sock.recv(2))[0]
        elif length == 127:
            length = struct.unpack('>Q', self.sock.recv(8))[0]
        
        is_masked = bool(b2 & 0x80)
        mask = self.sock.recv(4) if is_masked else None
        
        payload = bytearray()
        while len(payload) < length:
            chunk = self.sock.recv(length - len(payload))
            if not chunk:
                break
            payload.extend(chunk)
            
        if is_masked:
            payload = bytearray(payload[i] ^ mask[i % 4] for i in range(len(payload)))
            
        return json.loads(payload.decode('utf-8'))

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

print("SimpleWebSocket defined successfully!")

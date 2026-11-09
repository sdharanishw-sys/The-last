import subprocess
import time
import json
import urllib.request
import base64
import websocket

# Launch Chrome headless with remote debugging port
chrome_cmd = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--remote-debugging-port=9222",
    "--disable-gpu",
    "--no-sandbox",
    "--window-size=1400,1200",
    "http://127.0.0.1:8000/"
]

proc = subprocess.Popen(chrome_cmd)
time.sleep(2.5)

try:
    # Query targets
    req = urllib.request.urlopen("http://127.0.0.1:9222/json")
    targets = json.loads(req.read().decode())
    target = next(t for t in targets if t.get("type") == "page")
    ws_url = target["webSocketDebuggerUrl"]

    ws = websocket.create_connection(ws_url)

    # Enable console and runtime
    ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
    ws.send(json.dumps({"id": 2, "method": "Console.enable"}))
    ws.send(json.dumps({"id": 3, "method": "Page.enable"}))

    # Wait 3 seconds so the wave animation advances and streams forward
    time.sleep(3.5)

    # Check for errors in evaluate
    ws.send(json.dumps({
        "id": 4,
        "method": "Runtime.evaluate",
        "params": {
            "expression": "JSON.stringify({time: document.getElementById('p4_stream_time')?.textContent, v: document.getElementById('p4_kpi-v')?.textContent, i: document.getElementById('p4_kpi-i')?.textContent, battTime: document.getElementById('batt_stream_time')?.textContent})"
        }
    }))
    res = ws.recv()
    print("Eval response:", res)

    # Take screenshot
    ws.send(json.dumps({
        "id": 5,
        "method": "Page.captureScreenshot",
        "params": {"format": "png"}
    }))

    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == 5:
            data = base64.b64decode(resp["result"]["data"])
            shot_path = r"C:\Users\dhara\.gemini\antigravity\brain\4f32b166-0c78-487d-b6bf-bbbea4bbf5a4\screenshot_live_waves.png"
            with open(shot_path, "wb") as f:
                f.write(data)
            print("Saved screenshot to:", shot_path)
            break

    ws.close()
finally:
    proc.terminate()

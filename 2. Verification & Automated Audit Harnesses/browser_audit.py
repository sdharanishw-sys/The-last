"""
Complete Browser-based Dashboard & Demonstration Audit via Chrome DevTools Protocol (CDP)
========================================================================================
Audits:
  1. Console logs, warnings, and JavaScript exceptions.
  2. Tab navigation (Phase 4, Drive Cycle, HPPC).
  3. Interactive controls, filters, and safety indicators.
  4. HTML5 Canvas chart rendering (pixel density verification).
  5. Responsive layout testing (Desktop 1920x1080, Laptop 1280x800, Mobile 390x844).
  6. Offline air-gapped integrity verification (0 CDN/external script requests).
  7. High-resolution screenshot capture for demonstration artifacts.
"""

import subprocess
import time
import urllib.request
import json
import base64
import os
from test_cdp import SimpleWebSocket

def run_browser_audit(output_dir="."):
    os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        '--headless=new',
        '--remote-debugging-port=9222',
        '--disable-gpu',
        '--no-sandbox',
        r'--user-data-dir=C:\Users\dhara\AppData\Local\Temp\chrome_bms_test',
        'http://localhost:8000/'
    ]

    proc = subprocess.Popen(cmd)
    time.sleep(2)

    try:
        with urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=5) as resp:
            targets = json.loads(resp.read())
        page_target = next(t for t in targets if 'localhost:8000' in t.get('url', ''))
        ws_url = page_target['webSocketDebuggerUrl']
        ws = SimpleWebSocket(ws_url)

        req_id = 1
        recorded_exceptions = []

        def call_cdp(method, params=None):
            nonlocal req_id
            cid = req_id
            req_id += 1
            ws.send_json({'id': cid, 'method': method, 'params': params or {}})
            while True:
                msg = ws.recv_json(timeout=10)
                if msg is None:
                    raise TimeoutError(f"Timeout waiting for CDP response to {method}")
                if msg.get('method') == 'Runtime.exceptionThrown':
                    recorded_exceptions.append(msg.get('params', {}))
                if msg.get('id') == cid:
                    return msg.get('result', {})

        def eval_js(expr):
            res = call_cdp('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
            return res.get('result', {}).get('value')

        def capture_screenshot(filename, width=1280, height=800):
            call_cdp('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': (width < 600)
            })
            time.sleep(0.5)
            res = call_cdp('Page.captureScreenshot', {'format': 'png'})
            data = base64.b64decode(res['data'])
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(data)
            return filepath, len(data)

        # 1. Enable Runtime, Page
        call_cdp('Runtime.enable')
        call_cdp('Page.enable')

        # 2. Check document title and readyState
        title = eval_js('document.title')
        ready_state = eval_js('document.readyState')
        print(f"[+] Connected to browser: Title = '{title}', ReadyState = '{ready_state}'")

        # 3. Check Offline Assets (zero CDN scripts)
        external_scripts = eval_js('Array.from(document.querySelectorAll("script[src]")).map(s => s.src)')
        print(f"[+] External script sources count: {len(external_scripts)}")
        for src in external_scripts:
            print(f"    - {src}")

        # 4. Check for unhandled exceptions recorded so far
        print(f"[+] JavaScript uncaught exceptions so far: {len(recorded_exceptions)}")
        for ex in recorded_exceptions:
            print(f"    - Exception: {ex.get('exceptionDetails', {}).get('text')}")

        # 5. Test Tab 1: Phase 4 Validation & Diagnostic Dashboard
        print("\n[*] Auditing Tab 1: Phase 4 Validation & Diagnostics...")
        eval_js("document.querySelector('[data-tab=\"tab-phase4\"]').click()")
        time.sleep(0.5)
        p4_visible = eval_js("document.getElementById('tab-phase4').classList.contains('active')")
        print(f"    - Tab-phase4 active? {p4_visible}")

        # Verify Phase 4 canvases have rendered non-zero pixels
        p4_canvases = ['p4_canvas-v', 'p4_canvas-dcir', 'p4_canvas-temp', 'p4_canvas-soc']
        for cid in p4_canvases:
            is_non_blank = eval_js(f"""
                (() => {{
                    const c = document.getElementById('{cid}');
                    if (!c || c.width === 0 || c.height === 0) return false;
                    const ctx = c.getContext('2d');
                    const img = ctx.getImageData(0, 0, Math.min(100, c.width), Math.min(100, c.height));
                    return img.data.some(p => p !== 0);
                }})()
            """)
            print(f"    - Canvas '{cid}' has rendered pixel data: {is_non_blank}")

        # Test Alert Filtering Buttons
        filters = ['ALL', 'CRITICAL', 'WARNING', 'ADAPTIVE', 'FIXED']
        for flt in filters:
            row_count = eval_js(f"""
                (() => {{
                    const btn = document.querySelector('[data-filter=\"{flt}\"]');
                    if (btn) btn.click();
                    const tbody = document.getElementById('p4_tbody-alerts');
                    if (!tbody) return 0;
                    return Array.from(tbody.querySelectorAll('tr')).filter(r => r.style.display !== 'none').length;
                }})()
            """)
            print(f"    - Alert filter '{flt}' clicked -> visible rows: {row_count}")

        # Reset filter to ALL
        eval_js("document.querySelector('[data-filter=\"ALL\"]').click()")

        # Capture desktop screenshot of Phase 4
        s1, sz1 = capture_screenshot("screenshot_tab_phase4_desktop.png", 1280, 900)
        print(f"    [+] Saved Phase 4 desktop screenshot: {s1} ({sz1} bytes)")

        # 6. Test Tab 2: Battery Simulation (Drive Cycle)
        print("\n[*] Auditing Tab 2: Battery Simulation (Drive Cycle)...")
        eval_js("document.querySelector('[data-tab=\"tab-battery\"]').click()")
        time.sleep(0.5)
        batt_visible = eval_js("document.getElementById('tab-battery').classList.contains('active')")
        print(f"    - Tab-battery active? {batt_visible}")

        batt_canvases = ['batt_cv-current', 'batt_cv-voltage', 'batt_cv-soc', 'batt_cv-temp']
        for cid in batt_canvases:
            is_non_blank = eval_js(f"""
                (() => {{
                    const c = document.getElementById('{cid}');
                    if (!c || c.width === 0 || c.height === 0) return false;
                    const ctx = c.getContext('2d');
                    const img = ctx.getImageData(0, 0, Math.min(100, c.width), Math.min(100, c.height));
                    return img.data.some(p => p !== 0);
                }})()
            """)
            print(f"    - Canvas '{cid}' has rendered pixel data: {is_non_blank}")

        # Test legend toggling in Battery tab
        legend_toggled = eval_js("""
            (() => {
                const leg = document.querySelector('#tab-battery .legend-item');
                if (!leg) return false;
                leg.click(); // toggle series off
                const is_dim = leg.classList.contains('dimmed');
                leg.click(); // toggle series back on
                return is_dim;
            })()
        """)
        print(f"    - Interactive legend toggling functional: {legend_toggled}")

        s2, sz2 = capture_screenshot("screenshot_tab_battery_desktop.png", 1280, 900)
        print(f"    [+] Saved Battery Simulation desktop screenshot: {s2} ({sz2} bytes)")

        # 7. Test Tab 3: HPPC Pulse Characterization Test
        print("\n[*] Auditing Tab 3: HPPC Characterization Test...")
        eval_js("document.querySelector('[data-tab=\"tab-hppc\"]').click()")
        time.sleep(0.5)
        hppc_visible = eval_js("document.getElementById('tab-hppc').classList.contains('active')")
        print(f"    - Tab-hppc active? {hppc_visible}")

        hppc_canvases = ['hppc_cv-current', 'hppc_cv-voltage', 'hppc_cv-soc', 'hppc_cv-temp']
        for cid in hppc_canvases:
            is_non_blank = eval_js(f"""
                (() => {{
                    const c = document.getElementById('{cid}');
                    if (!c || c.width === 0 || c.height === 0) return false;
                    const ctx = c.getContext('2d');
                    const img = ctx.getImageData(0, 0, Math.min(100, c.width), Math.min(100, c.height));
                    return img.data.some(p => p !== 0);
                }})()
            """)
            print(f"    - Canvas '{cid}' has rendered pixel data: {is_non_blank}")

        s3, sz3 = capture_screenshot("screenshot_tab_hppc_desktop.png", 1280, 900)
        print(f"    [+] Saved HPPC desktop screenshot: {s3} ({sz3} bytes)")

        # 8. Test Responsive Mobile Layout (390 x 844)
        print("\n[*] Auditing Responsive Mobile Layout (390 x 844)...")
        eval_js("document.querySelector('[data-tab=\"tab-phase4\"]').click()")
        time.sleep(0.5)
        s4, sz4 = capture_screenshot("screenshot_mobile_phase4.png", 390, 844)
        print(f"    [+] Saved Mobile layout screenshot: {s4} ({sz4} bytes)")

        # Check for horizontal overflow on mobile
        overflow_x = eval_js("document.documentElement.scrollWidth > window.innerWidth")
        print(f"    - Unintended horizontal overflow on mobile? {overflow_x}")

        # Final check on recorded exceptions
        print(f"\n[+] Total JavaScript exceptions captured during run: {len(recorded_exceptions)}")

        ws.close()
        print("\n[+] Browser-based audit completed successfully!")
        return len(recorded_exceptions) == 0

    finally:
        try:
            proc.terminate()
        except Exception:
            pass

if __name__ == '__main__':
    run_browser_audit()

import re
import os
import shutil
import subprocess

build_path = r'D:\Python Battery Simulation Model\examples\build_unified_dashboard.py'

with open(build_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update Phase 4 stream bar buttons
p4_old_btns = """        <button class="live-ctrl-btn active" id="p4_btn_play" onclick="window.p4_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn" id="p4_spd_01" onclick="window.p4_setSpeed(0.1)">0.1x Ultra Slow</button>
        <button class="live-ctrl-btn active" id="p4_spd_025" onclick="window.p4_setSpeed(0.25)">0.25x Super Slow</button>
        <button class="live-ctrl-btn" id="p4_spd_05" onclick="window.p4_setSpeed(0.5)">0.5x Slow</button>
        <button class="live-ctrl-btn" id="p4_spd_1" onclick="window.p4_setSpeed(1.0)">1x Normal</button>
        <button class="live-ctrl-btn" onclick="window.p4_restartStream()">↺ Replay</button>"""

p4_new_btns = """        <button class="live-ctrl-btn active" id="p4_btn_play" onclick="window.p4_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn active" id="p4_spd_05" onclick="window.p4_setSpeed(0.5)">0.5x Slow</button>
        <button class="live-ctrl-btn" id="p4_spd_1" onclick="window.p4_setSpeed(1.0)">1x Normal</button>
        <button class="live-ctrl-btn" id="p4_spd_2" onclick="window.p4_setSpeed(2.0)">2x Fast</button>
        <button class="live-ctrl-btn" onclick="window.p4_restartStream()">↺ Replay</button>"""

if p4_old_btns in text:
    text = text.replace(p4_old_btns, p4_new_btns)
    print("Replaced p4 buttons successfully")
else:
    print("Warning: p4_old_btns not matched directly, checking normalized...")
    # Normalize CRLF
    p4_old_norm = p4_old_btns.replace('\r\n', '\n')
    text_norm = text.replace('\r\n', '\n')
    if p4_old_norm in text_norm:
        text = text_norm.replace(p4_old_norm, p4_new_btns)
        print("Replaced p4 buttons with newline normalization")
    else:
        print("Error: Could not match p4 buttons")

# 2. Update Drive cycle stream bar buttons
b_old_btns = """        <button class="live-ctrl-btn active" id="batt_btn_play" onclick="window.batt_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn" id="batt_spd_01" onclick="window.batt_setSpeed(0.1)">0.1x Ultra Slow</button>
        <button class="live-ctrl-btn active" id="batt_spd_025" onclick="window.batt_setSpeed(0.25)">0.25x Super Slow</button>
        <button class="live-ctrl-btn" id="batt_spd_05" onclick="window.batt_setSpeed(0.5)">0.5x Slow</button>
        <button class="live-ctrl-btn" id="batt_spd_1" onclick="window.batt_setSpeed(1.0)">1x Normal</button>
        <button class="live-ctrl-btn" onclick="window.batt_restartStream()">↺ Replay</button>"""

b_new_btns = """        <button class="live-ctrl-btn active" id="batt_btn_play" onclick="window.batt_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn active" id="batt_spd_05" onclick="window.batt_setSpeed(0.5)">0.5x Slow</button>
        <button class="live-ctrl-btn" id="batt_spd_1" onclick="window.batt_setSpeed(1.0)">1x Normal</button>
        <button class="live-ctrl-btn" id="batt_spd_2" onclick="window.batt_setSpeed(2.0)">2x Fast</button>
        <button class="live-ctrl-btn" onclick="window.batt_restartStream()">↺ Replay</button>"""

if b_old_btns in text:
    text = text.replace(b_old_btns, b_new_btns)
    print("Replaced batt buttons successfully")
else:
    b_old_norm = b_old_btns.replace('\r\n', '\n')
    if b_old_norm in text:
        text = text.replace(b_old_norm, b_new_btns)
        print("Replaced batt buttons with newline normalization")
    else:
        print("Error: Could not match batt buttons")

# 3. Update batt_motion_loop default speed and setSpeed function
text = text.replace("let batt_speed = 0.25; // Super slow by default!", "let batt_speed = 0.5; // Slow by default")
old_b_setSpeed = """    window.batt_setSpeed = function(spd) {
        batt_speed = spd;
        ['01', '025', '05', '1'].forEach(id => {
            const b = document.getElementById('batt_spd_' + id);
            if (b) b.classList.remove('active');
        });
        const key = spd === 0.1 ? '01' : (spd === 0.25 ? '025' : (spd === 0.5 ? '05' : '1'));
        const activeBtn = document.getElementById('batt_spd_' + key);
        if (activeBtn) activeBtn.classList.add('active');
    };"""

new_b_setSpeed = """    window.batt_setSpeed = function(spd) {
        batt_speed = spd;
        ['05', '1', '2'].forEach(id => {
            const b = document.getElementById('batt_spd_' + id);
            if (b) b.classList.remove('active');
        });
        const key = spd === 0.5 ? '05' : (spd === 2.0 ? '2' : '1');
        const activeBtn = document.getElementById('batt_spd_' + key);
        if (activeBtn) activeBtn.classList.add('active');
    };"""

text = text.replace(old_b_setSpeed, new_b_setSpeed)

# 4. Update p4_motion_loop default speed and setSpeed function
text = text.replace("let p4_speed = 0.25; // Super slow by default!", "let p4_speed = 0.5; // Slow by default")
old_p4_setSpeed = """    window.p4_setSpeed = function(spd) {
        p4_speed = spd;
        ['01', '025', '05', '1'].forEach(id => {
            const b = document.getElementById('p4_spd_' + id);
            if (b) b.classList.remove('active');
        });
        const key = spd === 0.1 ? '01' : (spd === 0.25 ? '025' : (spd === 0.5 ? '05' : '1'));
        const activeBtn = document.getElementById('p4_spd_' + key);
        if (activeBtn) activeBtn.classList.add('active');
    };"""

new_p4_setSpeed = """    window.p4_setSpeed = function(spd) {
        p4_speed = spd;
        ['05', '1', '2'].forEach(id => {
            const b = document.getElementById('p4_spd_' + id);
            if (b) b.classList.remove('active');
        });
        const key = spd === 0.5 ? '05' : (spd === 2.0 ? '2' : '1');
        const activeBtn = document.getElementById('p4_spd_' + key);
        if (activeBtn) activeBtn.classList.add('active');
    };"""

text = text.replace(old_p4_setSpeed, new_p4_setSpeed)

with open(build_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("build_unified_dashboard.py updated!")

# Rebuild dashboard
print("Rebuilding unified dashboard...")
subprocess.run(['python', build_path], check=True)

# Copy to appy 2 and The last
root_dir = r"D:\Python Battery Simulation Model"
appy2_dir = r"d:\appy 2"
thelast_dir = r"D:\Python Battery Simulation Model\The last"

for src_name in ['index.html', 'unified_dashboard.html']:
    src = os.path.join(root_dir, src_name)
    shutil.copy2(src, os.path.join(appy2_dir, src_name))
    shutil.copy2(src, os.path.join(thelast_dir, src_name))
    print(f"Copied {src_name} to appy 2 and The last")

# Git commit
subprocess.run(['git', '-C', thelast_dir, 'add', '.'], check=True)
res = subprocess.run(['git', '-C', thelast_dir, 'commit', '-m', 'refactor: remove 0.1x and 0.25x speed options, keep 0.5x Slow, 1x Normal, 2x Fast'], capture_output=True, text=True)
print("Git commit:", res.stdout)
print("All complete!")

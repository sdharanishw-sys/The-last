import re
import os

build_path = r'D:\Python Battery Simulation Model\examples\build_unified_dashboard.py'

with open(build_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update static label in p_stream_bar & b_stream_bar
text = text.replace('id="p4_stream_time">t = 0.0s / 209.0s</span>', 'id="p4_stream_time">t = 0.0s / 3600.0s (1.0 hr)</span>')
text = text.replace('id="batt_stream_time">t = 0.0s / 600.0s</span>', 'id="batt_stream_time">t = 0.0s / 3600.0s (1.0 hr)</span>')

# 2. Update p4_updateLiveKPIs time formatting
old_p4_time = """        const timeEl = document.getElementById('p4_stream_time');
        if (timeEl) timeEl.textContent = 't = ' + curT.toFixed(1) + 's / ' + maxT.toFixed(1) + 's';"""

new_p4_time = """        const timeEl = document.getElementById('p4_stream_time');
        if (timeEl) {
            const mins = Math.floor(curT / 60);
            const secs = Math.floor(curT % 60);
            timeEl.textContent = 't = ' + curT.toFixed(0) + 's (' + mins + 'm ' + (secs < 10 ? '0' : '') + secs + 's) / 3600s (1.0 hr)';
        }"""

text = text.replace(old_p4_time, new_p4_time)

# 3. Update batt_updateLiveStatus time formatting & step
old_batt_time = """        const timeEl = document.getElementById('batt_stream_time');
        if (timeEl) timeEl.textContent = 't = ' + curT.toFixed(1) + 's / ' + maxT.toFixed(1) + 's';"""

new_batt_time = """        const timeEl = document.getElementById('batt_stream_time');
        if (timeEl) {
            const mins = Math.floor(curT / 60);
            const secs = Math.floor(curT % 60);
            timeEl.textContent = 't = ' + curT.toFixed(0) + 's (' + mins + 'm ' + (secs < 10 ? '0' : '') + secs + 's) / 3600s (1.0 hr)';
        }"""

text = text.replace(old_batt_time, new_batt_time)
text = text.replace('batt_liveAnimIndex += 2;', 'batt_liveAnimIndex += 3;')

# 4. Update tune_chart_colors to format ticks as 0s, 12m, 24m...
if 'tickLbl' not in text:
    old_tune = "    script = script.replace(\"ctx.strokeStyle = '#f8fafc'\", \"ctx.strokeStyle = '#332e29'\")\n    return script"
    new_tune = """    script = script.replace("ctx.strokeStyle = '#f8fafc'", "ctx.strokeStyle = '#332e29'")
    script = script.replace("ctx.fillText(t + 's', x, h - 10);", "const tickLbl = (t >= 60) ? (t / 60).toFixed(0) + 'm' : t + 's'; ctx.fillText(tickLbl, x, h - 10);")
    return script"""
    text = text.replace(old_tune, new_tune)

with open(build_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated build_unified_dashboard.py for 1-hour timing!")

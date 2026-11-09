import re
import os

build_script_path = r'D:\Python Battery Simulation Model\examples\build_unified_dashboard.py'

with open(build_script_path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add CSS for live-stream-bar
css_addition = """
        /* ── Live Stream Telemetry Bar ─────────────────────────────── */
        .live-stream-bar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            background: #ffffff;
            border: 1px solid var(--border-dim);
            border-radius: 14px;
            padding: 12px 20px;
            margin: 16px 0 20px 0;
            box-shadow: 0 2px 8px rgba(80, 65, 45, 0.04);
        }
        .live-stream-status {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 13px;
            color: var(--text-main);
        }
        .live-pulse-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #16a34a;
            box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.7);
            animation: livePulseAnim 1.8s infinite;
            display: inline-block;
        }
        @keyframes livePulseAnim {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(22, 163, 74, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }
        }
        .live-title {
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.06em;
            color: #16a34a;
            text-transform: uppercase;
        }
        .live-step-label {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-dim);
            background: #f4eee2;
            padding: 3px 10px;
            border-radius: 6px;
            border: 1px solid #e8ded0;
        }
        .live-progress-track {
            width: 140px;
            height: 6px;
            background: #ebdccb;
            border-radius: 999px;
            overflow: hidden;
        }
        .live-progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #16a34a, #0284c7);
            border-radius: 999px;
            transition: width 0.05s ease;
        }
        .live-stream-controls {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .live-ctrl-btn {
            background: #fdfbf7;
            border: 1px solid #e8ded0;
            color: #4a4239;
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .live-ctrl-btn:hover {
            background: #f4eee2;
            border-color: #dbcebc;
            color: #221e1b;
        }
        .live-ctrl-btn.active {
            background: #16a34a;
            border-color: #16a34a;
            color: #ffffff;
            box-shadow: 0 2px 6px rgba(22, 163, 74, 0.25);
        }
"""

if '.live-stream-bar' not in code:
    code = code.replace(
        '/* ── Inject Scoped Sub-Dashboard Styles ──────────────────────── */',
        css_addition + '\n        /* ── Inject Scoped Sub-Dashboard Styles ──────────────────────── */'
    )

# 2. Add Live Stream Bar HTML into p_body & b_body
p_stream_html = """
p_stream_bar = \"\"\"
<div class="live-stream-bar">
    <div class="live-stream-status">
        <span class="live-pulse-dot"></span>
        <strong class="live-title">LIVE TELEMETRY STREAM</strong>
        <span class="live-step-label" id="p4_stream_time">t = 0.0s / 209.0s</span>
        <div class="live-progress-track">
            <div class="live-progress-bar" id="p4_stream_bar" style="width: 0%;"></div>
        </div>
    </div>
    <div class="live-stream-controls">
        <button class="live-ctrl-btn active" id="p4_btn_play" onclick="window.p4_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn" id="p4_spd_1" onclick="window.p4_setSpeed(1)">1x</button>
        <button class="live-ctrl-btn active" id="p4_spd_2" onclick="window.p4_setSpeed(2)">2x</button>
        <button class="live-ctrl-btn" id="p4_spd_5" onclick="window.p4_setSpeed(5)">5x</button>
        <button class="live-ctrl-btn" onclick="window.p4_restartStream()">↺ Replay</button>
    </div>
</div>
\"\"\"
p_body = p_body.replace('<div class="kpi-grid">', p_stream_bar + '\\n<div class="kpi-grid">', 1)

b_stream_bar = \"\"\"
<div class="live-stream-bar">
    <div class="live-stream-status">
        <span class="live-pulse-dot"></span>
        <strong class="live-title">DRIVE CYCLE WAVE STREAM</strong>
        <span class="live-step-label" id="batt_stream_time">t = 0.0s / 600.0s</span>
        <div class="live-progress-track">
            <div class="live-progress-bar" id="batt_stream_bar" style="width: 0%;"></div>
        </div>
    </div>
    <div class="live-stream-controls">
        <button class="live-ctrl-btn active" id="batt_btn_play" onclick="window.batt_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn" id="batt_spd_1" onclick="window.batt_setSpeed(1)">1x</button>
        <button class="live-ctrl-btn active" id="batt_spd_2" onclick="window.batt_setSpeed(2)">2x</button>
        <button class="live-ctrl-btn" id="batt_spd_5" onclick="window.batt_setSpeed(5)">5x</button>
        <button class="live-ctrl-btn" onclick="window.batt_restartStream()">↺ Replay</button>
    </div>
</div>
\"\"\"
b_body = re.sub(r'(<div\s+class="chart-card">)', b_stream_bar + r'\\n\\1', b_body, count=1)
"""

if 'p_stream_bar =' not in code:
    code = code.replace(
        "p_body = re.sub(r'<div id=\"p4_tooltip\"[^>]*>.*?</div>', '', p_body, flags=re.DOTALL)",
        "p_body = re.sub(r'<div id=\"p4_tooltip\"[^>]*>.*?</div>', '', p_body, flags=re.DOTALL)\n" + p_stream_html
    )

# 3. Add wave motion engine into p_clean
p_wave_engine = """
# Replace static curve drawing with live wave streaming motion in Phase 4
p_old_draw = '''        // Draw curves
        visibleSeries.forEach(s => {
            ctx.strokeStyle = s.color;
            ctx.lineWidth = s.width || 1.8;
            ctx.setLineDash(s.dash || []);
            ctx.beginPath();
            for (let i = 0; i < n; i++) {
                const x = padL + i * xStep;
                const y = getY(s.data[i]);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
        });'''

p_new_draw = '''        // 1. Ghost baseline trajectory (faint translucent curve)
        visibleSeries.forEach(s => {
            ctx.strokeStyle = s.color;
            ctx.globalAlpha = 0.22;
            ctx.lineWidth = 1.3;
            ctx.setLineDash(s.dash || [3, 3]);
            ctx.beginPath();
            for (let i = 0; i < n; i++) {
                const x = padL + i * xStep;
                const y = getY(s.data[i]);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.globalAlpha = 1.0;
        });

        // 2. Active moving waveform (streaming forward up to liveAnimIndex)
        const curStep = Math.min(n - 1, Math.max(1, p4_liveAnimIndex));
        visibleSeries.forEach(s => {
            ctx.strokeStyle = s.color;
            ctx.lineWidth = (s.width || 2.0) + 0.6;
            ctx.setLineDash(s.dash || []);
            ctx.beginPath();
            for (let i = 0; i <= curStep; i++) {
                const x = padL + i * xStep;
                const y = getY(s.data[i]);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.setLineDash([]);
        });

        // 3. Leading edge scanline & pulsing beacon head dot
        const leadX = padL + curStep * xStep;
        ctx.strokeStyle = 'rgba(2, 132, 199, 0.45)';
        ctx.lineWidth = 1.2;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(leadX, padT);
        ctx.lineTo(leadX, h - padB);
        ctx.stroke();
        ctx.setLineDash([]);

        const pulsePhase = (Date.now() / 180) % (Math.PI * 2);
        const pulseR = 4.2 + Math.sin(pulsePhase) * 1.5;
        visibleSeries.forEach(s => {
            const leadY = getY(s.data[curStep]);
            ctx.fillStyle = s.color;
            ctx.globalAlpha = 0.28;
            ctx.beginPath();
            ctx.arc(leadX, leadY, pulseR + 4, 0, Math.PI * 2);
            ctx.fill();

            ctx.globalAlpha = 1.0;
            ctx.beginPath();
            ctx.arc(leadX, leadY, pulseR, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(leadX, leadY, 1.8, 0, Math.PI * 2);
            ctx.fill();
        });'''

p_clean = p_clean.replace(p_old_draw, p_new_draw)

p_motion_loop = '''
    // ── Live Wave Motion Streaming Engine & KPI Updates ─────────
    let p4_liveAnimIndex = 0;
    let p4_isPlaying = true;
    let p4_speed = 2;
    let p4_lastFrameTime = 0;

    function p4_updateLiveKPIs(idx) {
        if (typeof DATA === 'undefined' || !DATA || !DATA.charts) return;
        const total = DATA.charts.times.length;
        const curT = DATA.charts.times[idx] || 0;
        const maxT = DATA.charts.times[total - 1] || 209;

        const timeEl = document.getElementById('p4_stream_time');
        if (timeEl) timeEl.textContent = 't = ' + curT.toFixed(1) + 's / ' + maxT.toFixed(1) + 's';
        const barEl = document.getElementById('p4_stream_bar');
        if (barEl) barEl.style.width = ((idx / (total - 1)) * 100).toFixed(1) + '%';

        const vEl = document.getElementById('p4_kpi-v');
        if (vEl && DATA.charts.v_meas) vEl.textContent = DATA.charts.v_meas[idx].toFixed(3);

        const iEl = document.getElementById('p4_kpi-i');
        const pEl = document.getElementById('p4_kpi-p');
        if (iEl && DATA.charts.current) {
            const curI = DATA.charts.current[idx];
            iEl.textContent = curI.toFixed(2);
            if (pEl && DATA.charts.v_meas) {
                pEl.textContent = Math.abs(curI * DATA.charts.v_meas[idx]).toFixed(1);
            }
        }

        const socEl = document.getElementById('p4_kpi-soc');
        if (socEl && DATA.charts.soc) socEl.textContent = DATA.charts.soc[idx].toFixed(1);

        const ahEl = document.getElementById('p4_kpi-ah');
        if (ahEl && DATA.charts.ah) ahEl.textContent = DATA.charts.ah[idx].toFixed(3);

        const tEl = document.getElementById('p4_kpi-t');
        if (tEl && DATA.charts.temp_cell) tEl.textContent = DATA.charts.temp_cell[idx].toFixed(1);

        const dcirEl = document.getElementById('p4_kpi-dcir');
        const dcirPredEl = document.getElementById('p4_kpi-dcir-ref');
        const dcirDriftEl = document.getElementById('p4_kpi-dcir-drift');
        if (dcirEl && DATA.charts.dcir_meas) {
            const m = DATA.charts.dcir_meas[idx];
            dcirEl.textContent = m.toFixed(1);
            if (DATA.charts.dcir_pred) {
                const pred = DATA.charts.dcir_pred[idx];
                if (dcirPredEl) dcirPredEl.textContent = pred.toFixed(1);
                if (dcirDriftEl) {
                    const drift = ((m - pred) / pred) * 100;
                    dcirDriftEl.textContent = (drift >= 0 ? '+' : '') + drift.toFixed(1);
                }
            }
        }

        const anomEl = document.getElementById('p4_kpi-anomaly');
        if (anomEl && DATA.charts.anomaly) anomEl.textContent = DATA.charts.anomaly[idx].toFixed(3);
    }

    function p4_animationLoop(timestamp) {
        if (p4_isPlaying) {
            if (!p4_lastFrameTime) p4_lastFrameTime = timestamp;
            const delta = timestamp - p4_lastFrameTime;
            const frameDelay = 60 / p4_speed;
            if (delta >= frameDelay) {
                p4_lastFrameTime = timestamp;
                p4_liveAnimIndex++;
                if (p4_liveAnimIndex >= DATA.charts.times.length) {
                    p4_liveAnimIndex = 0;
                }
                p4_updateLiveKPIs(p4_liveAnimIndex);
                if (typeof renderAllCharts === 'function') renderAllCharts();
            }
        }
        requestAnimationFrame(p4_animationLoop);
    }
    requestAnimationFrame(p4_animationLoop);

    window.p4_togglePlay = function() {
        p4_isPlaying = !p4_isPlaying;
        const btn = document.getElementById('p4_btn_play');
        if (btn) {
            btn.textContent = p4_isPlaying ? '⏸ Pause' : '▶ Play';
            if (p4_isPlaying) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    };

    window.p4_setSpeed = function(spd) {
        p4_speed = spd;
        [1, 2, 5].forEach(s => {
            const b = document.getElementById('p4_spd_' + s);
            if (b) {
                if (s === spd) b.classList.add('active');
                else b.classList.remove('active');
            }
        });
    };

    window.p4_restartStream = function() {
        p4_liveAnimIndex = 0;
        p4_isPlaying = true;
        const btn = document.getElementById('p4_btn_play');
        if (btn) {
            btn.textContent = '⏸ Pause';
            btn.classList.add('active');
        }
        p4_updateLiveKPIs(0);
        if (typeof renderAllCharts === 'function') renderAllCharts();
    };
'''
p_clean += p_motion_loop
"""

if 'p_wave_engine' not in code:
    code = code.replace(
        "p_wrapped = f\"\"\"",
        p_wave_engine + "\np_wrapped = f\"\"\""
    )

# 4. Add wave motion engine into b_clean
b_wave_engine = """
# Replace static curve drawing with live wave streaming motion in Battery Dashboard
b_old_draw = '''        // Draw curves
        cfg.series.filter(s => s.visible).forEach(s => {
            ctx.strokeStyle = s.color;
            ctx.lineWidth = 1.8;
            ctx.setLineDash(s.dash || []);
            ctx.beginPath();
            for (let i = 0; i < n; i++) {
                const x = padL + i * xStep;
                const y = getY(s.data[i]);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
        });'''

b_new_draw = '''        // 1. Ghost baseline envelope
        cfg.series.filter(s => s.visible).forEach(s => {
            ctx.strokeStyle = s.color;
            ctx.globalAlpha = 0.22;
            ctx.lineWidth = 1.3;
            ctx.setLineDash(s.dash || [3, 3]);
            ctx.beginPath();
            for (let i = 0; i < n; i++) {
                const x = padL + i * xStep;
                const y = getY(s.data[i]);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.globalAlpha = 1.0;
        });

        // 2. Active moving waveform
        const curStep = Math.min(n - 1, Math.max(1, batt_liveAnimIndex));
        cfg.series.filter(s => s.visible).forEach(s => {
            ctx.strokeStyle = s.color;
            ctx.lineWidth = 2.4;
            ctx.setLineDash(s.dash || []);
            ctx.beginPath();
            for (let i = 0; i <= curStep; i++) {
                const x = padL + i * xStep;
                const y = getY(s.data[i]);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.setLineDash([]);
        });

        // 3. Leading edge scanline & pulsing beacon head dot
        const leadX = padL + curStep * xStep;
        ctx.strokeStyle = 'rgba(22, 163, 74, 0.45)';
        ctx.lineWidth = 1.2;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(leadX, padT);
        ctx.lineTo(leadX, h - padB);
        ctx.stroke();
        ctx.setLineDash([]);

        const pulsePhase = (Date.now() / 180) % (Math.PI * 2);
        const pulseR = 4.2 + Math.sin(pulsePhase) * 1.5;
        cfg.series.filter(s => s.visible).forEach(s => {
            const leadY = getY(s.data[curStep]);
            ctx.fillStyle = s.color;
            ctx.globalAlpha = 0.28;
            ctx.beginPath();
            ctx.arc(leadX, leadY, pulseR + 4, 0, Math.PI * 2);
            ctx.fill();

            ctx.globalAlpha = 1.0;
            ctx.beginPath();
            ctx.arc(leadX, leadY, pulseR, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(leadX, leadY, 1.8, 0, Math.PI * 2);
            ctx.fill();
        });'''

b_clean = b_clean.replace(b_old_draw, b_new_draw)

b_motion_loop = '''
    // ── Live Drive Cycle Wave Motion Engine ───────────────────────
    let batt_liveAnimIndex = 0;
    let batt_isPlaying = true;
    let batt_speed = 2;
    let batt_lastFrameTime = 0;

    function batt_updateLiveStatus(idx) {
        if (typeof DATA === 'undefined' || !DATA || !DATA.times) return;
        const total = DATA.times.length;
        const curT = DATA.times[idx] || 0;
        const maxT = DATA.times[total - 1] || 600;

        const timeEl = document.getElementById('batt_stream_time');
        if (timeEl) timeEl.textContent = 't = ' + curT.toFixed(1) + 's / ' + maxT.toFixed(1) + 's';
        const barEl = document.getElementById('batt_stream_bar');
        if (barEl) barEl.style.width = ((idx / (total - 1)) * 100).toFixed(1) + '%';
    }

    function batt_animationLoop(timestamp) {
        if (batt_isPlaying) {
            if (!batt_lastFrameTime) batt_lastFrameTime = timestamp;
            const delta = timestamp - batt_lastFrameTime;
            const frameDelay = 50 / batt_speed;
            if (delta >= frameDelay) {
                batt_lastFrameTime = timestamp;
                batt_liveAnimIndex += 2;
                if (batt_liveAnimIndex >= DATA.times.length) {
                    batt_liveAnimIndex = 0;
                }
                batt_updateLiveStatus(batt_liveAnimIndex);
                if (typeof renderAll === 'function') renderAll();
            }
        }
        requestAnimationFrame(batt_animationLoop);
    }
    requestAnimationFrame(batt_animationLoop);

    window.batt_togglePlay = function() {
        batt_isPlaying = !batt_isPlaying;
        const btn = document.getElementById('batt_btn_play');
        if (btn) {
            btn.textContent = batt_isPlaying ? '⏸ Pause' : '▶ Play';
            if (batt_isPlaying) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    };

    window.batt_setSpeed = function(spd) {
        batt_speed = spd;
        [1, 2, 5].forEach(s => {
            const b = document.getElementById('batt_spd_' + s);
            if (b) {
                if (s === spd) b.classList.add('active');
                else b.classList.remove('active');
            }
        });
    };

    window.batt_restartStream = function() {
        batt_liveAnimIndex = 0;
        batt_isPlaying = true;
        const btn = document.getElementById('batt_btn_play');
        if (btn) {
            btn.textContent = '⏸ Pause';
            btn.classList.add('active');
        }
        batt_updateLiveStatus(0);
        if (typeof renderAll === 'function') renderAll();
    };
'''
b_clean += b_motion_loop
"""

if 'b_wave_engine' not in code:
    code = code.replace(
        "b_wrapped = f\"\"\"",
        b_wave_engine + "\nb_wrapped = f\"\"\""
    )

with open(build_script_path, 'w', encoding='utf-8') as f:
    f.write(code)

print("build_unified_dashboard.py updated successfully!")

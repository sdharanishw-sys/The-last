import re
import os

build_path = r'D:\Python Battery Simulation Model\examples\build_unified_dashboard.py'

with open(build_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update Phase 4 stream bar buttons to super slow options
old_p4_bar = """        <button class="live-ctrl-btn active" id="p4_btn_play" onclick="window.p4_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn" id="p4_spd_1" onclick="window.p4_setSpeed(1)">1x</button>
        <button class="live-ctrl-btn active" id="p4_spd_2" onclick="window.p4_setSpeed(2)">2x</button>
        <button class="live-ctrl-btn" id="p4_spd_5" onclick="window.p4_setSpeed(5)">5x</button>
        <button class="live-ctrl-btn" onclick="window.p4_restartStream()">↺ Replay</button>"""

new_p4_bar = """        <button class="live-ctrl-btn active" id="p4_btn_play" onclick="window.p4_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn" id="p4_spd_01" onclick="window.p4_setSpeed(0.1)">0.1x Ultra Slow</button>
        <button class="live-ctrl-btn active" id="p4_spd_025" onclick="window.p4_setSpeed(0.25)">0.25x Super Slow</button>
        <button class="live-ctrl-btn" id="p4_spd_05" onclick="window.p4_setSpeed(0.5)">0.5x Slow</button>
        <button class="live-ctrl-btn" id="p4_spd_1" onclick="window.p4_setSpeed(1.0)">1x Normal</button>
        <button class="live-ctrl-btn" onclick="window.p4_restartStream()">↺ Replay</button>"""

text = text.replace(old_p4_bar, new_p4_bar)

# 2. Update Battery Drive Cycle stream bar buttons
old_b_bar = """        <button class="live-ctrl-btn active" id="batt_btn_play" onclick="window.batt_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn" id="batt_spd_1" onclick="window.batt_setSpeed(1)">1x</button>
        <button class="live-ctrl-btn active" id="batt_spd_2" onclick="window.batt_setSpeed(2)">2x</button>
        <button class="live-ctrl-btn" id="batt_spd_5" onclick="window.batt_setSpeed(5)">5x</button>
        <button class="live-ctrl-btn" onclick="window.batt_restartStream()">↺ Replay</button>"""

new_b_bar = """        <button class="live-ctrl-btn active" id="batt_btn_play" onclick="window.batt_togglePlay()">⏸ Pause</button>
        <button class="live-ctrl-btn" id="batt_spd_01" onclick="window.batt_setSpeed(0.1)">0.1x Ultra Slow</button>
        <button class="live-ctrl-btn active" id="batt_spd_025" onclick="window.batt_setSpeed(0.25)">0.25x Super Slow</button>
        <button class="live-ctrl-btn" id="batt_spd_05" onclick="window.batt_setSpeed(0.5)">0.5x Slow</button>
        <button class="live-ctrl-btn" id="batt_spd_1" onclick="window.batt_setSpeed(1.0)">1x Normal</button>
        <button class="live-ctrl-btn" onclick="window.batt_restartStream()">↺ Replay</button>"""

text = text.replace(old_b_bar, new_b_bar)

# 3. Update b_new_draw to support floating-point sub-pixel interpolation
old_b_draw = """        // 2. Active moving waveform
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
        });"""

new_b_draw = """        // 2. Active moving waveform (smooth continuous sub-pixel trace)
        const curIdx = Math.min(n - 1, Math.max(0, batt_liveAnimIndex));
        const intIdx = Math.floor(curIdx);
        const frac = curIdx - intIdx;
        const leadX = padL + curIdx * xStep;

        cfg.series.filter(s => s.visible).forEach(s => {
            ctx.strokeStyle = s.color;
            ctx.lineWidth = 2.4;
            ctx.setLineDash(s.dash || []);
            ctx.beginPath();
            for (let i = 0; i <= intIdx; i++) {
                const x = padL + i * xStep;
                const y = getY(s.data[i]);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            if (intIdx + 1 < n && frac > 0.001) {
                const y0 = getY(s.data[intIdx]);
                const y1 = getY(s.data[intIdx + 1]);
                const leadY = y0 + (y1 - y0) * frac;
                ctx.lineTo(leadX, leadY);
            }
            ctx.stroke();
            ctx.setLineDash([]);
        });

        // 3. Leading edge scanline & pulsing beacon head dot
        ctx.strokeStyle = 'rgba(22, 163, 74, 0.40)';
        ctx.lineWidth = 1.2;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(leadX, padT);
        ctx.lineTo(leadX, h - padB);
        ctx.stroke();
        ctx.setLineDash([]);

        const pulsePhase = (Date.now() / 280) % (Math.PI * 2);
        const pulseR = 4.2 + Math.sin(pulsePhase) * 1.5;
        cfg.series.filter(s => s.visible).forEach(s => {
            const y0 = getY(s.data[intIdx]);
            const y1 = intIdx + 1 < n ? getY(s.data[intIdx + 1]) : y0;
            const leadY = y0 + (y1 - y0) * frac;

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
        });"""

text = text.replace(old_b_draw, new_b_draw)

# 4. Update b_motion_loop for super slow animation
old_b_loop = """    // ── Live Drive Cycle Wave Motion Engine ───────────────────────
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
        if (timeEl) {
            const mins = Math.floor(curT / 60);
            const secs = Math.floor(curT % 60);
            timeEl.textContent = 't = ' + curT.toFixed(0) + 's (' + mins + 'm ' + (secs < 10 ? '0' : '') + secs + 's) / 3600s (1.0 hr)';
        }
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
                batt_liveAnimIndex += 3;
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
    };"""

new_b_loop = """    // ── Live Drive Cycle Wave Motion Engine (Super Slow) ─────────
    let batt_liveAnimIndex = 0.0;
    let batt_isPlaying = true;
    let batt_speed = 0.25; // Super slow by default!
    let batt_lastFrameTime = 0;

    function batt_updateLiveStatus(idx) {
        if (typeof DATA === 'undefined' || !DATA || !DATA.times) return;
        const total = DATA.times.length;
        const curT = DATA.times[idx] || 0;
        const maxT = DATA.times[total - 1] || 3600;

        const timeEl = document.getElementById('batt_stream_time');
        if (timeEl) {
            const mins = Math.floor(curT / 60);
            const secs = Math.floor(curT % 60);
            timeEl.textContent = 't = ' + curT.toFixed(0) + 's (' + mins + 'm ' + (secs < 10 ? '0' : '') + secs + 's) / 3600s (1.0 hr)';
        }
        const barEl = document.getElementById('batt_stream_bar');
        if (barEl) barEl.style.width = ((idx / (total - 1)) * 100).toFixed(1) + '%';
    }

    function batt_animationLoop(timestamp) {
        if (batt_isPlaying) {
            if (!batt_lastFrameTime) batt_lastFrameTime = timestamp;
            const dt = Math.min((timestamp - batt_lastFrameTime) / 1000, 0.1);
            batt_lastFrameTime = timestamp;

            // 1801 points across 3600s: at 0.25x speed, advance ~7.5 steps per second
            batt_liveAnimIndex += (30.0 * batt_speed) * dt;
            if (batt_liveAnimIndex >= DATA.times.length - 1) {
                batt_liveAnimIndex = 0.0;
            }
            batt_updateLiveStatus(Math.floor(batt_liveAnimIndex));
            if (typeof renderAll === 'function') renderAll();
        } else {
            batt_lastFrameTime = timestamp;
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
        ['01', '025', '05', '1'].forEach(id => {
            const b = document.getElementById('batt_spd_' + id);
            if (b) b.classList.remove('active');
        });
        const key = spd === 0.1 ? '01' : (spd === 0.25 ? '025' : (spd === 0.5 ? '05' : '1'));
        const activeBtn = document.getElementById('batt_spd_' + key);
        if (activeBtn) activeBtn.classList.add('active');
    };

    window.batt_restartStream = function() {
        batt_liveAnimIndex = 0.0;
        batt_isPlaying = true;
        const btn = document.getElementById('batt_btn_play');
        if (btn) {
            btn.textContent = '⏸ Pause';
            btn.classList.add('active');
        }
        batt_updateLiveStatus(0);
        if (typeof renderAll === 'function') renderAll();
    };"""

text = text.replace(old_b_loop, new_b_loop)

# 5. Update p_new_draw to support floating-point sub-pixel interpolation
old_p_draw = """        // 2. Active moving waveform (streaming forward up to liveAnimIndex)
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
        });"""

new_p_draw = """        // 2. Active moving waveform (smooth continuous sub-pixel trace)
        const curIdx = Math.min(n - 1, Math.max(0, p4_liveAnimIndex));
        const intIdx = Math.floor(curIdx);
        const frac = curIdx - intIdx;
        const leadX = padL + curIdx * xStep;

        visibleSeries.forEach(s => {
            ctx.strokeStyle = s.color;
            ctx.lineWidth = (s.width || 2.0) + 0.6;
            ctx.setLineDash(s.dash || []);
            ctx.beginPath();
            for (let i = 0; i <= intIdx; i++) {
                const x = padL + i * xStep;
                const y = getY(s.data[i]);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            if (intIdx + 1 < n && frac > 0.001) {
                const y0 = getY(s.data[intIdx]);
                const y1 = getY(s.data[intIdx + 1]);
                const leadY = y0 + (y1 - y0) * frac;
                ctx.lineTo(leadX, leadY);
            }
            ctx.stroke();
            ctx.setLineDash([]);
        });

        // 3. Leading edge scanline & pulsing beacon head dot
        ctx.strokeStyle = 'rgba(2, 132, 199, 0.40)';
        ctx.lineWidth = 1.2;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(leadX, padT);
        ctx.lineTo(leadX, h - padB);
        ctx.stroke();
        ctx.setLineDash([]);

        const pulsePhase = (Date.now() / 280) % (Math.PI * 2);
        const pulseR = 4.2 + Math.sin(pulsePhase) * 1.5;
        visibleSeries.forEach(s => {
            const y0 = getY(s.data[intIdx]);
            const y1 = intIdx + 1 < n ? getY(s.data[intIdx + 1]) : y0;
            const leadY = y0 + (y1 - y0) * frac;

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
        });"""

text = text.replace(old_p_draw, new_p_draw)

# 6. Update p_motion_loop for super slow animation
old_p_loop = """    // ── Live Wave Motion Streaming Engine & KPI Updates ─────────
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
        if (timeEl) {
            const mins = Math.floor(curT / 60);
            const secs = Math.floor(curT % 60);
            timeEl.textContent = 't = ' + curT.toFixed(0) + 's (' + mins + 'm ' + (secs < 10 ? '0' : '') + secs + 's) / 3600s (1.0 hr)';
        }
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
    };"""

new_p_loop = """    // ── Live Wave Motion Streaming Engine & KPI Updates (Super Slow) ─────────
    let p4_liveAnimIndex = 0.0;
    let p4_isPlaying = true;
    let p4_speed = 0.25; // Super slow by default!
    let p4_lastFrameTime = 0;

    function p4_updateLiveKPIs(idx) {
        if (typeof DATA === 'undefined' || !DATA || !DATA.charts) return;
        const total = DATA.charts.times.length;
        const curT = DATA.charts.times[idx] || 0;
        const maxT = DATA.charts.times[total - 1] || 3600;

        const timeEl = document.getElementById('p4_stream_time');
        if (timeEl) {
            const mins = Math.floor(curT / 60);
            const secs = Math.floor(curT % 60);
            timeEl.textContent = 't = ' + curT.toFixed(0) + 's (' + mins + 'm ' + (secs < 10 ? '0' : '') + secs + 's) / 3600s (1.0 hr)';
        }
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
            const dt = Math.min((timestamp - p4_lastFrameTime) / 1000, 0.1);
            p4_lastFrameTime = timestamp;

            // 600 points across 3600s: at 0.25x speed, advance ~2.5 steps per second
            p4_liveAnimIndex += (10.0 * p4_speed) * dt;
            if (p4_liveAnimIndex >= DATA.charts.times.length - 1) {
                p4_liveAnimIndex = 0.0;
            }
            p4_updateLiveKPIs(Math.floor(p4_liveAnimIndex));
            if (typeof renderAllCharts === 'function') renderAllCharts();
        } else {
            p4_lastFrameTime = timestamp;
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
        ['01', '025', '05', '1'].forEach(id => {
            const b = document.getElementById('p4_spd_' + id);
            if (b) b.classList.remove('active');
        });
        const key = spd === 0.1 ? '01' : (spd === 0.25 ? '025' : (spd === 0.5 ? '05' : '1'));
        const activeBtn = document.getElementById('p4_spd_' + key);
        if (activeBtn) activeBtn.classList.add('active');
    };

    window.p4_restartStream = function() {
        p4_liveAnimIndex = 0.0;
        p4_isPlaying = true;
        const btn = document.getElementById('p4_btn_play');
        if (btn) {
            btn.textContent = '⏸ Pause';
            btn.classList.add('active');
        }
        p4_updateLiveKPIs(0);
        if (typeof renderAllCharts === 'function') renderAllCharts();
    };"""

text = text.replace(old_p_loop, new_p_loop)

with open(build_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Super slow wave motion applied to build_unified_dashboard.py!")

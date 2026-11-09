"""
Builds a single unified self-contained HTML dashboard merging all 3 sub-dashboards
into a single combined, continuous view with smooth jump navigation.
"""

import re
import os

def extract(path):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    style_m = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
    style = style_m.group(1).strip() if style_m else ''
    body_m = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
    raw_body = body_m.group(1).strip() if body_m else ''
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', raw_body, re.DOTALL)
    # Strip script tags from body so HTML contains only markup
    body = re.sub(r'<script\b[^>]*>.*?</script>', '', raw_body, flags=re.DOTALL).strip()
    return style, body, scripts

BASE = r'D:\Python Battery Simulation Model'
LOCAL_BASE = r'd:\appy 2'

active_base = BASE if os.path.exists(BASE) else LOCAL_BASE

b_style, b_body, b_scripts = extract(os.path.join(active_base, 'battery_dashboard.html'))
h_style, h_body, h_scripts = extract(os.path.join(active_base, 'hppc_dashboard.html'))
p_style, p_body, p_scripts = extract(os.path.join(active_base, 'phase4_dashboard.html'))

def prefix_body(html, prefix):
    """Add a prefix to all id=, for=, and href=# in body HTML."""
    html = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{prefix}{m.group(1)}"', html)
    html = re.sub(r'\bfor="([^"]+)"', lambda m: f'for="{prefix}{m.group(1)}"', html)
    html = re.sub(r'\bhref="#([^"]+)"', lambda m: f'href="#{prefix}{m.group(1)}"', html)
    return html

def prefix_script(script, prefix):
    """Prefix getElementById references in script, including dynamic cfg.id / cfg.legId."""
    script = re.sub(r"getElementById\('([^']+)'\)", lambda m: f"getElementById('{prefix}{m.group(1)}')", script)
    script = re.sub(r'getElementById\("([^"]+)"\)', lambda m: f'getElementById("{prefix}{m.group(1)}")', script)
    script = re.sub(r'getElementById\(cfg\.id\)', f"getElementById('{prefix}' + cfg.id)", script)
    script = re.sub(r'getElementById\(cfg\.legId\)', f"getElementById('{prefix}' + cfg.legId)", script)
    script = script.replace(f"getElementById('{prefix}tooltip')", "getElementById('global_tooltip')")
    return script

def strip_window_listeners(script):
    script = re.sub(r"window\.addEventListener\('resize'[^;]+;", '', script)
    script = re.sub(r"window\.addEventListener\('load'[^;]+;", '', script)
    script = re.sub(r'setTimeout\(\w+,\s*\d+\);', '', script)
    return script

b_body = prefix_body(b_body, 'batt_')
h_body = prefix_body(h_body, 'hppc_')
p_body = prefix_body(p_body, 'p4_')

# Remove duplicate local tooltip divs from bodies
b_body = re.sub(r'<div id="batt_tooltip"[^>]*>.*?</div>', '', b_body, flags=re.DOTALL)
h_body = re.sub(r'<div id="hppc_tooltip"[^>]*>.*?</div>', '', h_body, flags=re.DOTALL)
p_body = re.sub(r'<div id="p4_tooltip"[^>]*>.*?</div>', '', p_body, flags=re.DOTALL)

# Prepare scoped scripts inside IIFEs
b_raw = b_scripts[0] if b_scripts else ''
b_clean = strip_window_listeners(prefix_script(b_raw, 'batt_'))
b_wrapped = f"""
(() => {{
{b_clean}
    window.batt_renderAll = (typeof renderAll === 'function') ? renderAll : null;
}})();
"""

h_raw = h_scripts[0] if h_scripts else ''
h_clean = strip_window_listeners(prefix_script(h_raw, 'hppc_'))
h_wrapped = f"""
(() => {{
{h_clean}
    window.hppc_renderAll = (typeof renderAll === 'function') ? renderAll : null;
}})();
"""

p_raw = p_scripts[0] if p_scripts else ''
p_clean = strip_window_listeners(prefix_script(p_raw, 'p4_'))
p_wrapped = f"""
(() => {{
{p_clean}
    window.p4_renderAll = (typeof renderAllCharts === 'function') ? renderAllCharts : null;
}})();
"""

def clean_sub_style(css):
    # Remove body and root level styling so top-level body styling is preserved
    css = re.sub(r':root\s*\{[^}]*\}', '', css)
    css = re.sub(r'body\s*\{[^}]*\}', '', css)
    css = re.sub(r'@keyframes\s+pulse\s*\{.*?\}\s*\}', '', css, flags=re.DOTALL)
    return css

b_style_clean = clean_sub_style(b_style)
h_style_clean = clean_sub_style(h_style)
p_style_clean = clean_sub_style(p_style)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Battery Simulation Suite — Combined Single-Tab Dashboard</title>
    <style>
        /* ── Global Reset & Variables ──────────────────────────────── */
        :root {{
            --bg-base: #0b0f19;
            --bg-card: #131b2e;
            --bg-card-hover: #19233c;
            --bg-subtle: #0f172a;
            --border-dim: #1e293b;
            --border-bright: #334155;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --text-muted: #64748b;
            --cyan: #38bdf8;
            --emerald: #10b981;
            --amber: #f59e0b;
            --rose: #ef4444;
            --purple: #c084fc;
        }}
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            background: var(--bg-base);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh;
            padding-bottom: 60px;
        }}

        /* ── Top Navigation Bar ─────────────────────────────────────── */
        .top-nav {{
            position: sticky;
            top: 0;
            z-index: 1000;
            background: rgba(11,15,25,0.96);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-dim);
            padding: 0 32px;
            display: flex;
            align-items: center;
            gap: 16px;
            height: 58px;
        }}
        .nav-brand {{
            font-size: 15px;
            font-weight: 800;
            color: var(--cyan);
            letter-spacing: -0.5px;
            margin-right: 16px;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }}
        .nav-brand svg {{ flex-shrink: 0; }}
        .nav-all-in-one-badge {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--emerald);
            border: 1px solid rgba(16, 185, 129, 0.35);
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 3px 8px;
            border-radius: 9999px;
            margin-left: 6px;
        }}
        .tab-bar {{
            display: flex;
            gap: 4px;
            height: 100%;
            align-items: center;
            flex-wrap: nowrap;
            overflow-x: auto;
        }}
        .tab-btn {{
            background: none;
            border: 1px solid transparent;
            color: var(--text-muted);
            font-size: 12.5px;
            font-weight: 600;
            padding: 7px 14px;
            border-radius: 6px;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.15s ease;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .tab-btn:hover {{
            color: var(--text-dim);
            background: rgba(255,255,255,0.03);
            border-color: var(--border-dim);
        }}
        .tab-btn.active {{
            color: var(--cyan);
            background: rgba(56,189,248,0.1);
            border-color: rgba(56,189,248,0.35);
        }}
        .nav-status {{
            margin-left: auto;
            font-size: 11px;
            color: var(--text-muted);
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--emerald);
            display: inline-block;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%,100%{{ opacity:1; }}
            50%{{ opacity:0.4; }}
        }}

        /* ── All Tabs Combined Layout ───────────────────────────────── */
        .all-in-one-container {{
            max-width: 1440px;
            margin: 0 auto;
            padding: 24px 32px;
            display: flex;
            flex-direction: column;
            gap: 48px;
        }}

        /* All tab panes permanently visible */
        .tab-pane {{
            display: block !important;
            scroll-margin-top: 75px;
        }}

        /* ── Section Dividers & Banners ─────────────────────────────── */
        .section-banner {{
            display: flex;
            align-items: center;
            gap: 16px;
            background: linear-gradient(135deg, rgba(19, 27, 46, 0.95) 0%, rgba(15, 23, 42, 0.8) 100%);
            border: 1px solid var(--border-bright);
            border-left: 4px solid var(--cyan);
            border-radius: 10px;
            padding: 16px 22px;
            margin-bottom: 24px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        }}
        .section-banner.sec2 {{ border-left-color: var(--emerald); }}
        .section-banner.sec3 {{ border-left-color: var(--amber); }}
        .section-banner.sec4 {{ border-left-color: var(--purple); }}

        .section-badge {{
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
            background: rgba(56, 189, 248, 0.15);
            color: var(--cyan);
            border: 1px solid rgba(56, 189, 248, 0.3);
        }}
        .section-banner.sec2 .section-badge {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--emerald);
            border-color: rgba(16, 185, 129, 0.3);
        }}
        .section-banner.sec3 .section-badge {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--amber);
            border-color: rgba(245, 158, 11, 0.3);
        }}
        .section-banner.sec4 .section-badge {{
            background: rgba(192, 132, 252, 0.15);
            color: var(--purple);
            border-color: rgba(192, 132, 252, 0.3);
        }}

        .section-heading-text h2 {{
            font-size: 18px;
            font-weight: 700;
            color: var(--text-main);
            margin: 0 0 2px 0;
        }}
        .section-heading-text p {{
            font-size: 12px;
            color: var(--text-dim);
            margin: 0;
        }}

        /* ── Documentation & Presentation Cards ─────────────────────── */
        .doc-cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-top: 14px;
        }}
        .doc-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-dim);
            border-radius: 8px;
            padding: 16px 20px;
            text-decoration: none;
            color: inherit;
            display: flex;
            flex-direction: column;
            gap: 8px;
            transition: all 0.15s ease;
        }}
        .doc-card:hover {{
            background: var(--bg-card-hover);
            border-color: var(--cyan);
            transform: translateY(-2px);
        }}
        .doc-card-title {{
            font-size: 14px;
            font-weight: 700;
            color: var(--cyan);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .doc-card-desc {{
            font-size: 12px;
            color: var(--text-dim);
            line-height: 1.5;
        }}

        /* ── Shared tooltip ─────────────────────────────────────────── */
        #global_tooltip {{
            position: fixed;
            display: none;
            background: rgba(15,23,42,0.97);
            border: 1px solid var(--border-bright);
            padding: 9px 14px;
            border-radius: 7px;
            font-size: 11.5px;
            color: var(--text-main);
            pointer-events: none;
            z-index: 9999;
            box-shadow: 0 12px 28px rgba(0,0,0,0.6);
            line-height: 1.55;
            white-space: nowrap;
            max-width: 320px;
        }}

        /* ── Inject Scoped Sub-Dashboard Styles ──────────────────────── */
        /* Battery Dashboard styles */
        #tab-battery {{
            {b_style_clean}
        }}

        /* HPPC styles */
        #tab-hppc {{
            {h_style_clean}
        }}

        /* Phase 4 styles */
        #tab-phase4 {{
            {p_style_clean}
        }}

        /* Clean sub-headers to avoid redundancy with the section banner */
        .tab-pane .header {{ margin-bottom: 16px; }}
        .tab-pane .header h1 {{ font-size: 17px !important; }}
    </style>
</head>
<body>

    <!-- Top Navigation with Quick Section Jump Links -->
    <nav class="top-nav">
        <a href="#tab-phase4" class="nav-brand">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 18H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3.19"/>
                <path d="M15 6h2a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-3.19"/>
                <path d="M23 13v-2"/>
                <path d="M11 6v12"/><path d="M7 12h8"/>
            </svg>
            Battery Simulation Suite
            <span class="nav-all-in-one-badge">All Tabs Combined</span>
        </a>
        <div class="tab-bar">
            <a class="tab-btn active" href="#tab-phase4" data-tab="tab-phase4" onclick="scrollToSection('tab-phase4', event)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h18v18H3z"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
                1. Validation &amp; Diagnostics
            </a>
            <a class="tab-btn" href="#tab-battery" data-tab="tab-battery" onclick="scrollToSection('tab-battery', event)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                2. Drive Cycle Dynamics
            </a>
            <a class="tab-btn" href="#tab-hppc" data-tab="tab-hppc" onclick="scrollToSection('tab-hppc', event)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                3. HPPC Characterization
            </a>
            <a class="tab-btn" href="#tab-presentation" data-tab="tab-presentation" onclick="scrollToSection('tab-presentation', event)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                4. Viva &amp; Dissertation
            </a>
        </div>
        <div class="nav-status">
            <span class="dot"></span>&nbsp; Live &mdash; 100% Offline
        </div>
    </nav>

    <!-- ── Combined All-In-One Container ────────────────────────────── -->
    <div class="all-in-one-container">

        <!-- ── Section 1: Phase 4 Validation & Health Dashboard ─────── -->
        <section id="tab-phase4" class="tab-pane active">
            <div class="section-banner">
                <span class="section-badge">Section 1</span>
                <div class="section-heading-text">
                    <h2>Phase 4 — Adaptive Diagnostics &amp; Validation Benchmark</h2>
                    <p>Physics-informed digital twin parameter tracking, statistical comparison against fixed thresholds, and live anomaly alerts</p>
                </div>
            </div>
            {p_body}
        </section>

        <!-- ── Section 2: Battery Drive Cycle Dashboard ──────────────── -->
        <section id="tab-battery" class="tab-pane active">
            <div class="section-banner sec2">
                <span class="section-badge">Section 2</span>
                <div class="section-heading-text">
                    <h2>Dynamic Battery Drive Cycle Simulation</h2>
                    <p>High-frequency 2-RC Thevenin electrical &amp; thermal response under dynamic load, current, OCV, and SOC</p>
                </div>
            </div>
            {b_body}
        </section>

        <!-- ── Section 3: HPPC Characterization Dashboard ────────────── -->
        <section id="tab-hppc" class="tab-pane active">
            <div class="section-banner sec3">
                <span class="section-badge">Section 3</span>
                <div class="section-heading-text">
                    <h2>HPPC Pulse Characterization &amp; Parameter Identification</h2>
                    <p>Hybrid Pulse Power Characterization test isolating instantaneous ohmic resistance and diffusion overpotentials</p>
                </div>
            </div>
            {h_body}
        </section>

        <!-- ── Section 4: Viva Presentation & Academic Resources ─────── -->
        <section id="tab-presentation" class="tab-pane active">
            <div class="section-banner sec4">
                <span class="section-badge">Section 4</span>
                <div class="section-heading-text">
                    <h2>Academic Defense, Presentation &amp; Documentation</h2>
                    <p>Verified final-year EEE undergraduate dissertation deliverables, presentation deck, and audit reports</p>
                </div>
            </div>

            <div class="doc-cards-grid">
                <a href="/docs/viva_presentation_10_slides.html" target="_blank" class="doc-card">
                    <div class="doc-card-title">
                        <span>📊 10-Slide Interactive Viva Voce Defense Deck</span>
                        <span>↗</span>
                    </div>
                    <div class="doc-card-desc">
                        Full-screen presentation with oral speaker notes on every slide, mathematical derivations, 100-scenario benchmark cards, and examiner Q&amp;A prep.
                    </div>
                </a>
                <a href="/docs/academic_report_chapters_3_4_5.md" target="_blank" class="doc-card">
                    <div class="doc-card-title">
                        <span>📄 Academic Dissertation Chapters 3, 4, and 5</span>
                        <span>↗</span>
                    </div>
                    <div class="doc-card-desc">
                        Undergraduate engineering dissertation text with 2-RC state space equations, monotone Hermite splines, 95% Wilson confidence intervals, and thermal limitation analysis.
                    </div>
                </a>
                <a href="/docs/facts_to_verify_before_submission.md" target="_blank" class="doc-card">
                    <div class="doc-card-title">
                        <span>✅ Pre-Submission Student Verification Checklist</span>
                        <span>↗</span>
                    </div>
                    <div class="doc-card-desc">
                        Comprehensive checklist for institutional placeholders, supervisor designations, simulation boundary declarations, and numerical audit checks.
                    </div>
                </a>
                <a href="/audit_verification_results.json" target="_blank" class="doc-card">
                    <div class="doc-card-title">
                        <span>📈 Raw Benchmark Dataset (audit_verification_results.json)</span>
                        <span>↗</span>
                    </div>
                    <div class="doc-card-desc">
                        Machine-readable JSON data containing the 100-scenario held-out evaluation matrix, 5x5 confusion matrix, and condition breakdown.
                    </div>
                </a>
            </div>
        </section>

    </div>

    <!-- Global Shared Tooltip -->
    <div id="global_tooltip"></div>

    <!-- ── Combined Dashboard Navigation & Scroll Logic ─────────────── -->
    <script>
    function scrollToSection(sectionId, e) {{
        if (e) e.preventDefault();
        const target = document.getElementById(sectionId);
        if (target) {{
            const topNav = document.querySelector('.top-nav');
            const offset = topNav ? topNav.offsetHeight + 16 : 70;
            const topPos = target.getBoundingClientRect().top + window.pageYOffset - offset;
            window.scrollTo({{ top: topPos, behavior: 'smooth' }});
        }}
        document.querySelectorAll('.tab-btn').forEach(b => {{
            b.classList.toggle('active', b.getAttribute('data-tab') === sectionId);
        }});
    }}

    // Backwards-compatible switchTab (used by automated tests & CDP scripts)
    function switchTab(tabId, btn) {{
        scrollToSection(tabId);
        if (btn) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }}
    }}

    // Render all canvases across all 3 sections
    function renderAllSections() {{
        if (typeof window.p4_renderAll === 'function') window.p4_renderAll();
        if (typeof window.batt_renderAll === 'function') window.batt_renderAll();
        if (typeof window.hppc_renderAll === 'function') window.hppc_renderAll();
    }}

    window.addEventListener('resize', renderAllSections);
    window.addEventListener('load', () => {{ setTimeout(renderAllSections, 80); }});

    // Auto-highlight active navigation link on scroll
    window.addEventListener('scroll', () => {{
        const sections = ['tab-phase4', 'tab-battery', 'tab-hppc', 'tab-presentation'];
        const scrollPos = window.pageYOffset + 120;
        for (const id of sections) {{
            const el = document.getElementById(id);
            if (el) {{
                const top = el.offsetTop;
                const height = el.offsetHeight;
                if (scrollPos >= top && scrollPos < top + height) {{
                    document.querySelectorAll('.tab-btn').forEach(btn => {{
                        btn.classList.toggle('active', btn.getAttribute('data-tab') === id);
                    }});
                    break;
                }}
            }}
        }}
    }});
    </script>

    <!-- ── Phase 4 Script ────────────────────────────────────────────── -->
    <script>
    {p_wrapped}
    </script>

    <!-- ── Battery Drive Cycle Script ────────────────────────────────── -->
    <script>
    {b_wrapped}
    </script>

    <!-- ── HPPC Characterization Script ─────────────────────────────── -->
    <script>
    {h_wrapped}
    </script>

</body>
</html>
"""

# Write to both workspaces
for base_dir in [BASE, LOCAL_BASE]:
    if os.path.exists(base_dir):
        out_unified = os.path.join(base_dir, 'unified_dashboard.html')
        out_index = os.path.join(base_dir, 'index.html')
        with open(out_unified, 'w', encoding='utf-8') as f:
            f.write(HTML)
        with open(out_index, 'w', encoding='utf-8') as f:
            f.write(HTML)
        print(f"Updated: {out_unified} & {out_index} ({len(HTML):,} bytes)")

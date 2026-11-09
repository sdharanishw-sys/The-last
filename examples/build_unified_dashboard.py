"""
Builds a single unified self-contained HTML dashboard merging all 3 sub-dashboards
into a single combined, continuous view with a single merged taskbar header.
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

# Erase Phase 4 redundant header block from p_body, preserving badge span IDs (hidden) so JS runs without error
p_body = re.sub(
    r'<div class="header">.*?</div>\s*(?=<!-- Quick Navigation -->|<div class="nav-links">)',
    '<div style="display:none;"><span id="p4_badge-chem"></span><span id="p4_badge-cell"></span><span id="p4_badge-duration"></span><span id="p4_badge-status"></span></div>\\n',
    p_body,
    flags=re.DOTALL
)

# Remove duplicate local tooltip divs from bodies
b_body = re.sub(r'<div id="batt_tooltip"[^>]*>.*?</div>', '', b_body, flags=re.DOTALL)
h_body = re.sub(r'<div id="hppc_tooltip"[^>]*>.*?</div>', '', h_body, flags=re.DOTALL)
p_body = re.sub(r'<div id="p4_tooltip"[^>]*>.*?</div>', '', p_body, flags=re.DOTALL)

def tune_chart_colors(script):
    # Grid lines to warm subtle cream
    script = script.replace("ctx.strokeStyle = '#1e293b'", "ctx.strokeStyle = '#ebdccb'")
    script = script.replace("ctx.strokeStyle = '#334155'", "ctx.strokeStyle = '#ebdccb'")
    # Zero lines
    script = script.replace("ctx.strokeStyle = '#64748b'", "ctx.strokeStyle = '#c8bcab'")
    # Axis labels to readable warm taupe
    script = script.replace("ctx.fillStyle = '#64748b'", "ctx.fillStyle = '#78716c'")
    script = script.replace("ctx.fillStyle = '#94a3b8'", "ctx.fillStyle = '#78716c'")
    # Crosshair to deep charcoal
    script = script.replace("ctx.strokeStyle = '#f8fafc'", "ctx.strokeStyle = '#332e29'")
    return script

# Prepare scoped scripts inside IIFEs
b_raw = b_scripts[0] if b_scripts else ''
b_clean = tune_chart_colors(strip_window_listeners(prefix_script(b_raw, 'batt_')))
b_wrapped = f"""
(() => {{
{b_clean}
    window.batt_renderAll = (typeof renderAll === 'function') ? renderAll : null;
}})();
"""

h_raw = h_scripts[0] if h_scripts else ''
h_clean = tune_chart_colors(strip_window_listeners(prefix_script(h_raw, 'hppc_')))
h_wrapped = f"""
(() => {{
{h_clean}
    window.hppc_renderAll = (typeof renderAll === 'function') ? renderAll : null;
}})();
"""

p_raw = p_scripts[0] if p_scripts else ''
p_clean = tune_chart_colors(strip_window_listeners(prefix_script(p_raw, 'p4_')))
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
    <title>Battery Simulation Suite — Unified Single-Taskbar Dashboard</title>
    <style>
        /* ── Global Reset & Variables (Warm Sand & Cream Theme) ───────── */
        :root {{
            --bg-base: #fbf7ee;            /* Warm off-white / light cream linen base */
            --bg-card: #ffffff;            /* Crisp clean white cards */
            --bg-card-hover: #faf6ee;      /* Soft warm hover */
            --bg-subtle: #f4eee2;          /* Subtle warm sand fill */
            --border-dim: #e8ded0;         /* Soft warm card border */
            --border-bright: #dbcebc;      /* Focused / highlighted border */
            --text-main: #221e1b;          /* Deep warm espresso / charcoal */
            --text-dim: #6e665d;           /* Warm taupe */
            --text-muted: #8c827a;         /* Soft muted earth */
            --cyan: #0284c7;               /* Deep vibrant sky blue */
            --emerald: #16a34a;            /* Fresh leaf / emerald green (matches reference CTA) */
            --amber: #d97706;              /* Warm rich amber */
            --rose: #dc2626;               /* Clean crimson / rose */
            --purple: #7c3aed;             /* Rich violet */
            --blue: #2563eb;               /* Royal blue */

            /* Sub-dashboard unified variables */
            --bg-primary: #fbf7ee;
            --accent-blue: #0284c7;
            --accent-green: #16a34a;
            --accent-orange: #d97706;
            --accent-red: #dc2626;
            --border: #e8ded0;
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

        /* ── Top Navigation Bar (Warm Minimalist Design) ───────────────── */
        .top-nav {{
            position: sticky;
            top: 0;
            z-index: 1000;
            background: rgba(251, 247, 238, 0.94);
            backdrop-filter: blur(14px);
            border-bottom: 1px solid var(--border-dim);
            padding: 0 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 58px;
            gap: 16px;
            box-shadow: 0 2px 10px rgba(80, 65, 45, 0.03);
        }}
        .nav-brand {{
            font-size: 15px;
            font-weight: 800;
            color: var(--text-main);
            letter-spacing: -0.4px;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }}
        .nav-brand svg {{
            stroke: var(--emerald);
            flex-shrink: 0;
        }}

        /* ── Actions & Single Jump Menu ─────────────────────────────── */
        .nav-actions {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .single-jump-menu {{
            position: relative;
            display: inline-block;
        }}
        .single-jump-btn {{
            background: #ffffff;
            border: 1px solid var(--border-dim);
            color: var(--text-dim);
            padding: 7px 16px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 2px 6px rgba(80, 65, 45, 0.04);
            transition: all 0.15s ease;
        }}
        .single-jump-btn:hover {{
            color: var(--text-main);
            border-color: var(--border-bright);
            background: var(--bg-card-hover);
        }}
        .single-jump-dropdown {{
            position: absolute;
            top: 100%;
            right: 0;
            margin-top: 8px;
            background: #ffffff;
            border: 1px solid var(--border-dim);
            border-radius: 14px;
            box-shadow: 0 12px 32px rgba(80, 65, 45, 0.12);
            display: none;
            flex-direction: column;
            min-width: 240px;
            overflow: hidden;
            z-index: 1001;
        }}
        .single-jump-menu:hover .single-jump-dropdown,
        .single-jump-menu:focus-within .single-jump-dropdown {{
            display: flex;
        }}
        .single-jump-item {{
            padding: 11px 18px;
            color: var(--text-main);
            text-decoration: none;
            font-size: 12px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: background 0.15s;
            border-bottom: 1px solid var(--border-dim);
        }}
        .single-jump-item:last-child {{
            border-bottom: none;
        }}
        .single-jump-item:hover {{
            background: var(--bg-card-hover);
            color: var(--emerald);
        }}

        .nav-status {{
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
            gap: 44px;
        }}

        /* All tab panes permanently visible */
        .tab-pane {{
            display: block !important;
            scroll-margin-top: 75px;
        }}

        /* ── Card Styling & Theme Overrides ─────────────────────────── */
        .kpi-card, .chart-card, .table-card, .chart-container, .analysis-card {{
            background: #ffffff !important;
            border: 1px solid var(--border-dim) !important;
            border-radius: 16px !important;
            box-shadow: 0 3px 14px rgba(70, 55, 40, 0.04) !important;
        }}
        .analysis-card {{
            background: #ffffff !important;
        }}
        .tag-info {{ background: #e0f2fe !important; color: #0369a1 !important; border: 1px solid #bae6fd !important; border-radius: 9999px !important; }}
        .tag-warning {{ background: #fef3c7 !important; color: #b45309 !important; border: 1px solid #fde68a !important; border-radius: 9999px !important; }}
        .tag-critical {{ background: #fee2e2 !important; color: #b91c1c !important; border: 1px solid #fecaca !important; border-radius: 9999px !important; }}
        .tag-fault {{ background: #fee2e2 !important; color: #b91c1c !important; border: 1px solid #f87171 !important; border-radius: 9999px !important; }}
        .tag-monitor-adaptive {{ background: #dcfce7 !important; color: #15803d !important; border: 1px solid #bbf7d0 !important; border-radius: 9999px !important; }}
        .tag-monitor-fixed {{ background: #fef3c7 !important; color: #b45309 !important; border: 1px solid #fde68a !important; border-radius: 9999px !important; }}
        .badge {{ background: #f4eee2 !important; color: var(--text-main) !important; border: 1px solid var(--border-dim) !important; border-radius: 9999px !important; }}
        .offline-tag {{ background: #dcfce7 !important; color: #15803d !important; border: 1px solid #bbf7d0 !important; padding: 4px 10px !important; border-radius: 9999px !important; }}
        
        .nav-btn {{
            background: #ffffff !important;
            border: 1px solid var(--border-dim) !important;
            color: var(--text-dim) !important;
            border-radius: 9999px !important;
            font-weight: 500 !important;
            box-shadow: 0 2px 6px rgba(70, 55, 40, 0.03) !important;
            transition: all 0.15s ease !important;
        }}
        .nav-btn:hover {{
            background: var(--bg-card-hover) !important;
            color: var(--text-main) !important;
            border-color: var(--border-bright) !important;
        }}
        .filter-btn {{
            background: #ffffff !important;
            border: 1px solid var(--border-dim) !important;
            color: var(--text-dim) !important;
            border-radius: 9999px !important;
            font-weight: 500 !important;
            padding: 6px 14px !important;
            transition: all 0.15s ease !important;
        }}
        .filter-btn:hover {{
            background: var(--bg-card-hover) !important;
            color: var(--text-main) !important;
        }}
        .filter-btn.active {{
            background: var(--emerald) !important;
            color: #ffffff !important;
            border-color: var(--emerald) !important;
            font-weight: 600 !important;
            box-shadow: 0 2px 8px rgba(22, 163, 74, 0.25) !important;
        }}
        
        .table-wrap {{
            border-radius: 14px !important;
            overflow: hidden !important;
            border: 1px solid var(--border-dim) !important;
        }}
        .alerts-table thead th {{
            background: #f4eee2 !important;
            color: var(--text-main) !important;
            border-bottom: 1px solid var(--border-dim) !important;
        }}
        .alerts-table tbody tr {{
            border-bottom: 1px solid var(--border-dim) !important;
        }}
        .alerts-table tbody tr:hover {{
            background: #faf6ee !important;
        }}
        .alerts-table td {{
            color: var(--text-main) !important;
        }}

        /* ── Documentation & Presentation Cards ─────────────────────── */
        .doc-cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-top: 14px;
        }}
        .doc-card {{
            background: #ffffff;
            border: 1px solid var(--border-dim);
            border-radius: 16px;
            padding: 18px 22px;
            text-decoration: none;
            color: inherit;
            display: flex;
            flex-direction: column;
            gap: 8px;
            box-shadow: 0 3px 14px rgba(70, 55, 40, 0.04);
            transition: all 0.15s ease;
        }}
        .doc-card:hover {{
            background: #ffffff;
            border-color: var(--emerald);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(70, 55, 40, 0.08);
        }}
        .doc-card-title {{
            font-size: 14px;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .doc-card-title span:last-child {{
            color: var(--emerald);
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
            background: rgba(34, 30, 27, 0.94);
            border: 1px solid rgba(255, 255, 255, 0.12);
            padding: 9px 14px;
            border-radius: 8px;
            font-size: 11.5px;
            color: #fbf7ee;
            pointer-events: none;
            z-index: 9999;
            box-shadow: 0 12px 28px rgba(40, 30, 20, 0.18);
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

    <!-- Top Navigation: Merged Single Taskbar Header -->
    <nav class="top-nav">
        <a href="#tab-phase4" class="nav-brand">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 18H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3.19"/>
                <path d="M15 6h2a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-3.19"/>
                <path d="M23 13v-2"/>
                <path d="M11 6v12"/><path d="M7 12h8"/>
            </svg>
            Battery Simulation Suite
        </a>

        <div class="nav-actions">
            <!-- Single Compact Jump Dropdown Menu -->
            <div class="single-jump-menu">
                <button class="single-jump-btn" id="btn-jump-menu">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
                    Jump to Section ▾
                </button>
                <div class="single-jump-dropdown">
                    <a class="single-jump-item" href="#tab-phase4" data-tab="tab-phase4" onclick="scrollToSection('tab-phase4', event)">
                        <span>Validation &amp; Diagnostics</span>
                    </a>
                    <a class="single-jump-item" href="#tab-battery" data-tab="tab-battery" onclick="scrollToSection('tab-battery', event)">
                        <span>Drive Cycle Dynamics</span>
                    </a>
                    <a class="single-jump-item" href="#tab-hppc" data-tab="tab-hppc" onclick="scrollToSection('tab-hppc', event)">
                        <span>HPPC Characterization</span>
                    </a>
                    <a class="single-jump-item" href="#tab-presentation" data-tab="tab-presentation" onclick="scrollToSection('tab-presentation', event)">
                        <span>Viva &amp; Dissertation</span>
                    </a>
                </div>
            </div>

            <div class="nav-status">
                <span class="dot"></span>&nbsp; Live &mdash; 100% Offline
            </div>
        </div>
    </nav>

    <!-- ── Combined All-In-One Container ────────────────────────────── -->
    <div class="all-in-one-container">

        <!-- ── Validation & Health Dashboard ─────── -->
        <section id="tab-phase4" class="tab-pane active">
            {p_body}
        </section>

        <!-- ── Battery Drive Cycle Dashboard ──────────────── -->
        <section id="tab-battery" class="tab-pane active">
            {b_body}
        </section>

        <!-- ── HPPC Characterization Dashboard ────────────── -->
        <section id="tab-hppc" class="tab-pane active">
            {h_body}
        </section>

        <!-- ── Viva Presentation & Academic Resources ─────── -->
        <section id="tab-presentation" class="tab-pane active">
            <div class="header" style="margin-bottom: 20px;">
                <div>
                    <h1 style="font-size:20px; font-weight:700; color:var(--text-main); margin-bottom:4px;">Academic Defense, Presentation &amp; Documentation</h1>
                    <p style="font-size:12px; color:var(--text-dim);">Verified final-year EEE undergraduate dissertation deliverables, presentation deck, and audit reports</p>
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
    }}

    // Backwards-compatible switchTab (used by automated tests & CDP scripts)
    function switchTab(tabId, btn) {{
        scrollToSection(tabId);
    }}

    // Render all canvases across all 3 sections
    function renderAllSections() {{
        if (typeof window.p4_renderAll === 'function') window.p4_renderAll();
        if (typeof window.batt_renderAll === 'function') window.batt_renderAll();
        if (typeof window.hppc_renderAll === 'function') window.hppc_renderAll();
    }}

    window.addEventListener('resize', renderAllSections);
    window.addEventListener('load', () => {{ setTimeout(renderAllSections, 80); }});
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

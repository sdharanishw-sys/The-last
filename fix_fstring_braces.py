with open(r'D:\Python Battery Simulation Model\examples\build_unified_dashboard.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix unescaped single braces in @keyframes livePulseAnim
old_anim = """        @keyframes livePulseAnim {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(22, 163, 74, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }
        }"""

new_anim = """        @keyframes livePulseAnim {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(22, 163, 74, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }}
        }}"""

# Also fix the rules in .live-stream-bar and its classes
text = text.replace(old_anim, new_anim)

# Let's check other braces in the added css
rules = [
    ('.live-stream-bar {', '.live-stream-bar {{'),
    ('.live-stream-status {', '.live-stream-status {{'),
    ('.live-pulse-dot {', '.live-pulse-dot {{'),
    ('.live-title {', '.live-title {{'),
    ('.live-step-label {', '.live-step-label {{'),
    ('.live-progress-track {', '.live-progress-track {{'),
    ('.live-progress-bar {', '.live-progress-bar {{'),
    ('.live-stream-controls {', '.live-stream-controls {{'),
    ('.live-ctrl-btn {', '.live-ctrl-btn {{'),
    ('.live-ctrl-btn:hover {', '.live-ctrl-btn:hover {{'),
    ('.live-ctrl-btn.active {', '.live-ctrl-btn.active {{'),
]

# We need to only replace within the CSS addition
css_start = text.find('/* ── Live Stream Telemetry Bar ─────────────────────────────── */')
css_end = text.find('/* ── Inject Scoped Sub-Dashboard Styles ──────────────────────── */')

if css_start != -1 and css_end != -1:
    css_section = text[css_start:css_end]
    # Replace all single { and } with {{ and }} if not already doubled
    # Let's replace systematically
    fixed_section = css_section
    for old_r, new_r in rules:
        fixed_section = fixed_section.replace(old_r, new_r)
    # Also replace trailing } with }}
    # Notice each rule ends with }
    fixed_section = fixed_section.replace(';\n        }', ';\n        }}')
    fixed_section = fixed_section.replace(';\n        }\n', ';\n        }}\n')
    text = text[:css_start] + fixed_section + text[css_end:]

with open(r'D:\Python Battery Simulation Model\examples\build_unified_dashboard.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed CSS f-string braces in build_unified_dashboard.py")

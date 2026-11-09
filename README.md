# Twin Reference Adaptive Battery Management System with Deviation Attribution for Personalized EV Battery Health

A physics-informed electro-thermal battery simulation engine that generates realistic **voltage, current, state of charge (SOC), and temperature telemetry** without requiring physical hardware.

Includes:
- **Phase 1**: Industry-standard **2-RC Thevenin Equivalent Circuit Model (ECM)** with strictly monotonic thermodynamic OCV curves, coupled with an **Arrhenius-corrected lumped thermal model**, multi-cell battery packs with passive balancing, and simulated Battery Management System (BMS) safety supervision.
- **Phase 2**: **Personalized Reference Model** establishing an individualized baseline fingerprint for each cell (usable capacity across temperatures, DC internal resistance curve, slow/fast RC time constants, OCV deviation) to compare live measurements against expected values in real-time.
- **Phase 3**: **Fault Attribution Diagnostics Engine** introducing controlled physical degradation and sensory anomalies (increased internal resistance, abnormal temperature rise, capacity fade, sensor bias) and extracting physical discriminator signatures to identify root causes with high confidence.
- **Phase 4**: **Interactive Health Dashboard & Validation Benchmark** generating a 100% offline air-gapped HTML5 Canvas dashboard with battery operational metrics, reference-versus-actual plots, live alerts feed, and a quantitative benchmark engine comparing the **Adaptive Reference Model** against a conventional **Fixed-Threshold Baseline**.

---

## 🎯 Scope & Architecture Clarification

> [!IMPORTANT]
> **What This System Is:**
> A physics-informed **software simulation digital twin** for cells and series-parallel packs. It calculates continuous electrochemical dynamics, thermal heat dissipation, transient polarization relaxation, personalized reference tracking, and root-cause fault attribution for algorithm prototyping and telemetry synthesis.
>
> **What This System Is NOT:**
> This is **not embedded microcontroller firmware for a physical vehicle BMS**. It does not interface with physical hardware via CAN bus / LIN, does not communicate over SPI with analog frontend ICs (e.g. BQ76952, LTC6811), and does not implement vehicle-specific high-level supervisory state machines (e.g. ISO 26262 ASIL-D fault managers or drive-mode personalities).

---

## 📊 Phase 4: Dashboard & Validation Benchmark

Phase 4 evaluates and contrasts the **Adaptive Reference Model** method against conventional **Fixed-Threshold Baselines** (static scalar bounds used in traditional BMS firmware: $V_{\min}=2.75\text{V}, V_{\max}=4.25\text{V}, T_{\max}=55^\circ\text{C}, R_{0,\max}=55\,\text{m}\Omega$).

### Quantitative Benchmark Comparison

Evaluated across a comprehensive suite of 7 operational scenarios (Nominal 25°C, Sub-Zero -10°C Cold, Mild Resistance +12 mΩ, Severe Resistance +25 mΩ, Sensor Bias +35 mV, Abnormal Cooling Loss + Heat Flux, and Capacity Fade):

```text
==========================================================================
     BENCHMARK: ADAPTIVE REFERENCE MODEL vs FIXED-THRESHOLD BASELINE
==========================================================================
  Total Scenarios Evaluated: 7 (5 faults, 2 nominal/harsh)
--------------------------------------------------------------------------
METRIC                             |  FIXED-THRESHOLD |  ADAPTIVE METHOD
--------------------------------------------------------------------------
Overall Classification Accuracy    |            28.6% |           100.0%
False Positive Rate (FPR)          |            50.0% |             0.0%
False Negative Rate (Missed)       |            80.0% |             0.0%
Mean Detection Latency (TTD)       |            2.0 s |           27.2 s
Root-Cause Attribution Specificity |             0.0% |           100.0%
==========================================================================
```

### Why Fixed-Threshold BMS Fails (and How the Adaptive Model Succeeds)

1. **Harsh Environment False Alarms (50.0% FPR):**
   - At $-10^\circ\text{C}$ sub-zero ambient temperature, a healthy battery cell's internal resistance naturally rises $\sim 2.5\times$ due to fundamental Arrhenius kinetics ($E_a \approx 22.5\,\text{kJ/mol}$).
   - Static threshold monitors trip false alarms when $R_0 > 55\,\text{m}\Omega$ on perfectly healthy cells.
   - The **Adaptive Reference Model** predicts the temperature-dependent Arrhenius resistance rise, avoiding false alarms ($0.0\%$ FPR).
2. **Silent Failures on Subtle Drift (80.0% Missed / FNR):**
   - A $+35\,\text{mV}$ ADC voltage sensor calibration bias or $+12\,\text{m}\Omega$ early contact corrosion leaves cell voltage at $\sim 3.835\,\text{V}$, well within static $2.75\text{V} - 4.25\text{V}$ bounds. Static BMS monitors completely miss these faults.
   - The **Adaptive Reference Model** continuously monitors dynamic signed residuals ($V_{\text{res}} = V_{\text{meas}} - V_{\text{pred}}$), flagging anomalous deviations within seconds.
3. **Decoupled Root-Cause Attribution (0.0% vs 100.0%):**
   - A static threshold trip indicates only that a limit was breached; it provides zero information on whether voltage sag was caused by high load current, sub-zero cold, SEI layer thickening, or sensor drift.
   - The **Adaptive Attribution Engine** separates current-correlated slope $dV_{\text{res}}/dI$ (Ohmic degradation) from resting zero-current offset $V_{\text{rest}}$ (sensor bias), identifying the exact root cause with high confidence.

### Interactive Phase 4 Dashboard (`phase4_dashboard.html`)

- **100% Offline & Air-Gapped**: Pure vanilla HTML5 `<canvas>` rendering engine; zero CDN dependencies, zero external network scripts, fully self-contained.
- **Section 1 — Operational Metrics**: Real-time KPI cards for Terminal Voltage, Current & Power, SOC & Coulombic Ah, Cell Temperature & Delta vs Ambient, DCIR & Impedance Drift %, SOH %, Anomaly Score, and Diagnostic Health Badge.
- **Section 2 — Reference-vs-Actual Plots**:
  - *Terminal Voltage & Dynamic Residual Ribbon*: Measured voltage vs Baseline predicted voltage, plus dynamic residual $V_{\text{res}}$ in mV with warning bands.
  - *DCIR Internal Resistance Tracking*: Measured $R_0(t)$ vs Baseline expected $R_{0,\text{baseline}}(\text{SOC}, T)$ over time and SOC.
  - *Thermal Evolution & Convective Equilibrium*: Cell temperature vs model equilibrium prediction highlighting excess heat zones.
  - *SOC & Delivered Energy*: SOC tracking alongside net Ah / Wh throughput.
- **Section 3 — Live Alerts Feed**: Filterable multi-monitor alerts table with severity badges (`INFO`, `WARNING`, `CRITICAL`, `FAULT`), source monitor pills, measured vs threshold numbers, and residuals.
- **Section 4 — Validation Benchmark Engine**: Side-by-side KPI comparison cards and full multi-scenario comparative matrix with physical failure insights.

---

## 🔍 Phase 3: Fault Attribution & Diagnostics

The diagnostic engine extracts physical discriminator signatures from operational telemetry and baseline reference residuals to differentiate between physical battery degradation and sensor calibration drift:

| Fault Type | Physical Mechanism | Primary Discriminator Signature | Rest (I ≈ 0) Behavior |
| :--- | :--- | :--- | :--- |
| **Increased Internal Resistance** | Contact corrosion, SEI layer growth, electrolyte degradation | Voltage residual is strictly proportional to load current: $\Delta V = -I \cdot \Delta R_0$. Steep negative $dV_{\text{res}}/dI$ slope. | $\Delta V_{\text{residual}} \approx 0\,\text{mV}$ (residual vanishes when current ceases). |
| **Voltage Sensor Bias** | ADC reference shift, operational amplifier offset | Constant voltage residual $V_{\text{residual}} = V_{\text{bias}}$ independent of current. | $\Delta V_{\text{residual}} = V_{\text{bias}} \neq 0\,\text{mV}$ (offset persists at rest). |
| **Abnormal Temperature Rise** | Convective cooling failure, micro-internal soft short | Cell temperature $T_{\text{cell}}$ persistently exceeds model-predicted thermal equilibrium: $T_{\text{cell}} - T_{\text{pred}} \gg 0$. | Excess heat continues dissipating slowly based on lumped thermal mass. |
| **Capacity Fade** | Active material cracking, lithium inventory loss | Delivered Ah throughput before voltage cutoff degrades ($Q_{\text{actual}} < Q_{\text{baseline}}$); Coulomb counting diverges from OCV lookup. | Static resistance slope and zero-current voltage remain nominal. |
| **Nominal (Healthy)** | Standard measurement noise | All residuals within calibration tolerances ($\|dV/dI\| < 6\,\text{m}\Omega$, $\|\Delta V_{\text{rest}}\| < 15\,\text{mV}$, $\Delta T < 4^\circ\text{C}$). | No persistent residuals. |

---

## ⚡ Core Capabilities

- **Strictly Monotonic Thermodynamic OCV**:
  - Implements **Fritsch-Carlson Monotone Cubic Spline** interpolation to guarantee $\frac{\partial V_{\text{ocv}}}{\partial \text{SOC}} > 0$ strictly across the entire $[0.0, 1.0]$ SOC domain without Runge-phenomenon polynomial oscillations (supports NMC and LFP chemistries).
- **Equivalent Circuit Model (2-RC Dual Polarization Thevenin)**:
  - Ohmic resistance $R_0(\text{SOC}, T)$ with Arrhenius temperature scaling ($E_a / R_{\text{gas}}$).
  - Fast charge-transfer polarization ($R_1, C_1$, $\tau_1 \approx 17\,\text{s}$).
  - Slow chemical diffusion polarization ($R_2, C_2$, $\tau_2 \approx 81\,\text{s}$).
- **First-Law Coupled Lumped Thermal Model**:
  - Reversible entropic heat ($\pm I \cdot T \cdot \frac{\partial V_{\text{ocv}}}{\partial T}$).
  - Irreversible Ohmic Joule heating ($I^2 R_0$).
  - Polarization dissipative losses ($V_{\text{rc1}}^2 / R_1 + V_{\text{rc2}}^2 / R_2$).
  - Convective heat dissipation to ambient ($h \cdot A \cdot (T_{\text{cell}} - T_{\text{ambient}})$).
- **Multi-Cell Battery Pack & Passive Balancing**:
  - Models $N_s \times N_p$ topologies (e.g. 4S1P, 16S2P).
  - Cell-to-cell parameter manufacturing dispersion (capacity $\sigma \approx 1.5\%$, resistance $\sigma \approx 4\%$).
  - **Passive Cell Balancing**: When individual cell voltages exceed threshold during top-of-charge, a shunt bleed resistor ($R_{\text{bleed}} \approx 47\,\Omega$, $\sim 88\,\text{mA}$) bypasses current to equalize pack cell dispersion ($\Delta V = V_{\max} - V_{\min}$).
- **BMS Safety Supervision**:
  - Over-voltage cutoff ($V > V_{\max} + 0.05\,\text{V}$)
  - Under-voltage cutoff ($V < V_{\min}$)
  - Over-temperature safety trip ($T \ge 60.0^\circ\text{C}$)
  - Sub-zero charging lockout ($T < 0.0^\circ\text{C}$ to prevent lithium plating)
- **100% Offline Visualization & Exporters**:
  - Telemetry CSV and JSON export.
  - Publication-grade 4-panel SVG vector charts.
  - **100% Air-Gapped Offline HTML Dashboard**: Pure HTML5 `<canvas>` interactive charts with mouse hover crosshairs and tooltips, requiring **0 CDN requests and 0 external scripts**.

---

## ⏱️ Trajectory Accounting & Stepping Convention

For a requested simulation duration $D$ and step size $\Delta t$:
- **Total Physics Steps**: $N = \text{round}(D / \Delta t)$.
- **Simulated Elapsed Time**: $D = N \cdot \Delta t$.
- **Trajectory Points Recorded**: $N + 1$ samples.
  - **Point 0 ($t = 0.0\,\text{s}$)**: Initial baseline condition before any time steps are applied.
  - **Points $1 \dots N$ ($t = k \cdot \Delta t$)**: Physical battery states after each integration interval.

---

## 🚀 Quickstart CLI

### Basic Simulation
```bash
python -m battery_sim.cli --profile drive-cycle --initial-soc 0.90 --temp-profile sinusoidal --ambient-temp 25.0 --duration 1800 --dt 1.0
```

### Phase 4 Validation Benchmark & Dashboard Generation
```bash
# Run simulation, benchmark engine, and export Phase 4 dashboard
python -m battery_sim.cli --profile drive-cycle --duration 300 --benchmark --phase4-dashboard phase4_dashboard.html
```

### Fault Injection & Attribution
```bash
# Inject +25 mOhm resistance fault and diagnose
python -m battery_sim.cli --profile drive-cycle --duration 300 --fault resistance --resistance-adder 0.025

# Inject +40 mV voltage sensor bias and diagnose
python -m battery_sim.cli --profile drive-cycle --duration 300 --fault sensor-bias --voltage-bias 0.040

# Inject cooling failure thermal anomaly
python -m battery_sim.cli --profile drive-cycle --duration 300 --fault temperature --cooling-factor 0.20

# Inject 20% capacity fade
python -m battery_sim.cli --profile drive-cycle --duration 300 --fault capacity-fade --capacity-retention 0.80
```

### Pre-packaged Examples

1. **Phase 4 Dashboard & Validation Benchmark Demo**:
   ```bash
   python examples/run_phase4_dashboard.py
   ```
2. **Phase 3 Fault Attribution Benchmark Suite**:
   ```bash
   python examples/run_phase3_fault_attribution.py
   ```
3. **Phase 2 Reference Model Calibration & Comparison**:
   ```bash
   python examples/run_phase2_reference_model.py
   ```
4. **Multi-Cell Pack with Passive Balancing (4S1P)**:
   ```bash
   python examples/run_pack_balancing.py
   ```
5. **Ambient Temperature Sweep ($-15^\circ\text{C}$ to $45^\circ\text{C}$)**:
   ```bash
   python examples/run_temp_sweep.py
   ```
6. **HPPC Pulse Characterization Test**:
   ```bash
   python examples/run_hppc_pulse.py
   ```

---

## 💻 Python API Usage

### Phase 4 Validation & Dashboard Pipeline

```python
from battery_sim.cell_model import BatteryCell, CellParameters
from battery_sim.reference_model import BaselineCalibrator
from battery_sim.validation import (
    FixedThresholdMonitor,
    AdaptiveReferenceMonitor,
    BenchmarkRunner,
)
from battery_sim.visualizer import generate_phase4_dashboard

# 1. Calibrate baseline reference model
cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=1.0)
baseline = BaselineCalibrator(cell, cell_id="REF-001").build()

# 2. Run benchmark comparing Adaptive Model vs Fixed Threshold Baseline
runner = BenchmarkRunner(baseline=baseline)
summary = runner.run_benchmark(sim_duration_s=360.0)

print(summary.summary())

# 3. Generate 100% offline self-contained HTML5 dashboard
generate_phase4_dashboard(
    telemetry=[], # Or simulation history
    benchmark_summary=summary,
    output_path="phase4_dashboard.html",
)
```

---

## 📚 Academic Documentation & Dissertation Chapters

The repository is organized into 7 clearly categorized modules:

```text
The-last/
├── 1. Root Application & Live Dashboard/
│   ├── index.html                     # Canonical unified 1-hour interactive simulation dashboard
│   ├── serve.py                       # Local multi-threaded HTTP server daemon (port 8000)
│   └── requirements.txt               # Dependencies
├── 2. Verification & Automated Audit Harnesses/
│   ├── demonstrate_flows.py           # End-to-end multi-phase simulation runner
│   ├── verification_suite.py          # 100-scenario statistical validation suite
│   └── browser_audit.py               # Automated headless Chrome CDP health-check
├── 3. Simulation Datasets & Telemetry Baselines/
│   ├── CELL-NMC-001_baseline.json     # Reference fresh cell baseline calibration
│   ├── CELL-NMC-AGED_baseline.json    # Aged cell degradation baseline
│   ├── audit_verification_results.json# 100-scenario held-out evaluation matrix
│   ├── phase4_alerts.csv              # 1-hour physical anomaly alert log (1,231 events)
│   ├── drive_cycle_telemetry.csv      # Dynamic drive cycle current & voltage profile
│   ├── hppc_telemetry.csv             # HPPC test telemetry profile
│   └── battery_telemetry.csv          # Sample cell telemetry
├── 4. Core Simulation Package/
│   └── battery_sim/                   # Core physics-informed 2-RC model package
├── 5. Executable Examples/
│   ├── build_unified_dashboard.py     # Compiles unified offline dashboard
│   ├── run_phase4_dashboard.py        # 1-hour Phase 4 adaptive diagnostic simulation
│   ├── run_drive_cycle.py             # 1-hour drive cycle terminal dynamics
│   ├── run_phase2_reference_model.py  # Reference model vs degraded cell comparison
│   ├── run_phase3_fault_attribution.py# Multi-parameter fault isolation
│   ├── run_hppc_pulse.py              # HPPC pulse characterization tests
│   ├── run_pack_balancing.py          # Multi-cell passive balancing
│   └── run_temp_sweep.py              # Temperature sweep evaluation
├── 6. Test Suite/
│   ├── test_battery_sim.py            # Physics equations & ECM unit tests
│   ├── test_fault_attribution.py      # Anomaly scoring & attribution unit tests
│   └── test_validation_benchmark.py   # Benchmark regression tests
└── 7. Documentation, Viva Slides & Assets/
    ├── academic_report_chapters_3_4_5.md
    ├── bms_dashboard_demonstration_guide.md
    ├── facts_to_verify_before_submission.md
    ├── viva_presentation_10_slides.html
    ├── viva_presentation_10_slides.md
    ├── pipeline_architecture.png
    ├── Elegant Mathematical Equation.png
    ├── Neon Battery Safety Processing Pipeline.png
    └── screenshots/
```

- **[Academic Dissertation Chapters 3, 4, and 5](7.%20Documentation,%20Viva%20Slides%20&%20Assets/academic_report_chapters_3_4_5.md):** Formal undergraduate Electrical & Electronics Engineering (EEE) thesis chapters:
  - *Chapter 3:* 2-RC Thevenin state-space equations, Fritsch-Carlson monotone cubic spline interpolation, Arrhenius temperature kinetics, lumped 1-D thermal model, 4-stage personalized baseline calibration, resting dwell polarization compensation, and BMS safety supervisor cutoffs.
  - *Chapter 4:* 100-scenario held-out benchmark ($N=100$, seeds 2000–2099) results, multi-class confusion matrix, two-sided 95% Wilson confidence intervals, and detailed physical analysis of the 6/16 thermal fault detection rate ($\tau_{\text{th}} = 780\text{ s}$).
  - *Chapter 5:* Declaration of synthetic software simulation digital twin, physical modeling assumptions (1-D lumped thermal, ECM vs DFN), failure modes, and hardware implementation roadmap (C99 on ARM Cortex-M4/M7, Analog Front-End ICs, Dual UKF, ISO 26262 ASIL).
- **[10-Slide Viva Voce Defense Presentation (Markdown)](docs/viva_presentation_10_slides.md) / [Interactive Web Presentation (HTML)](docs/viva_presentation_10_slides.html):** Comprehensive 10-slide oral defense deck with complete speaker scripts, mathematical derivations, visual layout descriptions, and anticipated examiner Q&A answers.
- **[Pre-Submission Student Verification Checklist](docs/facts_to_verify_before_submission.md):** Institutional placeholders, integrity verification, and quantitative audit check.
- **[Dashboard Demonstration & Presentation Guide](docs/bms_dashboard_demonstration_guide.md):** Step-by-step demonstration manual covering healthy cycles, aggressive driving, sensor bias injection, resistance growth, thermal limitations, and telemetry rejections with high-resolution UI screenshots (`docs/screenshots/`).

---

## 🧪 Comprehensive Verification Tests

Run the complete 32-test verification suite:

```bash
python -m unittest discover tests -v
```

Verified physical & diagnostic properties:
1. **OCV Strict Monotonicity**: Verifies $\Delta V_{\text{ocv}} \ge 0$ strictly across 1,000 fine grid points for both NMC and LFP.
2. **Arrhenius Linearity**: Verifies $\ln(R_0) \propto 1/T$ slope matches $E_a / R_{\text{gas}}$ across $-20^\circ\text{C}$ to $55^\circ\text{C}$.
3. **Diffusion Relaxation**: Verifies exponential decay $V_{\text{rc}}(t) = V_0 e^{-t/\tau}$ at zero-current relaxation.
4. **First Law Energy Conservation**: Verifies $\int Q_{\text{gen}} dt = m C_p \Delta T$ in an adiabatic system.
5. **Coulombic Efficiency & Low-Temp Derating**: Verifies charge asymmetry ($\eta = 0.995$) and cold capacity degradation.
6. **Trajectory Accounting**: Verifies $N = D / \Delta t$ physics steps and $N+1$ stored points.
7. **BMS Safety Cutoffs**: Sub-zero charging lockout, over-temperature thermal trip, and under-voltage protection.
8. **Battery Pack & Balancing**: Verifies series voltage summation and passive balancing bleed activation.
9. **Fault Attribution: Increased Resistance**: Verifies detection of $+20\,\text{m}\Omega$ degradation with $>90\%$ confidence.
10. **Fault Attribution: Voltage Sensor Bias**: Verifies detection of positive and negative ADC offsets ($+40\,\text{mV}, -30\,\text{mV}$).
11. **Fault Attribution: Temperature Rise**: Verifies detection of cooling failure + micro-short heat flux.
12. **Fault Attribution: Capacity Fade**: Verifies detection of $25\%$ active material loss.
13. **Fault Attribution: Nominal Baseline**: Verifies zero false-positive rate on healthy cells.
14. **Discriminator Orthogonality**: Mathematically proves clean separation between current-proportional $IR$ voltage drop and static sensor bias.
15. **Fixed-Threshold Cold False Alarm**: Verifies static BMS triggers false alarm at $-10^\circ\text{C}$ sub-zero, while Adaptive Model maintains $0\%$ FPR.
16. **Fixed-Threshold Silent Failure**: Verifies static BMS misses $+35\,\text{mV}$ voltage sensor bias, while Adaptive Model detects the dynamic residual.
17. **Adaptive Alert Generation**: Verifies severity ratings (`CRITICAL`, `WARNING`, `FAULT`) and dynamic residual reporting.
18. **Validation Benchmark Engine**: Verifies multi-scenario scorecards and $100\%$ root-cause attribution specificity.
19. **Air-Gapped Offline Dashboard Integrity**: Verifies zero CDN URLs, zero external script tags, and pure embedded Canvas rendering in generated HTML.

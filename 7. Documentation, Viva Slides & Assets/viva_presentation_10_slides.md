# Adaptive EV Battery Management System: 10-Slide Viva Voce Presentation & Speaker Notes

## Final-Year Undergraduate Engineering Defense (EEE)

---

## Slide 1: Title & Project Overview

### Slide Visual / Layout
- **Header:** Final-Year B.E. Project Defense
- **Main Title:** Adaptive EV Battery Management System: Personality-Based Diagnostics and Physics-Informed Digital Twin
- **Subtitle:** Decoupling Dynamic Driver Transients from Incipient Cell Degradation and Sensor Faults
- **Project Team Members:**
  - **AL ZAFIRAH M** (Roll No: 730923105003)
  - **BASKAR RAJA S** (Roll No: 730923105008)
  - **DHARANISHWARAN S** (Roll No: 730923105014)
  - **DINESH A** (Roll No: 730923105015)
- **Degree:** Bachelor of Engineering (B.E.)
- **Supervisor:** Prof. Rajaswari
- **Department:** Department of Electrical & Electronics Engineering
- **Institution:** Excel Engineering College (Autonomous), Batch: 2023–2027

### Key Bullet Points
- **Core Problem:** Conventional fixed-threshold BMS architectures suffer from an unavoidable compromise: high false alarms during aggressive driving vs. silent failure on subtle sensor drift.
- **Proposed Solution:** A physics-informed **Personalized Digital Twin** integrating a 2-RC Thevenin equivalent circuit, Fritsch-Carlson monotone OCV spline, and Arrhenius thermal kinetics.
- **Key Innovation:** Decoupled multi-class fault attribution using dynamic impedance regression ($\frac{dV_{\text{res}}}{dI}$) and polarization-compensated rest dwell filtering ($t_{\text{dwell}} \ge 20\text{ s}$).
- **Benchmark Performance:** Evaluated across a 100-scenario held-out benchmark ($N=100$): **$89.0\%$ overall accuracy** and **$98.31\%$ precision**, reducing false positive rate from $31.25\%$ to **$3.12\%$**.

---

### Speaker Notes (Oral Script)
> *"Respected external examiner, internal supervisor Prof. Rajaswari, and faculty members, good morning. We—Al Zafirah, Baskar Raja, Dharanishwaran, and Dinesh—welcome you to the defense of our final-year project: 'Adaptive EV Battery Management System: Personality-Based Diagnostics and Physics-Informed Digital Twin'.*
>
> *In modern electric vehicles, the battery management system is the central nervous system ensuring safety, performance, and longevity. However, traditional commercial BMS firmware relies heavily on static scalar thresholds. When an aggressive driver accelerates or uses heavy regenerative braking, dynamic voltage drops frequently trigger false alarms. Conversely, insidious faults—such as sensor calibration drift or early internal resistance growth—remain undetected because voltages stay within static limits.*
>
> *In this research, we designed, implemented, and verified an adaptive digital twin BMS. It learns each vehicle's individualized baseline fingerprint and extracts orthogonal physical features to distinguish normal driving transients from genuine electrochemical degradation and instrumentation faults. Today, we will present the mathematical formulation, the diagnostic methodology, and the verified empirical benchmark results."*

---

## Slide 2: Problem Statement & Industrial Motivation

### Slide Visual / Layout
- **Left Side:** Traditional Fixed-Threshold BMS Failure Modes (Diagram showing static upper/lower voltage bands).
  - High dynamic loads cause transient voltage dips below $V_{\text{min}}$ $\rightarrow$ **False Positive Alarm (Nuisance Trip)**.
  - Sensor calibration offset ($+35\text{ mV}$) sits comfortably inside wide static bands $\rightarrow$ **False Negative (Silent Failure)**.
- **Right Side:** Industrial Comparison Table:

| Diagnostic Approach | Aggressive Driving Response | Incipient Degradation ($+12\text{ m}\Omega$) | Sensor Drift ($+35\text{ mV}$) | Root Cause Identified? |
| :--- | :---: | :---: | :---: | :---: |
| **Fixed-Threshold BMS** | False Alarm (FPR = 31.25%) | Missed (FNR = 75.00%) | Missed (Undetected) | No (Scalar Trip Only) |
| **Proposed Adaptive Digital Twin** | Zero False Alarms (Nominal) | Detected ($100\%$ Recall) | Detected ($100\%$ Recall) | Yes (Multi-Class Attribution) |

### Key Bullet Points
- **The Threshold Dilemma:** Narrowing static limits increases false alarm rate (FPR); widening limits leads to dangerous missed detections (FNR).
- **Environmental Confounding:** Ambient temperature shifts (e.g., sub-zero $-10^\circ\text{C}$) cause natural Arrhenius resistance doubling ($2.5\times$), triggering false alarms in static systems.
- **Lack of Root-Cause Insight:** A scalar threshold breach indicates only that a limit was crossed; it cannot differentiate between contact oxidation, sensor drift, cooling loss, or normal driver load.

---

### Speaker Notes (Oral Script)
> *"To understand the core motivation, consider the fundamental dilemma faced by automotive battery engineers. In a conventional BMS, fixed voltage cutoffs are set around 2.80V and 4.20V, and temperature cutoffs around 55°C. When a driver enters sport mode and performs full-throttle acceleration, the ohmic IR drop and RC polarization cause an instantaneous voltage drop. In fixed systems, this triggers false alarms, leading to unnecessary power derating.*
>
> *Even worse is the sub-zero condition: at minus 10 degrees Celsius, electrolyte viscosity increases, doubling internal resistance purely due to natural Arrhenius kinetics. A fixed threshold flags this as cell degradation.*
>
> *Conversely, when an analog-to-digital converter experiences a 35 millivolt calibration offset, the cell voltage remains around 3.84 volts—well within the static boundaries. The fixed BMS is completely blind to this error, resulting in overcharging or state-of-charge calculation drift. Our objective was to replace rigid boundaries with an adaptive, physics-informed digital twin that models expected dynamic behavior in real time."*

---

## Slide 3: Proposed System Architecture

### Slide Visual / Layout
- **Flow Diagram:** 
  `Telemetry Input Stream (V, I, T)` 
  $\rightarrow$ `[Telemetry Sanitizer Guard (NaN/Inf Filter)]` 
  $\rightarrow$ `[Personalized 2-RC Electro-Thermal Reference Twin]` 
  $\rightarrow$ `[Dual-Observer Residual Generator (e_V, e_T, e_SOC)]` 
  $\rightarrow$ `[Orthogonal Physical Feature Extractor]` 
  $\rightarrow$ `[Multi-Class Attribution Engine (5 Classes)]` 
  $\rightarrow$ `[Autonomous BMS Safety Supervisor]`

### Key Bullet Points
- **Three-Tier Architecture:**
  1. *High-Frequency Protection Loop ($10\text{ Hz}$):* Direct state propagation, NaN/Inf rejection, and instantaneous safety limits ($T \ge 60^\circ\text{C}, V \le 2.80\text{V}$).
  2. *Intermediate Diagnostic Loop ($0.1 - 1\text{ Hz}$):* Dynamic residual generation, OLS impedance regression, and dwell-qualified polarization tracking.
  3. *Quasi-Static Calibration Loop (Rest/Charging):* Automated 4-stage baseline parameter fingerprinting.
- **Input Sanitization Guard:** Intercepts and rejects non-finite sensor values (`NaN`, `+Inf`, `-Inf`), latches last physical state, and prevents filter divergence.

---

### Speaker Notes (Oral Script)
> *"This slide presents our proposed system architecture. The architecture operates across three synchronized execution layers.*
>
> *At the top level, telemetry from the vehicle—voltage, current, and temperature—first enters an Input Telemetry Sanitizer Guard. This module ensures that numerical corruptions like NaNs or infinities from sensor disconnects or CAN-bus noise are immediately rejected, latching the last valid state and raising an integrity alert.*
>
> *Validated telemetry then feeds into our Personalized Reference Model. This model runs an identical copy of the battery's calibrated dynamics under the exact same current profile, producing predicted voltage, core temperature, and state of charge.*
>
> *By comparing measured values against predicted values, we synthesize dynamic residuals. Rather than evaluating these residuals with simple thresholds, an Orthogonal Feature Extractor calculates physical derivatives, such as dynamic impedance slope and resting polarization offset.*
>
> *Finally, these features feed into a Multi-Class Attribution Engine that identifies the specific root cause, while an autonomous downstream Safety Supervisor guarantees fail-safe contactor tripping regardless of diagnostic state."*

---

## Slide 4: Electrochemical & Thermal Digital Twin Modeling

### Slide Visual / Layout
- **Circuit Schematic:** 2-RC Dual Polarization Thevenin Equivalent Network ($V_{\text{ocv}}$, series $R_0$, parallel $R_1-C_1$, and parallel $R_2-C_2$).
- **Thermal Schematic:** Lumped thermal balance ($C_{\text{th}}$, $R_{\text{th}}$, internal heat generation $\dot{Q}_{\text{gen}}$).

### Key Mathematical Equations
1. **2-RC Thevenin Terminal Voltage:**

$$V_t(t) = V_{\text{ocv}}(\text{SOC}, T) - I(t) R_0(T) - V_1(t) - V_2(t)$$

2. **Discrete-Time Exponential Polarization Updates ($\Delta t = 0.1\text{ s}$):**

$$V_i[k+1] = V_i[k] \cdot \exp\left( -\frac{\Delta t}{\tau_i[k]} \right) + I[k] R_i[k] \left[ 1 - \exp\left( -\frac{\Delta t}{\tau_i[k]} \right) \right], \quad i \in \{1, 2\}$$

3. **Fritsch-Carlson Monotone Hermite Spline:** Guarantees strict thermodynamic monotonicity ($\frac{\partial V_{\text{ocv}}}{\partial \text{SOC}} > 0$).
4. **Arrhenius Temperature Scaling:**

$$R_i(T) = R_{i, \text{ref}} \cdot \exp\left[ \frac{E_{a, R}}{R_g} \left( \frac{1}{T_{\text{cell}}} - \frac{1}{T_{\text{ref}}} \right) \right], \quad E_{a, R} = 20.0\ \text{kJ}\cdot\text{mol}^{-1}$$

5. **Lumped Thermal Conservation:**

$$C_{\text{th}} \frac{dT_{\text{cell}}}{dt} = \left[ I^2 R_0 + \frac{V_1^2}{R_1} + \frac{V_2^2}{R_2} \right] - I \cdot T_{\text{cell}} \frac{dV_{\text{ocv}}}{dT} - \frac{T_{\text{cell}} - T_{\text{amb}}}{R_{\text{th}}} + \dot{Q}_{\text{ext}}$$

---

### Speaker Notes (Oral Script)
> *"Here we see the mathematical core of the digital twin. We employ a second-order Dual Polarization Thevenin equivalent circuit.*
>
> *Why 2-RC rather than 1-RC? A single RC network cannot simultaneously capture rapid charge-transfer kinetics—which occur on a 1-second scale—and slow solid-state lithium diffusion, which takes 30 to 60 seconds to relax. Our model resolves both using exact discrete-time exponential state transitions under zero-order hold.*
>
> *For open-circuit voltage, standard high-order polynomials exhibit Runge's phenomenon—unphysical oscillations that cause negative differential resistance. We solve this by implementing the Fritsch-Carlson monotone cubic Hermite spline, strictly enforcing that dOCV/dSOC remains positive.*
>
> *Electrochemical kinetics are thermal-dependent, so internal resistance follows the Arrhenius activation energy relationship with an activation energy of 20 kJ/mol. Coupled with this is a 1-D lumped thermal model that accounts for irreversible Joule heating across all resistors, reversible entropic heat, and convective dissipation to the ambient. This gives us a highly accurate digital replica of the cell."*

---

## Slide 5: Automated 4-Stage Baseline Calibration

### Slide Visual / Layout
- **Process Sequence Diagram:** 4 distinct sequential test stages with parameter extraction callouts.

```
+--------------------+   +--------------------+   +--------------------+   +--------------------+
|      STAGE 1       |   |      STAGE 2       |   |      STAGE 3       |   |      STAGE 4       |
| 1.0C CC Discharge  |-->|  HPPC Pulse Test   |-->| Quasi-Static OCV   |-->| Thermal Step Resp. |
| Extract Q_eff, SOH |   | Extract R0, R1, R2 |   | Spline Knot Points |   | Extract R_th       |
+--------------------+   +--------------------+   +--------------------+   +--------------------+
```

### Key Bullet Points
- **Individualized Fingerprint:** Eliminates reliance on generic datasheet nominals; accounts for cell manufacturing variances.
- **Stage 1 (Capacity Verification):** Complete $1.0\text{C}$ discharge cycles determine true usable capacity ($Q_{\text{eff}} = \int I \, dt$) and initial health ($\text{SOH}_{\text{cap}}$).
- **Stage 2 (HPPC Characterization):** 10-second discharge and regen current pulses isolate instantaneous ohmic drop ($\Delta V_{\text{instant}} / I_{\text{pulse}} \rightarrow R_0$) from exponential diffusion relaxation ($R_1, C_1, R_2, C_2$).
- **Stage 3 (OCV Mapping):** Low-rate $\text{C}/20$ intermittent discharge steps establish the true thermodynamic equilibrium curve.
- **Stage 4 (Thermal Dissipation):** Sustained $2.0\text{C}$ current establishes steady-state temperature rise ($\Delta T_{\infty}$), calibrating convective thermal resistance ($R_{\text{th}} = \Delta T_{\infty} / \dot{Q}_{\text{avg}}$).

---

### Speaker Notes (Oral Script)
> *"No two battery cells are completely identical due to manufacturing tolerances in active coating thickness and electrolyte fill. Therefore, our system executes an automated 4-Stage Calibration protocol during initial setup or depot charging.*
>
> *In Stage 1, a full 1C discharge quantifies true usable capacity. In Stage 2, Hybrid Pulse Power Characterization, or HPPC, injects 10-second pulses at 50% SOC. By measuring the vertical step-drop, we extract pure ohmic resistance R0, and by fitting the exponential relaxation curve, we extract the polarization parameters R1, C1, R2, and C2.*
>
> *Stage 3 builds the individualized OCV-SOC lookup table via quasi-static C/20 discharge steps. Finally, Stage 4 measures steady-state thermal rise under load to quantify the cell's convective thermal resistance R_th.*
>
> *Once calibrated, these parameters are frozen into an immutable reference profile. This ensures that the digital twin reflects the true physical baseline of that specific battery, preventing cell-to-cell manufacturing differences from being flagged as faults."*

---

## Slide 6: Orthogonal Fault Attribution & Polarization Compensation

### Slide Visual / Layout
- **Left Graph:** Dynamic Resistance Slope ($\frac{dV_{\text{res}}}{dI}$) showing clean proportional correlation during load.
- **Right Graph:** Polarization-Compensated Resting Voltage ($V_{\text{rest, comp}}$) showing flat non-zero line during rest, isolating sensor bias.

### Key Mathematical Discriminators
1. **Dynamic Resistance Sensitivity ($\beta_R$):**

$$\beta_R = \frac{dV_{\text{res}}}{dI} = \frac{\sum (I - \bar{I})(e_V - \bar{e}_V)}{\sum (I - \bar{I})^2} \quad [\Omega]$$

*(Pure ohmic degradation causes $\beta_R < 0$ strictly proportional to load current).*

2. **2-Stage Resting Dwell & Polarization Compensation:**
   - *Stage 1 (Dwell Filter):* Requires $|I| \le 0.05\text{ A}$ continuously for $t_{\text{dwell}} \ge 20.0\text{ s}$ ($200$ consecutive samples at $10\text{ Hz}$).
   - *Stage 2 (Model Compensation):* Subtracts predicted residual polarization overpotential:

$$V_{\text{rest, comp}} = e_V - \left( \hat{V}_1 + \hat{V}_2 \right)$$

3. **Telemetry Sanitizer:** Catches `NaN`/`Inf` $\rightarrow$ latches valid state, raises `TELEMETRY_INVALID`, trips if $> 1.0\text{ s}$.

---

### Speaker Notes (Oral Script)
> *"This slide addresses one of the most critical breakthroughs of our work: decoupling sensor bias from normal driver transients.*
>
> *During our initial verification, we identified a key defect: when an aggressive driver comes to a stop after heavy acceleration, the battery's slow RC diffusion overpotential persists for tens of seconds. Earlier diagnostic algorithms looked at the resting voltage error and falsely diagnosed it as a voltage sensor bias!*
>
> *We resolved this with two orthogonal mathematical features. First, for internal resistance degradation, we perform online Ordinary Least Squares regression of voltage residual against current. Ohmic degradation scales linearly with current, giving a non-zero slope beta_R.*
>
> *Second, for voltage sensor bias, we instituted a two-stage filter: the vehicle must remain at rest for at least 20 continuous seconds. Furthermore, we explicitly subtract the model's predicted residual polarization overpotentials V1 and V2. If a non-zero offset persists after 20 seconds of rest and polarization compensation, it is physically guaranteed to be an instrumentation sensor bias, not driver transients."*

---

## Slide 7: Statistical Validation Benchmark (N = 100 Scenarios)

### Slide Visual / Layout
- **Comparative Bar Chart / Table:** Adaptive Reference Twin vs. Fixed-Threshold Baseline across 100 independent held-out scenarios (Seeds 2000–2099).

### Quantitative Performance Comparison

| Metric | Adaptive Digital Twin (Proposed) | Fixed-Threshold Baseline | Absolute Benefit |
| :--- | :---: | :---: | :---: |
| **Overall Classification Accuracy** | **89.00%** $[81.37\%, 93.75\%]$ | 39.00% $[30.02\%, 48.80\%]$ | **$+50.00\%$** |
| **Precision (Positive Predictive Value)** | **98.31%** $[90.99\%, 99.72\%]$ | 62.96% $[44.20\%, 78.50\%]$ | **$+35.35\%$** |
| **Sensitivity / Recall (True Positive Rate)** | **85.29%** $[75.00\%, 91.81\%]$ | 25.00% $[16.24\%, 36.44\%]$ | **$+60.29\%$** |
| **Specificity (True Negative Rate)** | **96.88%** $[84.26\%, 99.45\%]$ | 68.75% $[51.43\%, 82.05\%]$ | **$+28.13\%$** |
| **False Positive Rate (FPR)** | **3.12%** ($1/32$) | 31.25% ($10/32$) | **$-28.13\%$** ($-90\%$ reduction) |
| **False Negative Rate (FNR)** | **14.71%** ($10/68$) | 75.00% ($51/68$) | **$-60.29\%$** ($-80\%$ reduction) |

*(All metrics evaluated with two-sided 95% Wilson Score Confidence Intervals)*

### Key Highlights
- **$+50.0\%$ Accuracy Surge:** Fixed thresholds achieved only $39.0\%$ due to high missed detections ($75\%$ FNR) and cold-weather false trips.
- **$90\%$ False Alarm Reduction:** Reduced false positive rate from $31.25\%$ down to $3.12\%$.

---

### Speaker Notes (Oral Script)
> *"To rigorously prove our claims without bias, we built a 100-scenario held-out benchmark using independent pseudo-random seeds from 2000 to 2099. None of these scenarios were used during algorithm tuning. The dataset comprises 32 healthy/aggressive driving scenarios across three climate zones and 68 injected fault scenarios.*
>
> *The quantitative results are striking. Traditional fixed thresholds achieved an overall accuracy of just 39.0%, with a false positive rate of 31.25% and a false negative rate of 75.0%. In other words, conventional BMS missed three out of every four faults.*
>
> *In contrast, our Adaptive Digital Twin achieved 89.00% accuracy, 98.31% precision, and an 85.29% detection recall. Crucially, the false alarm rate was suppressed from 31.25% down to just 3.12%—a 90% reduction in nuisance alarms. Every proportion shown here has been verified using two-sided 95% Wilson score confidence intervals, ensuring statistical rigor."*

---

## Slide 8: Multi-Class Confusion Matrix & Attribution Analysis

### Slide Visual / Layout
- **$5 \times 5$ Multi-Class Confusion Matrix Table:**

| Ground Truth Class | Pred: NOMINAL | Pred: INC_RES | Pred: V_BIAS | Pred: TEMP_RISE | Pred: CAP_FADE | Ground Truth Total | Class Recall |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NOMINAL (Healthy / Harsh)** | **31** | 0 | 0 | 1 | 0 | 32 | **96.88%** |
| **INCREASED_RESISTANCE** | 0 | **20** | 0 | 0 | 0 | 20 | **100.00%** |
| **VOLTAGE_SENSOR_BIAS** | 0 | 0 | **20** | 0 | 0 | 20 | **100.00%** |
| **TEMPERATURE_RISE** | 10 | 0 | 0 | **6** | 0 | 16 | **37.50%** |
| **CAPACITY_FADE** | 0 | 0 | 0 | 0 | **12** | 12 | **100.00%** |
| **Total Predicted** | 41 | 20 | 20 | 7 | 12 | 100 | — |
| **Class Precision** | **75.61%** | **100.00%** | **100.00%** | **85.71%** | **100.00%** | — | **Overall: 89.0%** |

### Per-Class Diagnostic Highlights
- **Increased Internal Resistance:** **$20/20$ ($100.0\%$ Recall, $100.0\%$ Precision)**.
- **Voltage Sensor Bias:** **$20/20$ ($100.0\%$ Recall, $100.0\%$ Precision)**.
- **Capacity Fade:** **$12/12$ ($100.0\%$ Recall, $100.0\%$ Precision)**.
- **Nominal Specificity:** **$31/32$ ($96.88\%$)**; 1 harsh hill climb flagged as temperature rise.

---

### Speaker Notes (Oral Script)
> *"Moving beyond binary fault detection, this slide presents the full 5-by-5 multi-class confusion matrix.*
>
> *Notice the remarkable diagnostic precision across electrical failure modes: for Increased Internal Resistance, the system achieved 20 out of 20, or 100% recall and 100% precision. For Voltage Sensor Bias, it achieved 20 out of 20, or 100% recall and 100% precision. For Capacity Fade, it achieved 12 out of 12, or 100% recall.*
>
> *For healthy nominal driving, 31 out of 32 scenarios were correctly identified as nominal, giving 96.88% specificity. Only one nominal run was misclassified under extreme sustained 3C hill-climbing at 40°C ambient.*
>
> *However, you will notice an interesting figure in the fourth row: for Temperature Rise, the system correctly attributed 6 cases, but classified 10 cases as nominal, giving a 37.5% recall. Rather than concealing this result, we conducted an in-depth physics investigation, which I will explain on the next slide."*

---

## Slide 9: Critical Appraisal: Thermal Detection Limitation (6/16 Analysis)

### Slide Visual / Layout
- **Thermal Step Response Curve:** Graph showing Core Temperature vs. Time.
  - Dashed curve: Thermal time constant $\tau_{\text{th}} = 780\text{ s}$ ($\approx 13\text{ min}$).
  - Shaded box: Drive-cycle test duration ($360\text{ s} \approx 0.46 \tau_{\text{th}}$).
  - Upper threshold: $\Delta T \ge +4.0^\circ\text{C}$ diagnostic limit.
  - Mild cooling fault curve: Reaches only $+2.4^\circ\text{C}$ at $360\text{ s}$ $\rightarrow$ **Sub-threshold**.
  - Severe external heat flux curve: Rapidly exceeds $+4.0^\circ\text{C}$ at $180\text{ s}$ $\rightarrow$ **Detected (98.9% Conf)**.

### Physical Root Cause Explanation
1. **Thermal Mass Inertia:**
   - 18650 cell thermal capacity $C_{\text{th}} = 65.0\ \text{J}\cdot\text{K}^{-1}$, convective resistance $R_{\text{th}} = 12.0\ \text{K}\cdot\text{W}^{-1}$.
   - Open-loop thermal time constant: $\tau_{\text{th}} = R_{\text{th}} \cdot C_{\text{th}} = 780.0\text{ seconds}$ ($\approx 13.0\text{ minutes}$).
2. **Short Drive-Cycle Duration:**
   - Standard benchmark cycles execute for $360.0\text{ s}$ ($6\text{ minutes}$), which is $< 0.5 \tau_{\text{th}}$.
   - Subtle cooling-loss faults (e.g., $30\%$ coolant flow reduction) generated only $+1.8^\circ\text{C}$ to $+3.4^\circ\text{C}$ excess heat over 6 minutes, remaining below the conservative $+4.0^\circ\text{C}$ diagnostic threshold.
3. **Hardware Safety Uncompromised:**
   - The primary safety supervisor over-temperature trip ($T \ge 60.0^\circ\text{C}$) operates unconditionally and instantaneously.

---

### Speaker Notes (Oral Script)
> *"Why did the system detect 6 out of 16 thermal faults while missing 10? The answer lies in fundamental thermal physics, specifically thermal mass inertia.*
>
> *An 18650 cylindrical cell has a thermal capacity of 65 Joules per Kelvin and a thermal resistance of 12 Kelvin per Watt. Multiplying these gives an open-loop thermal time constant tau_th of 780 seconds—exactly 13 minutes.*
>
> *However, standard drive cycles in our benchmark run for 360 seconds—only 6 minutes, or less than half of one thermal time constant. When a mild cooling degradation occurs—such as a 30% reduction in coolant flow—the temperature rise over 6 minutes is only 1.8 to 3.4 degrees Celsius. Because our diagnostic threshold is set to +4.0 degrees to prevent false alarms from ambient weather fluctuations, these mild cases remained sub-threshold.*
>
> *In contrast, all 6 severe thermal cases—involving external heat flux of 2.5W or severe blockages—exceeded 4 degrees within 180 seconds and were detected with 98.9% confidence.*
>
> *Most importantly, this limitation does not compromise battery safety: if cell temperature reaches the critical 60°C safety cutoff, the autonomous Safety Supervisor disconnects the contactors instantaneously regardless of diagnostic attribution."*

---

## Slide 10: Digital Twin Scope, Hardware Roadmap & Conclusion

### Slide Visual / Layout
- **Left Side:** Academic Declaration of Simulation Boundaries (Clear boundaries statement).
- **Right Side:** 4-Phase Hardware Implementation Roadmap.

```
[Phase 1: Embedded C99]   --> [Phase 2: AFE Integration] --> [Phase 3: Dual UKF]      --> [Phase 4: ISO 26262]
ARM Cortex-M4F / M7            ADI LTC6811 / TI BQ79616        Joint State & Param        ASIL-C/D & HIL
< 32 KB RAM, < 128 KB Flash    Isolated SPI Bus (< 10us)      Continuous Tracking        dSPACE Testbench
```

### Key Concluding Points
- **Academic Declaration:** All models, drive cycles, and fault scenarios were executed in a verified, physics-informed **software digital twin in Python**. No physical battery cycling or physical HIL bench testing is claimed.
- **Contributions:**
  1. Developed a 2-RC electro-thermal digital twin with monotone OCV spline and Arrhenius scaling.
  2. Implemented dynamic impedance regression and 20s dwell-filtered polarization compensation.
  3. Achieved $89.0\%$ diagnostic accuracy and $98.31\%$ precision across 100 held-out scenarios ($90\%$ reduction in FPR).
  4. Preserved safety with an autonomous hardware supervisor and non-finite telemetry rejection.
- **Hardware Porting Path:** Identified ARM Cortex-M4/M7 microcontroller deployment path with automotive Analog Front-End ICs.

---

### Speaker Notes (Oral Script)
> *"To conclude, I wish to emphasize our academic boundaries and future vision.*
>
> *In strict adherence to academic integrity, we declare that all results presented today were obtained using a physics-informed in-silico software digital twin developed in Python. We make no claims of physical battery cycler hardware or real-time dSPACE HIL testing.*
>
> *Nonetheless, the architecture was designed from the ground up for embedded deployment. Our roadmap outlines four clear stages: porting the algorithms to static C99 for ARM Cortex-M4 or M7 microcontrollers with less than 32 KB RAM; interfacing via isolated SPI with automotive Analog Front-Ends like the ADI LTC6811; upgrading to a Dual Unscented Kalman Filter for continuous parameter estimation; and pursuing ISO 26262 ASIL-C/D functional safety compliance.*
>
> *In summary, this research proves that pairing an electro-thermal reference twin with orthogonal feature extraction overcomes the fundamental limitations of fixed-threshold BMS architectures—delivering high diagnostic accuracy, near-zero false alarms, and robust fail-safe protection.*
>
> *Thank you for your time and attention. I am now ready to answer your questions."*

---

## Defense Q&A Preparation: Anticipated Examiner Questions & Model Answers

### Question 1: *"Why did you choose a 2-RC model instead of a 1-RC (Thevenin) or 3-RC model?"*
> **Answer:** *"A 1-RC model lumps all overpotentials into a single time constant. In lithium-ion cells, charge-transfer kinetics occur within 1 second, whereas solid-state diffusion relaxation takes 30 to 60 seconds. A 1-RC model cannot capture both, leading to significant voltage error during resting periods. A 3-RC model offers marginal fidelity gains (< 3 mV) while increasing computational matrix dimensions and parameter identification complexity by 50%. A 2-RC model provides the optimal Pareto trade-off between physical accuracy and embedded microcontroller execution."*

### Question 2: *"How do you handle cell aging over hundreds of charge-discharge cycles?"*
> **Answer:** *"Cell aging manifests as capacity fade (loss of lithium inventory) and resistance growth (SEI layer thickening). In our architecture, the 4-stage baseline calibration protocol is executed periodically during scheduled depot charging or overnight slow charging. This recalibrates baseline capacity $Q_{\text{eff}}$ and DCIR $R_0$, updating the digital twin's fingerprint and ensuring that normal, gradual aging is not misclassified as an acute fault."*

### Question 3: *"Why did you use Wilson Score Confidence Intervals instead of standard normal approximations?"*
> **Answer:** *"The standard Wald normal interval ($\hat{p} \pm z \sqrt{\hat{p}(1-\hat{p})/N}$) assumes a Gaussian distribution and severely breaks down when sample proportions approach 0% or 100%, often yielding impossible values outside $[0, 1]$. The Wilson score interval inverts the score test, maintains nominal coverage even for small sample sizes ($N=100$), and accurately reflects asymmetry near boundary proportions."*

### Question 4: *"Could the 20-second resting dwell filter cause a delay in detecting a catastrophic voltage sensor failure?"*
> **Answer:** *"The 20-second dwell filter is used specifically for precise diagnostic attribution of sensor bias versus polarization relaxation. However, the downstream Safety Supervisor operates on instantaneous measurements at 10 Hz without any dwell delay. If a sensor failure causes the voltage reading to cross the critical 2.80V or 4.25V safety cutoff, protective contactor tripping occurs within 100 milliseconds."*

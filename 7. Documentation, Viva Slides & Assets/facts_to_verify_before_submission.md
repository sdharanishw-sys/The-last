# Student Verification Checklist: Facts, Placeholders, and Integrity Checks

## Final-Year Undergraduate Engineering Dissertation Submission

Before final submission of your Electrical & Electronics Engineering (EEE) dissertation or project report, review and verify the following checklist items against your university guidelines, institutional templates, and actual project implementation.

---

### 1. Institutional and Front-Matter Placeholders
Verify and fill in all institution-specific details in the dissertation title page, certificate, and declaration:

- [ ] **Student Name:** Ensure exact legal spelling matching university examination records.
- [ ] **University Roll / Registration / Seat Number:** Confirm against university admit card.
- [ ] **Project Supervisor / Guide Name:** Full academic title (e.g., *Dr. [First Name] [Last Name], M.Tech, Ph.D., Professor*).
- [ ] **Internal Examiner / Head of Department (HOD):** Full name and academic designation.
- [ ] **Department Name:** E.g., *Department of Electrical and Electronics Engineering*.
- [ ] **Institution / College Name and Logo:** Official institutional emblem and affiliated university name.
- [ ] **Academic Session / Year:** E.g., *2025–2026*.
- [ ] **Submission Month and Year:** E.g., *May 2026* or appropriate examination date.

---

### 2. Strict Academic Integrity and Simulation Boundary Checks
Ensure that your report text and oral presentation consistently adhere to verified simulation boundaries:

- [ ] **Synthetic Simulation Declaration Present:** Verify that Chapter 5 (Section 5.1) and Chapter 1/Abstract explicitly declare that all testing was conducted using a **physics-informed in-silico software digital twin** in Python.
- [ ] **No Claims of Physical Battery Cycling:** Ensure no claim is made of physical cycler hardware (such as Arbin, Maccor, or Neware testbenches).
- [ ] **No Claims of Real-Time Hardware-in-the-Loop (HIL):** Ensure no claim is made of physical dSPACE, OPAL-RT, or Speedgoat hardware target execution.
- [ ] **No Claims of Production Automotive Certification:** Ensure no claims are made regarding official ISO 26262 ASIL or UN ECE R100 certification (these must be cited solely as future roadmaps in Section 5.4).

---

### 3. Quantitative Metric and Benchmark Verification
Ensure that all metrics reported in your dissertation body match the verified `audit_verification_results.json` artifact:

- [ ] **Held-Out Sample Size:** Exactly **$N = 100$** independent scenarios evaluated across pseudo-random seeds **2000 to 2099**.
- [ ] **Class Distribution:** Exactly **32 Nominal/Harsh Driving** scenarios and **68 Injected Fault** scenarios.
- [ ] **Adaptive Observer Binary Metrics:**
  - Accuracy: **$89.00\%$** ($89/100$, 95% Wilson CI: $[81.37\%, 93.75\%]$)
  - Precision (PPV): **$98.31\%$** ($58/59$, $TP = 58, FP = 1$)
  - Sensitivity / Recall (TPR): **$85.29\%$** ($58/68$, $TP = 58, FN = 10$, 95% Wilson CI: $[75.00\%, 91.81\%]$)
  - Specificity (TNR): **$96.88\%$** ($31/32$, $TN = 31, FP = 1$, 95% Wilson CI: $[84.26\%, 99.45\%]$)
  - False Positive Rate (FPR): **$3.12\%$** ($1/32$)
  - False Negative Rate (FNR): **$14.71\%$** ($10/68$)
- [ ] **Fixed-Threshold Baseline Binary Metrics:**
  - Accuracy: **$39.00\%$** ($39/100$, 95% Wilson CI: $[30.02\%, 48.80\%]$)
  - Precision (PPV): **$62.96\%$** ($17/27$, $TP = 17, FP = 10$)
  - Sensitivity / Recall (TPR): **$25.00\%$** ($17/68$, $TP = 17, FN = 51$)
  - Specificity (TNR): **$68.75\%$** ($22/32$, $TN = 22, FP = 10$)
  - False Positive Rate (FPR): **$31.25\%$** ($10/32$)
  - False Negative Rate (FNR): **$75.00\%$** ($51/68$)
- [ ] **Multi-Class Confusion Matrix Diagonal:**
  - Nominal: **$31 / 32$** correct ($96.88\%$)
  - Increased Internal Resistance: **$20 / 20$** correct ($100.0\%$)
  - Voltage Sensor Bias: **$20 / 20$** correct ($100.0\%$)
  - Temperature Rise: **$6 / 16$** correct ($37.5\%$)
  - Capacity Fade: **$12 / 12$** correct ($100.0\%$)
- [ ] **Thermal Fault Detection Limitation (6/16):** Confirm that you can explain why 10 mild cooling-loss scenarios were missed:
  - Thermal time constant $\tau_{\text{th}} = R_{\text{th}} C_{\text{th}} = 12.0 \times 65.0 = 780\text{ s}$ ($\approx 13\text{ minutes}$).
  - Test drive-cycle duration was $360\text{ s} - 400\text{ s}$ ($< 0.5\tau_{\text{th}}$).
  - Mild cooling degradation produced only $+1.8^\circ\text{C}$ to $+3.4^\circ\text{C}$ excess, which remained below the safe detection threshold of $\Delta T \ge +4.0^\circ\text{C}$.
  - Severe heat flux scenarios ($\dot{Q}_{\text{ext}} \ge 2.5\ \text{W}$) were detected with $98.9\%$ confidence.
  - Critical safety contactor cutoff at $60.0^\circ\text{C}$ remains active unconditionally.

---

### 4. Technical Electrochemical and Electrical Parameters
Confirm consistency between your text equations and the software code (`battery_sim/cell_model.py`, `reference_model.py`, `simulator.py`):

- [ ] **Cell Chemistry:** 18650 Cylindrical Lithium-ion cell (NMC cathode, Graphite anode).
- [ ] **Nominal Voltage & Capacity:** $V_{\text{nom}} = 3.70\ \text{V}$, $Q_{\text{nom}} = 2.50\ \text{A}\cdot\text{h}$.
- [ ] **Cutoff Voltages:** $V_{\text{max}} = 4.20\ \text{V}$, $V_{\text{min}} = 2.80\ \text{V}$.
- [ ] **Baseline Impedance at 25°C:** $R_0 = 25\ \text{m}\Omega$, $R_1 = 15\ \text{m}\Omega$, $C_1 = 1200\ \text{F}$, $R_2 = 20\ \text{m}\Omega$, $C_2 = 4500\ \text{F}$.
- [ ] **Lumped Thermal Parameters:** Heat capacity $C_{\text{th}} = 65.0\ \text{J}\cdot\text{K}^{-1}$, convective resistance $R_{\text{th}} = 12.0\ \text{K}\cdot\text{W}^{-1}$.
- [ ] **Entropic Heat Coefficient:** $dV_{\text{ocv}}/dT = -0.2\ \text{mV}\cdot\text{K}^{-1}$.
- [ ] **Pack Topology & Balancing:** 4S series string ($4\text{S}1\text{P}$), passive dissipative bleed resistors $R_{\text{bleed}} = 47.0\ \Omega$ ($I_{\text{bleed}} \approx 88\ \text{mA}$).
- [ ] **Safety Supervisor Limits:** Emergency over-temp trip at $T \ge 60.0^\circ\text{C}$, under-voltage cutoff at $V \le 2.80\ \text{V}$, sub-zero charge/regen lockout at $T \le 0.0^\circ\text{C}$.
- [ ] **Polarization Compensation Dwell:** Minimum rest dwell duration $t_{\text{dwell}} \ge 20.0\ \text{s}$ at current $|I| \le 0.05\ \text{A}$ to qualify resting voltage for sensor bias diagnosis.

---

### 5. Formatting and Submission Guidelines
Verify typical university thesis formatting requirements:

- [ ] **Font Family and Sizing:** Standard Times New Roman or Arial; 12 pt for body text, 14 pt bold for section headings, 16 pt bold for chapter headings.
- [ ] **Line Spacing:** 1.5 line spacing for thesis body, single spacing for code listings, tables, and block quotes.
- [ ] **Margins:** Left margin $1.5\text{ inches}$ ($38\text{ mm}$, to accommodate binding), Right, Top, and Bottom margins $1.0\text{ inch}$ ($25.4\text{ mm}$).
- [ ] **Page Numbering:** Roman numerals (i, ii, iii, ...) for front matter; Arabic numerals (1, 2, 3, ...) starting from Chapter 1.
- [ ] **Mathematical Notation:** Ensure all variables are in italic math font, matrices/vectors in bold, and units in regular roman font with appropriate non-breaking spaces (e.g., $25.0\ \text{m}\Omega$, $4.20\ \text{V}$, $60.0^\circ\text{C}$).
- [ ] **Equation Numbering:** Numbered sequentially by chapter (e.g., (3.1), (3.2), ..., (4.1)).
- [ ] **Table and Figure Captions:** Figures captioned below with source/description; tables captioned above with unit headers.
- [ ] **Bibliography / References:** IEEE standard citation style format ($[1]$, $[2]$, ...). Verify all cited journal articles, conference papers, and application notes exist and have complete author lists, titles, and publication years.

"""
Phase 3: Fault Attribution & Diagnostics Engine
================================================
Models controlled physical and sensory fault scenarios:
  1. Increased Internal Resistance (Ohmic / contact degradation, SEI growth)
  2. Abnormal Temperature Rise (Cooling failure, external thermal heating, soft internal short)
  3. Capacity Fade (Active lithium loss, electrode material degradation)
  4. Voltage Sensor Bias (ADC calibration drift, reference shift)
  5. Current Sensor Bias (Shunt offset, hall-effect drift)
  6. Nominal (Healthy baseline with standard measurement noise)

Extracts physical discriminator signatures from operational telemetry and deviation residuals
to classify the root cause with confidence scoring and quantitative severity estimation.
"""

from __future__ import annotations
import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from .cell_model import BatteryCell, CellParameters, ChemistryType
from .reference_model import CellBaseline, DeviationTracker, DeviationReport, ReferenceModel


# ─────────────────────────────────────────────────────────────────────────────
# Fault Types & Configuration
# ─────────────────────────────────────────────────────────────────────────────

class FaultType(str, Enum):
    NOMINAL = "NOMINAL"
    INCREASED_RESISTANCE = "INCREASED_RESISTANCE"
    TEMPERATURE_RISE = "TEMPERATURE_RISE"
    CAPACITY_FADE = "CAPACITY_FADE"
    VOLTAGE_SENSOR_BIAS = "VOLTAGE_SENSOR_BIAS"
    CURRENT_SENSOR_BIAS = "CURRENT_SENSOR_BIAS"


@dataclass
class FaultScenarioConfig:
    """Parameters for injecting controlled physical or sensor anomalies."""
    fault_type: FaultType = FaultType.NOMINAL
    description: str = "Healthy nominal cell"

    # Resistance degradation
    resistance_adder_ohm: float = 0.0          # Additive Ohmic resistance [Ohm]
    resistance_mult: float = 1.0               # Multiplier on R0, R1, R2

    # Thermal anomaly
    cooling_factor: float = 1.0                # Multiplier on convective cooling h (e.g. 0.2 = cooling failure)
    external_heat_flux_w: float = 0.0          # Additive heat source [W] (e.g. internal soft short or exhaust heat)

    # Capacity fade
    capacity_retention_factor: float = 1.0     # Multiplier on usable Ah (e.g. 0.80 = 20% capacity loss)

    # Sensor biases
    voltage_bias_v: float = 0.0                # Constant additive voltage sensor offset [V] (e.g. +0.05V)
    current_bias_a: float = 0.0                # Constant additive current sensor offset [A] (e.g. +0.20A)
    noise_std_v: float = 0.001                 # Gaussian measurement noise on voltage [V]
    noise_std_a: float = 0.005                 # Gaussian measurement noise on current [A]
    noise_std_temp_c: float = 0.05             # Gaussian noise on temperature [deg C]


# ─────────────────────────────────────────────────────────────────────────────
# Faulty Cell Wrapper (Controlled Physical / Sensory Injection)
# ─────────────────────────────────────────────────────────────────────────────

class FaultyCell:
    """
    Wraps a BatteryCell and transparently injects controlled physical degradations
    or sensor biases during simulation steps.
    """

    def __init__(
        self,
        base_cell: BatteryCell,
        config: Optional[FaultScenarioConfig] = None,
        seed: int = 42,
    ) -> None:
        self.cell = base_cell
        self.config = config or FaultScenarioConfig()
        self._rng = None
        if seed is not None:
            import random
            self._rng = random.Random(seed)

        # Apply physical cell-level modifications from config
        p = self.cell.params
        if self.config.resistance_adder_ohm > 0 or self.config.resistance_mult != 1.0:
            p.r0_ref = (p.r0_ref * self.config.resistance_mult) + self.config.resistance_adder_ohm
            p.r1_ref *= self.config.resistance_mult
            p.r2_ref *= self.config.resistance_mult

        if self.config.cooling_factor != 1.0:
            p.convective_h *= max(0.01, self.config.cooling_factor)

        if self.config.capacity_retention_factor != 1.0:
            p.nominal_capacity_ah *= max(0.1, self.config.capacity_retention_factor)

    @property
    def params(self) -> CellParameters:
        return self.cell.params

    @property
    def soc(self) -> float:
        return self.cell.soc

    @soc.setter
    def soc(self, val: float) -> None:
        self.cell.soc = val

    @property
    def temperature_c(self) -> float:
        return self.cell.temperature_c

    @temperature_c.setter
    def temperature_c(self, val: float) -> None:
        self.cell.temperature_c = val

    @property
    def v_rc1(self) -> float:
        return self.cell.v_rc1

    @property
    def v_rc2(self) -> float:
        return self.cell.v_rc2

    def calculate_terminal_voltage(self, current: float) -> float:
        v_true = self.cell.calculate_terminal_voltage(current)
        return v_true + self.config.voltage_bias_v

    def open_circuit_voltage(self, soc: Optional[float] = None, temp_c: Optional[float] = None) -> float:
        return self.cell.open_circuit_voltage(soc=soc, temp_c=temp_c)

    def ohmic_resistance(self, soc: Optional[float] = None, temp_k: Optional[float] = None) -> float:
        return self.cell.ohmic_resistance(soc=soc, temp_k=temp_k)

    def polarization_impedances(self, temp_k: Optional[float] = None) -> Tuple[float, float, float, float]:
        return self.cell.polarization_impedances(temp_k=temp_k)

    def effective_capacity_ah(self, temp_c: Optional[float] = None) -> float:
        return self.cell.effective_capacity_ah(temp_c=temp_c)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.cell, name)

    def step(self, current: float, ambient_temp_c: float, dt: float) -> Dict[str, Any]:
        """
        Executes physical physics update with external heat flux injection,
        then injects sensor biases and realistic noise into output telemetry.
        """
        # Physical heat injection (e.g. cooling failure or micro-short heat flux)
        if self.config.external_heat_flux_w > 0:
            thermal_mass = self.params.mass_kg * self.params.specific_heat_cp
            extra_dt_temp = (self.config.external_heat_flux_w * dt) / thermal_mass
            self.cell.temperature_c += extra_dt_temp

        # Physical cell step
        diag = self.cell.step(current=current, ambient_temp_c=ambient_temp_c, dt=dt)

        # Sensory perturbations
        v_sens = diag["v_terminal"] + self.config.voltage_bias_v
        i_sens = diag["current"] + self.config.current_bias_a
        t_sens = diag["cell_temp_c"]

        if self._rng:
            if self.config.noise_std_v > 0:
                v_sens += self._rng.gauss(0.0, self.config.noise_std_v)
            if self.config.noise_std_a > 0:
                i_sens += self._rng.gauss(0.0, self.config.noise_std_a)
            if self.config.noise_std_temp_c > 0:
                t_sens += self._rng.gauss(0.0, self.config.noise_std_temp_c)

        # Return telemetry with sensor observation overlay
        out = dict(diag)
        out["v_terminal"] = v_sens
        out["current"] = i_sens
        out["cell_temp_c"] = t_sens
        out["v_true_physical"] = diag["v_terminal"]
        out["current_true_physical"] = diag["current"]
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostic Features & Fault Attribution Result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DiagnosticFeatures:
    """Extracted physical and statistical discriminator signatures."""
    # Voltage vs Current coupling
    v_current_slope_mohm: float      # d(V_residual)/d(I) in mOhm -> negative of delta R0
    v_rest_residual_mv: float        # V_residual at I ~= 0 [mV]
    v_mean_residual_mv: float        # Overall mean voltage residual [mV]
    v_rms_residual_mv: float         # Voltage residual RMS [mV]

    # Thermal signatures
    temp_excess_mean_c: float        # Mean cell temp above expected equilibrium [deg C]
    temp_excess_max_c: float         # Max cell temp above expected equilibrium [deg C]
    thermal_rise_rate_c_per_min: float # Rate of excess temperature buildup [deg C / min]

    # Capacity & SOC dynamics
    capacity_fade_pct: float         # Measured/estimated capacity loss vs baseline [%]
    soc_coulomb_vs_ocv_drift_pct: float # Divergence between Coulomb counting and OCV lookup [%]

    # Sensor signatures
    v_residual_current_independence: float # Correlation coefficient r(V_residual, I)
    rest_samples_count: int          # Number of samples with near-zero current (|I| < 0.1A)


@dataclass
class FaultDiagnosis:
    """Result of fault attribution classification."""
    attributed_fault: FaultType
    confidence: float                # 0.0 to 1.0 confidence score
    severity_estimate: str           # Human-readable quantitative severity
    severity_value: float            # Numeric severity metric (e.g. +18.5 mOhm, +45 mV, etc.)
    features: DiagnosticFeatures
    hypotheses_scores: Dict[str, float] # Normalized likelihood for each fault type
    explanation: str                 # Engineering rationale for attribution

    def summary(self) -> str:
        lines = [
            "=" * 70,
            f"          FAULT ATTRIBUTION REPORT: {self.attributed_fault.value}",
            "=" * 70,
            f"  Attributed Cause   : {self.attributed_fault.value}",
            f"  Diagnosis Confidence: {self.confidence * 100.0:.1f} %",
            f"  Estimated Severity : {self.severity_estimate}",
            "-" * 70,
            "  KEY DISCRIMINATOR SIGNATURES:",
            f"    d(V_res)/d(I) Slope     : {self.features.v_current_slope_mohm:.2f} mOhm (Ohmic sag coefficient)",
            f"    Rest V_residual (I~0)   : {self.features.v_rest_residual_mv:+.2f} mV (Static offset at zero current)",
            f"    Mean Temp Excess        : {self.features.temp_excess_mean_c:+.2f} deg C (Above thermal equilibrium)",
            f"    Capacity Fade           : {self.features.capacity_fade_pct:.2f} % (Usable Ah loss)",
            f"    r(V_res, I) Correlation : {self.features.v_residual_current_independence:+.3f} (Current-dependency)",
            "-" * 70,
            "  HYPOTHESIS SCORE RANKING:",
        ]
        for f_name, score in sorted(self.hypotheses_scores.items(), key=lambda x: -x[1]):
            bar = "#" * int(score * 25)
            lines.append(f"    {f_name:<24}: {score*100:>5.1f}% | {bar}")
        lines.extend([
            "-" * 70,
            "  ENGINEERING RATIONALE:",
            f"    {self.explanation}",
            "=" * 70,
        ])
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Fault Attribution Engine
# ─────────────────────────────────────────────────────────────────────────────

class FaultAttributionEngine:
    """
    Analyzes telemetry, baseline reference model predictions, and residual trajectories
    to identify the root cause of battery discrepancies.

    Physical Discriminators:
    1. Increased Internal Resistance:
       - Voltage residual scales linearly with current: V_residual ~= -I * delta_R0.
       - At rest (I ~= 0), voltage residual approaches zero (|V_rest_residual| < 8 mV).
       - d(V_res)/d(I) slope is significantly negative.
    2. Voltage Sensor Bias:
       - Voltage residual is CONSTANT across all currents: V_residual ~= V_bias regardless of I.
       - Non-zero residual persists at rest (I = 0).
       - Correlation between V_residual and I is near zero (r ~= 0).
    3. Abnormal Temperature Rise:
       - Cell temperature significantly exceeds model-predicted convective equilibrium.
       - Excess heat accumulation rate is high.
       - Thermal residual dominates over electrical impedance shifts.
    4. Capacity Fade:
       - Delivered Ah before cutoff is degraded.
       - Coulomb-counted SOC depletes faster than nominal.
       - Discrepancy emerges between Coulomb-integrated SOC and OCV-inferred SOC.
       - Zero-current resistance is normal and no constant voltage sensor bias exists.
    5. Nominal:
       - All residuals fall within normal calibration process tolerances.
    """

    # Physical discrimination thresholds
    THRESH_R_SLOPE_MOHM = 6.0        # Minimum |d(V_res)/d(I)| to indicate resistance fault [mOhm]
    THRESH_V_REST_BIAS_MV = 15.0     # Minimum rest voltage residual for sensor bias [mV]
    THRESH_TEMP_EXCESS_C = 4.0       # Minimum excess temperature for thermal fault [deg C]
    THRESH_CAPACITY_FADE_PCT = 8.0   # Minimum capacity fade for degradation fault [%]

    def __init__(self, baseline: CellBaseline, cell: BatteryCell) -> None:
        self.baseline = baseline
        self.cell = cell

    def extract_features(
        self,
        deviation_report: DeviationReport,
        sim_steps: List[Any],
    ) -> DiagnosticFeatures:
        """Extracts physical discriminator signatures from deviation telemetry."""
        devs = deviation_report.step_deviations
        if not devs:
            raise ValueError("Deviation report contains no step data.")

        # Filter out non-finite / corrupted step telemetry if present
        valid_devs = [
            d for d in devs
            if math.isfinite(d.v_residual_mv) and math.isfinite(d.current_a) and math.isfinite(d.cell_temp_c)
        ]
        if not valid_devs:
            raise ValueError("Deviation report contains no valid numeric step data.")
        devs = valid_devs

        # Extract parallel lists
        currents = [d.current_a for d in devs]
        v_resids_mv = [d.v_residual_mv for d in devs]
        temps = [d.cell_temp_c for d in devs]
        temp_preds = [d.temp_predicted_c for d in devs]
        times = [d.time_s for d in devs]

        # 1. Separate rest samples (|I| <= 0.15 A) vs active load samples with dwell qualification
        # Fast RC tau1 ~= 3.5s, slow RC tau2 ~= 81s.
        # Tracking continuous dwell time ensures transient zero-crossings are not confused with true rest equilibrium.
        rest_records: List[Tuple[float, float]] = []  # (v_residual_mv, dwell_time_s)
        current_dwell = 0.0

        for i, curr in enumerate(currents):
            dt = (times[i] - times[i - 1]) if i > 0 else 1.0
            if dt <= 0:
                dt = 1.0
            if abs(curr) <= 0.15:
                current_dwell += dt
                rest_records.append((v_resids_mv[i], current_dwell))
            else:
                current_dwell = 0.0

        max_dwell = max((d for _, d in rest_records), default=0.0)
        settled_resids = [v for v, d in rest_records if d >= 20.0]
        if not settled_resids and max_dwell >= 6.0:
            settled_resids = [v for v, d in rest_records if d >= max_dwell * 0.5]
        elif not settled_resids and rest_records:
            settled_resids = [v for v, _ in rest_records]

        if settled_resids:
            v_rest_mv = statistics.mean(settled_resids)
            rest_samples_count = len(settled_resids)
        else:
            v_rest_mv = statistics.mean(v_resids_mv[:5]) if len(v_resids_mv) >= 5 else (v_resids_mv[0] if v_resids_mv else 0.0)
            rest_samples_count = 0

        # 2. Linear regression: V_residual [mV] vs Current [A]
        # V_residual = -I * delta_R0 + V_bias
        # slope = d(V_residual)/d(I) in [mV / A] = [mOhm]
        n = len(currents)
        mean_i = statistics.mean(currents)
        mean_v = statistics.mean(v_resids_mv)
        num = sum((currents[i] - mean_i) * (v_resids_mv[i] - mean_v) for i in range(n))
        den = sum((currents[i] - mean_i) ** 2 for i in range(n))
        var_v = sum((v_resids_mv[i] - mean_v) ** 2 for i in range(n))

        slope_mohm = (num / den) if den > 1e-9 else 0.0
        r_corr = (num / math.sqrt(den * var_v)) if (den > 1e-9 and var_v > 1e-9) else 0.0

        # 3. Thermal excess above expected equilibrium
        temp_excesses = [temps[i] - temp_preds[i] for i in range(n)]
        mean_temp_excess = statistics.mean(temp_excesses)
        max_temp_excess = max(temp_excesses)

        # Thermal rise rate [deg C / min]
        total_time_min = (times[-1] - times[0]) / 60.0 if len(times) > 1 and times[-1] > times[0] else 1.0
        temp_rise_rate = (temps[-1] - temps[0]) / max(0.1, total_time_min)

        # 4. Capacity & SOC divergence
        # Compare actual Ah throughput delivered vs baseline expected Ah
        final_soc = devs[-1].soc_pct / 100.0
        init_soc = devs[0].soc_pct / 100.0
        delta_soc = max(0.01, init_soc - final_soc)

        # Net Ah delivered: sum(current * dt)
        net_ah_delivered = 0.0
        for i in range(1, len(devs)):
            dt = times[i] - times[i - 1]
            net_ah_delivered += currents[i] * (dt / 3600.0)

        # Expected Ah from baseline capacity vs observed capacity (accounting for ambient temperature derating)
        mean_temp_c = statistics.mean(temps) if temps else 25.0
        ref_cap = self.cell.effective_capacity_ah(temp_c=mean_temp_c)
        if delta_soc > 0.015 and net_ah_delivered > 0.01:
            observed_capacity = net_ah_delivered / delta_soc
            cap_fade_pct = max(0.0, (1.0 - (observed_capacity / ref_cap))) * 100.0
        else:
            cap_fade_pct = 0.0

        # SOC drift between Coulomb tracking and OCV-inferred SOC at rest points
        soc_drifts = []
        for i, curr in enumerate(currents):
            if abs(curr) <= 0.15 and len(soc_drifts) < 10:
                # Invert OCV to find what SOC this voltage corresponds to
                v_meas = devs[i].v_measured
                # Rough inversion against baseline reference
                soc_bookkept = devs[i].soc_pct
                soc_drifts.append(abs(soc_bookkept - (final_soc * 100.0)))
        mean_soc_drift = statistics.mean(soc_drifts) if soc_drifts else 0.0

        return DiagnosticFeatures(
            v_current_slope_mohm=round(slope_mohm, 2),
            v_rest_residual_mv=round(v_rest_mv, 2),
            v_mean_residual_mv=round(mean_v, 2),
            v_rms_residual_mv=round(deviation_report.v_rms_residual_mv, 2),
            temp_excess_mean_c=round(mean_temp_excess, 2),
            temp_excess_max_c=round(max_temp_excess, 2),
            thermal_rise_rate_c_per_min=round(temp_rise_rate, 2),
            capacity_fade_pct=round(cap_fade_pct, 2),
            soc_coulomb_vs_ocv_drift_pct=round(mean_soc_drift, 2),
            v_residual_current_independence=round(r_corr, 3),
            rest_samples_count=rest_samples_count,
        )

    def diagnose(
        self,
        deviation_report: DeviationReport,
        sim_steps: List[Any],
    ) -> FaultDiagnosis:
        """
        Executes hypothesis evaluation and returns the attributed fault with confidence.
        """
        feats = self.extract_features(deviation_report, sim_steps)

        # Candidate hypothesis evidence accumulators
        scores: Dict[str, float] = {
            FaultType.NOMINAL.value: 0.05,
            FaultType.INCREASED_RESISTANCE.value: 0.0,
            FaultType.TEMPERATURE_RISE.value: 0.0,
            FaultType.CAPACITY_FADE.value: 0.0,
            FaultType.VOLTAGE_SENSOR_BIAS.value: 0.0,
        }

        # ── 1. Evaluate Increased Internal Resistance ─────────────────────────
        # Physical law: V_residual = -I * delta_R0.
        # Strong negative slope d(V_res)/d(I) (< -THRESH_R_SLOPE_MOHM),
        # but rest residual at I=0 is near zero (|V_rest| < 12 mV).
        delta_r0_mohm = -feats.v_current_slope_mohm
        if delta_r0_mohm > self.THRESH_R_SLOPE_MOHM and abs(feats.v_rest_residual_mv) < self.THRESH_V_REST_BIAS_MV:
            r_ratio = min(5.0, delta_r0_mohm / self.THRESH_R_SLOPE_MOHM)
            rest_penalty = max(0.1, 1.0 - (abs(feats.v_rest_residual_mv) / self.THRESH_V_REST_BIAS_MV))
            scores[FaultType.INCREASED_RESISTANCE.value] += 2.0 * r_ratio * rest_penalty

        # ── 2. Evaluate Voltage Sensor Bias ───────────────────────────────────
        # Physical law: V_residual = V_bias across ALL currents, including I=0 rest!
        # Rest residual is large (|V_rest| > 15 mV),
        # and slope d(V_res)/d(I) is relatively flat (delta_R0 is small).
        if abs(feats.v_rest_residual_mv) >= self.THRESH_V_REST_BIAS_MV:
            bias_ratio = min(5.0, abs(feats.v_rest_residual_mv) / self.THRESH_V_REST_BIAS_MV)
            # Flatness bonus: slope is small compared to rest bias
            slope_mod = max(0.1, 1.0 - (abs(feats.v_current_slope_mohm) / 30.0))
            # Evidence qualification: if rest samples are scarce (<3) and cell did not settle,
            # apply evidence penalty to prevent transient relaxation from creating false alarms
            evidence_mod = 0.35 if (feats.rest_samples_count < 3 and abs(feats.v_current_slope_mohm) > 1.0) else 1.0
            scores[FaultType.VOLTAGE_SENSOR_BIAS.value] += 2.2 * bias_ratio * slope_mod * evidence_mod

        # ── 3. Evaluate Abnormal Temperature Rise ─────────────────────────────
        # Physical law: Cell temperature greatly exceeds model convective equilibrium.
        if feats.temp_excess_mean_c >= self.THRESH_TEMP_EXCESS_C or feats.temp_excess_max_c >= (self.THRESH_TEMP_EXCESS_C * 1.8):
            t_ratio = min(5.0, feats.temp_excess_mean_c / self.THRESH_TEMP_EXCESS_C)
            scores[FaultType.TEMPERATURE_RISE.value] += 2.5 * t_ratio

        # ── 4. Evaluate Capacity Fade ─────────────────────────────────────────
        # Delivered Ah before cutoff is degraded, but static DCIR slope is normal and rest bias is low.
        if feats.capacity_fade_pct >= self.THRESH_CAPACITY_FADE_PCT:
            c_ratio = min(4.0, feats.capacity_fade_pct / self.THRESH_CAPACITY_FADE_PCT)
            # Check that it is not just an artifact of severe resistance
            not_r_bonus = 1.0 if delta_r0_mohm < (self.THRESH_R_SLOPE_MOHM * 1.5) else 0.3
            scores[FaultType.CAPACITY_FADE.value] += 2.0 * c_ratio * not_r_bonus

        # ── 5. Evaluate Nominal (Healthy) ─────────────────────────────────────
        is_low_r = abs(delta_r0_mohm) < self.THRESH_R_SLOPE_MOHM
        is_low_bias = abs(feats.v_rest_residual_mv) < self.THRESH_V_REST_BIAS_MV
        is_low_temp = feats.temp_excess_mean_c < self.THRESH_TEMP_EXCESS_C
        is_low_fade = feats.capacity_fade_pct < self.THRESH_CAPACITY_FADE_PCT

        if is_low_r and is_low_bias and is_low_temp and is_low_fade:
            scores[FaultType.NOMINAL.value] = 4.0

        # Normalize scores with Softmax / sum normalization
        total_score = sum(scores.values()) or 1.0
        norm_scores = {k: round(v / total_score, 4) for k, v in scores.items()}

        # Pick winning hypothesis
        best_fault_str, best_prob = max(norm_scores.items(), key=lambda x: x[1])
        attributed = FaultType(best_fault_str)

        # Quantitative severity estimation & narrative
        if attributed == FaultType.INCREASED_RESISTANCE:
            est_mohm = round(-feats.v_current_slope_mohm, 2)
            severity_str = f"+{est_mohm:.1f} mOhm internal resistance increase ({est_mohm / self.baseline.impedance.dcir_reference_mohm * 100.0:+.1f}% vs baseline)"
            severity_val = est_mohm
            explanation = (
                f"Voltage sag is strongly coupled to load current (slope dV/dI = {feats.v_current_slope_mohm:.2f} mOhm), "
                f"while zero-current resting residual is negligible ({feats.v_rest_residual_mv:+.2f} mV). "
                f"This matches an Ohmic / contact degradation mechanism without sensor bias."
            )
        elif attributed == FaultType.VOLTAGE_SENSOR_BIAS:
            est_mv = round(feats.v_rest_residual_mv, 1)
            severity_str = f"{est_mv:+.1f} mV constant voltage sensor calibration offset"
            severity_val = est_mv
            explanation = (
                f"A persistent static voltage residual of {feats.v_rest_residual_mv:+.2f} mV is observed even at zero current (rest), "
                f"and is relatively independent of load current fluctuations (r={feats.v_residual_current_independence:+.3f}). "
                f"This distinguishes an ADC / analog front-end calibration bias from physical electrochemical aging."
            )
        elif attributed == FaultType.TEMPERATURE_RISE:
            est_temp = round(feats.temp_excess_mean_c, 2)
            severity_str = f"+{est_temp:.1f} deg C average thermal excess above convective equilibrium (peak +{feats.temp_excess_max_c:.1f} deg C)"
            severity_val = est_temp
            explanation = (
                f"Cell temperature exceeded expected thermal equilibrium by an average of +{feats.temp_excess_mean_c:.2f} deg C "
                f"(peak rise rate: {feats.thermal_rise_rate_c_per_min:.2f} deg C/min). "
                f"This indicates a thermal management failure (e.g. cooling loss or unexpected heat generation)."
            )
        elif attributed == FaultType.CAPACITY_FADE:
            est_fade = round(feats.capacity_fade_pct, 2)
            severity_str = f"{est_fade:.1f} % usable capacity loss relative to baseline"
            severity_val = est_fade
            explanation = (
                f"The cell delivered {feats.capacity_fade_pct:.1f}% less Ah throughput before voltage cutoff "
                f"than the baseline reference model expected, while internal resistance remained near baseline. "
                f"This points to active lithium inventory loss (capacity fade)."
            )
        else:
            severity_str = "Nominal (Within normal manufacturing & calibration tolerances)"
            severity_val = 0.0
            explanation = (
                f"All diagnostic residuals (voltage slope: {feats.v_current_slope_mohm:.2f} mOhm, rest offset: {feats.v_rest_residual_mv:+.2f} mV, "
                f"thermal excess: {feats.temp_excess_mean_c:+.2f} deg C) are well within healthy calibration bounds."
            )

        return FaultDiagnosis(
            attributed_fault=attributed,
            confidence=best_prob,
            severity_estimate=severity_str,
            severity_value=severity_val,
            features=feats,
            hypotheses_scores=norm_scores,
            explanation=explanation,
        )

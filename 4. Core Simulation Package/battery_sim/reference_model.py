"""
Phase 2: Personalized Reference Model
======================================
Builds a per-cell baseline model by characterizing its unique parameter fingerprint
(capacity, DCIR, OCV curve deviation, thermal time constant) from a standardized
calibration protocol. At runtime, compares measured telemetry against baseline-predicted
values and surfaces signed residuals, anomaly severity scores, and health indicators.
"""

from __future__ import annotations
import json
import math
import statistics
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

from .cell_model import BatteryCell, CellParameters
from .profiles import (
    ConstantCurrentProfile,
    ConstantTempProfile,
    MultiStepProfile,
    PulseProfile,
)
from .simulator import BatterySimulator


# -----------------------------------------------------------------------------
# Baseline Data Structures
# -----------------------------------------------------------------------------

@dataclass
class CapacityBaseline:
    """Actual measured capacity at multiple temperatures."""
    temp_c_list: List[float]                 # Temperature setpoints [deg C]
    capacity_ah_list: List[float]            # Measured usable capacity at each temp [Ah]
    reference_ah: float                      # Capacity at 25 deg C (nominal reference)
    derating_coeff_per_c: float              # Fitted cold-derating slope [Ah / deg C]


@dataclass
class ImpedanceBaseline:
    """DC Internal Resistance (DCIR) and RC time constants at reference conditions."""
    soc_pct_list: List[float]                # SOC test points [%]
    dcir_mohm_list: List[float]              # Measured DCIR at each SOC [mOhm]
    dcir_reference_mohm: float               # DCIR at SOC=50%, 25 deg C [mOhm]
    dcir_soc_gradient: float                 # dR0/d(SOC) [mOhm / % SOC]
    tau1_s: float                            # Fast RC time constant [s]
    tau2_s: float                            # Slow RC time constant [s]
    dcir_arrhenius_ea: float                 # Fitted activation energy [J/mol]


@dataclass
class OcvBaseline:
    """Per-cell OCV vs SOC calibration (deviation from chemistry reference curve)."""
    soc_pct_list: List[float]                # SOC sample points [%]
    ocv_measured_v: List[float]              # OCV measured after 2h rest [V]
    ocv_model_v: List[float]                 # OCV from chemistry reference model [V]
    max_deviation_mv: float                  # Max absolute deviation from reference [mV]
    rms_deviation_mv: float                  # RMS deviation from reference [mV]


@dataclass
class ThermalBaseline:
    """Lumped thermal time constant and steady-state self-heating coefficient."""
    thermal_time_constant_s: float           # Time for 63.2% step response [s]
    self_heating_coeff_wh_per_a2: float      # Joule heating per A^2 at 25 deg C


@dataclass
class CellBaseline:
    """
    Complete personalized reference fingerprint for a single simulated battery cell.
    Captures the cell's unique identity: capacity, impedance, OCV deviation,
    and thermal profile -- all relative to the nominal chemistry specification.
    """
    cell_id: str
    chemistry: str
    nominal_capacity_ah: float               # Nominal chemistry specification
    calibration_timestamp: float             # POSIX time of baseline creation
    calibration_temp_c: float                # Temperature during calibration
    calibration_cycles: int                  # Simulated cycle number at calibration time

    capacity: CapacityBaseline
    impedance: ImpedanceBaseline
    ocv: OcvBaseline
    thermal: ThermalBaseline

    # Derived health summary
    state_of_health_pct: float               # Actual capacity / original capacity * 100
    capacity_fade_pct: float                 # Percentage capacity lost vs nominal

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, filepath: str) -> None:
        """Persist baseline fingerprint to a JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_json(cls, filepath: str) -> "CellBaseline":
        """Restore baseline fingerprint from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            cell_id=data["cell_id"],
            chemistry=data["chemistry"],
            nominal_capacity_ah=data["nominal_capacity_ah"],
            calibration_timestamp=data["calibration_timestamp"],
            calibration_temp_c=data["calibration_temp_c"],
            calibration_cycles=data["calibration_cycles"],
            capacity=CapacityBaseline(**data["capacity"]),
            impedance=ImpedanceBaseline(**data["impedance"]),
            ocv=OcvBaseline(**data["ocv"]),
            thermal=ThermalBaseline(**data["thermal"]),
            state_of_health_pct=data["state_of_health_pct"],
            capacity_fade_pct=data["capacity_fade_pct"],
        )


# -----------------------------------------------------------------------------
# Baseline Builder: Calibration Protocol
# -----------------------------------------------------------------------------

class BaselineCalibrator:
    """
    Runs a standardized multi-test calibration protocol on a simulated battery cell
    to extract its unique personalized reference fingerprint.

    Protocol:
    1. Capacity Test: Full 1C discharge at multiple temperatures to measure actual
       usable Ah at each thermal setpoint and fit a derating curve.
    2. HPPC DCIR Test: 10-second discharge pulses at 6 SOC waypoints at 25 deg C
       to measure DC internal resistance and resistance-SOC gradient.
    3. OCV Calibration: Slow C/20 discharge with equilibrium rest stops to map the
       cell's actual OCV vs SOC curve and compute deviation from the reference spline.
    4. Thermal Step Test: Apply a 2C step current and measure temperature rise trajectory
       to fit a lumped thermal time constant via 63.2% step-response criterion.
    """

    def __init__(
        self,
        cell: BatteryCell,
        cell_id: str = "CELL-001",
        calibration_cycles: int = 0,
    ) -> None:
        self.cell = cell
        self.cell_id = cell_id
        self.calibration_cycles = calibration_cycles

    def _fresh_cell(self, initial_soc: float = 1.0, temp_c: float = 25.0) -> BatteryCell:
        """Creates a fresh BatteryCell with the same parameters, reset to a clean state."""
        import copy
        fresh = BatteryCell(
            params=copy.deepcopy(self.cell.params),
            initial_soc=initial_soc,
            initial_temp_c=temp_c,
        )
        return fresh

    def _discharge_to_empty(self, temp_c: float) -> float:
        """
        Performs a full 1C constant-current discharge at temp_c.
        Returns measured usable capacity in Ah.
        """
        c1_rate = self.cell.params.nominal_capacity_ah  # 1C discharge current
        fresh = self._fresh_cell(initial_soc=1.0, temp_c=temp_c)
        sim = BatterySimulator(
            cell=fresh,
            load_profile=ConstantCurrentProfile(c1_rate),
            temperature_profile=ConstantTempProfile(temp_c),
            dt=10.0,
            max_duration_s=7200.0,
            temp_cutoff_max_c=80.0,
        )
        res = sim.run()
        return fresh.cumulative_ah_throughput

    def _measure_dcir_at_soc(self, soc: float, pulse_current: float, dt_pulse: float = 10.0) -> float:
        """
        Measures DCIR using a 10-second current pulse at a specific SOC.
        DCIR [Ohm] = (V_rest - V_pulse) / I_pulse
        """
        fresh = self._fresh_cell(initial_soc=soc, temp_c=25.0)
        v_rest = fresh.open_circuit_voltage()

        # Apply a single 10s pulse step (pre-heat first with tiny current for RC settling)
        fresh.step(current=0.1, ambient_temp_c=25.0, dt=120.0)  # Small pre-conditioning
        fresh.soc = soc   # Reset SOC back after pre-conditioning

        # Record V before pulse
        v_before = fresh.open_circuit_voltage() - fresh.v_rc1 - fresh.v_rc2

        # Apply pulse
        diag = fresh.step(current=pulse_current, ambient_temp_c=25.0, dt=dt_pulse)
        v_during = diag["v_terminal"]

        dcir = (v_before - v_during) / pulse_current
        return max(0.0, dcir)

    def _measure_ocv_curve(self) -> Tuple[List[float], List[float], List[float]]:
        """
        Slow C/20 discharge with periodic rests to measure equilibrium OCV at SOC waypoints.
        Returns (soc_pct_list, ocv_measured_v, ocv_model_v).
        """
        c20_rate = self.cell.params.nominal_capacity_ah / 20.0
        fresh = self._fresh_cell(initial_soc=1.0, temp_c=25.0)

        soc_waypoints = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
        soc_pct_list, ocv_measured, ocv_model = [], [], []

        # Discharge step-by-step from 100% to each waypoint and rest for equilibrium
        for target_soc in soc_waypoints:
            # Discharge until target SOC
            while fresh.soc > target_soc + 0.005:
                fresh.step(current=c20_rate, ambient_temp_c=25.0, dt=30.0)

            # Equilibrium rest: 20 x 30s steps = 10 minutes relaxation
            for _ in range(20):
                fresh.step(current=0.0, ambient_temp_c=25.0, dt=30.0)

            # Measure resting voltage (OCV surrogate after relaxation)
            v_meas = fresh.calculate_terminal_voltage(0.0)
            v_ref = fresh.open_circuit_voltage(soc=fresh.soc)

            soc_pct_list.append(round(fresh.soc * 100.0, 1))
            ocv_measured.append(round(v_meas, 4))
            ocv_model.append(round(v_ref, 4))

        return soc_pct_list, ocv_measured, ocv_model

    def _measure_thermal_time_constant(self) -> Tuple[float, float]:
        """
        Applies a 2C step discharge and tracks temperature rise.
        Fits a lumped thermal time constant via 63.2% of final temperature rise.
        Returns (tau_s, self_heating_coeff).
        """
        fresh = self._fresh_cell(initial_soc=0.7, temp_c=25.0)
        c2_rate = 2.0 * self.cell.params.nominal_capacity_ah
        dt = 5.0
        n_steps = 120      # 600 seconds total

        t_initial = fresh.temperature_c
        temps: List[float] = [t_initial]
        times: List[float] = [0.0]

        for k in range(n_steps):
            diag = fresh.step(current=c2_rate, ambient_temp_c=25.0, dt=dt)
            temps.append(diag["cell_temp_c"])
            times.append((k + 1) * dt)

        # Approximate steady state as max observed temperature
        t_final = max(temps)
        t_63 = t_initial + 0.632 * (t_final - t_initial)

        # Find crossing time by linear interpolation
        tau_s = None
        for i in range(1, len(temps)):
            if temps[i] >= t_63:
                # Linear interpolation between steps
                frac = (t_63 - temps[i - 1]) / max(1e-9, temps[i] - temps[i - 1])
                tau_s = times[i - 1] + frac * dt
                break

        if tau_s is None:
            tau_s = float(n_steps * dt)

        # Self-heating coefficient: average Q_joule / I^2 at mid-run
        r0_mid = self.cell.ohmic_resistance(soc=0.6, temp_k=298.15)
        self_heating_coeff = r0_mid  # W / A^2 = Ohm

        return round(tau_s, 1), round(self_heating_coeff, 5)

    def build(self) -> CellBaseline:
        """
        Executes the full calibration protocol and returns a CellBaseline fingerprint.
        """
        params = self.cell.params

        # -- 1. Capacity measurements at 3 temperatures ----------------------
        cal_temps = [-10.0, 25.0, 45.0]
        cap_measurements: List[float] = []
        for tc in cal_temps:
            ah = self._discharge_to_empty(temp_c=tc)
            cap_measurements.append(round(ah, 4))

        ref_ah = cap_measurements[cal_temps.index(25.0)]

        # Fit linear derating slope (Ah loss per deg C below 25 deg C)
        pairs = [(t, ah) for t, ah in zip(cal_temps, cap_measurements) if t <= 25.0]
        if len(pairs) >= 2:
            delta_t = pairs[-1][0] - pairs[0][0]
            delta_ah = pairs[-1][1] - pairs[0][1]
            derating_slope = delta_ah / delta_t if delta_t != 0 else 0.0
        else:
            derating_slope = -params.temp_capacity_derating_per_c * params.nominal_capacity_ah

        capacity_bsl = CapacityBaseline(
            temp_c_list=cal_temps,
            capacity_ah_list=cap_measurements,
            reference_ah=round(ref_ah, 4),
            derating_coeff_per_c=round(derating_slope, 5),
        )

        # -- 2. DCIR measurements at 6 SOC waypoints -------------------------
        soc_waypoints = [0.2, 0.35, 0.50, 0.65, 0.80, 0.90]
        pulse_current = 2.0 * params.nominal_capacity_ah   # 2C pulse
        dcir_vals: List[float] = []
        for soc in soc_waypoints:
            r_ohm = self._measure_dcir_at_soc(soc, pulse_current)
            dcir_vals.append(round(r_ohm * 1000.0, 2))   # Convert to mOhm

        # DCIR at SOC=50% ~= reference
        dcir_ref_idx = soc_waypoints.index(0.50)
        dcir_ref_mohm = dcir_vals[dcir_ref_idx]

        # Linear regression: dR0/d(SOC)
        soc_pct_pts = [s * 100.0 for s in soc_waypoints]
        n = len(soc_pct_pts)
        mean_s = statistics.mean(soc_pct_pts)
        mean_r = statistics.mean(dcir_vals)
        numerator = sum((soc_pct_pts[i] - mean_s) * (dcir_vals[i] - mean_r) for i in range(n))
        denominator = sum((soc_pct_pts[i] - mean_s) ** 2 for i in range(n))
        dcir_slope = numerator / denominator if denominator != 0 else 0.0

        # Time constants from parameters (same cell, different notation)
        r1, c1, r2, c2 = self.cell.polarization_impedances(temp_k=298.15)
        tau1_s = r1 * c1
        tau2_s = r2 * c2

        impedance_bsl = ImpedanceBaseline(
            soc_pct_list=[s * 100.0 for s in soc_waypoints],
            dcir_mohm_list=dcir_vals,
            dcir_reference_mohm=round(dcir_ref_mohm, 2),
            dcir_soc_gradient=round(dcir_slope, 4),
            tau1_s=round(tau1_s, 2),
            tau2_s=round(tau2_s, 2),
            dcir_arrhenius_ea=params.ea_r0,
        )

        # -- 3. OCV Curve Deviation -------------------------------------------
        soc_pct_list, ocv_meas, ocv_ref = self._measure_ocv_curve()
        deviations_mv = [(m - r) * 1000.0 for m, r in zip(ocv_meas, ocv_ref)]
        max_dev_mv = max(abs(d) for d in deviations_mv)
        rms_dev_mv = math.sqrt(statistics.mean(d ** 2 for d in deviations_mv))

        ocv_bsl = OcvBaseline(
            soc_pct_list=soc_pct_list,
            ocv_measured_v=ocv_meas,
            ocv_model_v=ocv_ref,
            max_deviation_mv=round(max_dev_mv, 2),
            rms_deviation_mv=round(rms_dev_mv, 2),
        )

        # -- 4. Thermal Time Constant -----------------------------------------
        tau_thermal, shc = self._measure_thermal_time_constant()
        thermal_bsl = ThermalBaseline(
            thermal_time_constant_s=tau_thermal,
            self_heating_coeff_wh_per_a2=shc,
        )

        # -- Derived SOH and capacity fade ------------------------------------
        soh = (ref_ah / params.nominal_capacity_ah) * 100.0
        fade = 100.0 - soh

        return CellBaseline(
            cell_id=self.cell_id,
            chemistry=params.chemistry.value,
            nominal_capacity_ah=params.nominal_capacity_ah,
            calibration_timestamp=time.time(),
            calibration_temp_c=25.0,
            calibration_cycles=self.calibration_cycles,
            capacity=capacity_bsl,
            impedance=impedance_bsl,
            ocv=ocv_bsl,
            thermal=thermal_bsl,
            state_of_health_pct=round(soh, 2),
            capacity_fade_pct=round(fade, 2),
        )


# -----------------------------------------------------------------------------
# Reference Model: Predictions from Baseline
# -----------------------------------------------------------------------------

class ReferenceModel:
    """
    Generates model-predicted values for voltage, temperature, and DCIR at each
    time step, using the cell's personalized baseline fingerprint.

    Voltage prediction uses the full 2-RC Thevenin model (integrates RC state
    alongside the simulator) so transient polarization overpotentials are captured:
      V_pred = OCV(SOC, T) - I * R0(SOC, T) - V_rc1(t) - V_rc2(t)
    """

    def __init__(self, baseline, cell):
        self.baseline = baseline
        self.cell = cell
        self._v_rc1_pred = 0.0
        self._v_rc2_pred = 0.0

    def _baseline_r0(self, soc, temp_c):
        """Baseline-calibrated R0 with SOC interpolation and Arrhenius temperature correction."""
        import math
        soc_pct = soc * 100.0
        bsl_soc = self.baseline.impedance.soc_pct_list
        bsl_dcir = self.baseline.impedance.dcir_mohm_list
        r_mohm = _interp1d(soc_pct, bsl_soc, bsl_dcir)
        ea = self.baseline.impedance.dcir_arrhenius_ea
        t_k = temp_c + 273.15
        thermal_factor = math.exp((ea / 8.314462) * (1.0 / t_k - 1.0 / 298.15))
        return (r_mohm * thermal_factor) / 1000.0

    def step_predict_voltage(self, soc, current, temp_c, dt):
        """
        Advances the reference RC predictor by dt seconds and returns the predicted
        terminal voltage including transient polarization overpotentials.
        V_pred = OCV(SOC, T) - I * R0 - V_rc1(t) - V_rc2(t)

        Polarization resistances (R1, R2) and time constants (tau1, tau2) are derived
        directly from the cell's electrochemical parameters at the operating temperature,
        preventing under-prediction of polarization relaxation during dynamic driving.
        """
        import math
        v_ocv = self.cell.open_circuit_voltage(soc=soc, temp_c=temp_c)
        r0 = self._baseline_r0(soc=soc, temp_c=temp_c)
        if hasattr(self.cell, "polarization_impedances"):
            r1, c1, r2, c2 = self.cell.polarization_impedances(temp_k=temp_c + 273.15)
            tau1 = max(1.0, r1 * c1)
            tau2 = max(1.0, r2 * c2)
        else:
            tau1 = max(1.0, self.baseline.impedance.tau1_s)
            tau2 = max(1.0, self.baseline.impedance.tau2_s)
            r1 = r0 * 0.50
            r2 = r0 * 0.35
        dt = max(1e-6, float(dt))
        exp1 = math.exp(-dt / tau1)
        self._v_rc1_pred = self._v_rc1_pred * exp1 + current * r1 * (1.0 - exp1)
        exp2 = math.exp(-dt / tau2)
        self._v_rc2_pred = self._v_rc2_pred * exp2 + current * r2 * (1.0 - exp2)
        return v_ocv - current * r0 - self._v_rc1_pred - self._v_rc2_pred

    def predict_voltage(self, soc, current, temp_c):
        """Stateless voltage prediction (OCV - I*R0) for single-point queries."""
        v_ocv = self.cell.open_circuit_voltage(soc=soc, temp_c=temp_c)
        r0 = self._baseline_r0(soc=soc, temp_c=temp_c)
        return v_ocv - current * r0

    def predict_capacity_ah(self, temp_c):
        """Predicts usable capacity at given temperature using the baseline derating curve."""
        bsl_temps = self.baseline.capacity.temp_c_list
        bsl_caps = self.baseline.capacity.capacity_ah_list
        return max(0.1, _interp1d(temp_c, bsl_temps, bsl_caps))

    def predict_dcir_mohm(self, soc, temp_c):
        """Predicts DCIR in mOhm using baseline impedance curve with Arrhenius correction."""
        import math
        soc_pct = soc * 100.0
        bsl_soc = self.baseline.impedance.soc_pct_list
        bsl_dcir = self.baseline.impedance.dcir_mohm_list
        r_base = _interp1d(soc_pct, bsl_soc, bsl_dcir)
        ea = self.baseline.impedance.dcir_arrhenius_ea
        t_k = temp_c + 273.15
        thermal_factor = math.exp((ea / 8.314462) * (1.0 / t_k - 1.0 / 298.15))
        return r_base * thermal_factor

def _interp1d(x: float, xs: List[float], ys: List[float]) -> float:
    """Linear interpolation with clamped extrapolation."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])
    return ys[-1]


# -----------------------------------------------------------------------------
# Deviation & Anomaly Analysis
# -----------------------------------------------------------------------------

@dataclass
class StepDeviation:
    """Per-step deviation between measured and model-predicted values."""
    time_s: float
    soc_pct: float
    current_a: float
    cell_temp_c: float

    # Voltage
    v_measured: float
    v_predicted: float
    v_residual_mv: float         # (measured - predicted) * 1000 [mV]
    v_residual_pct: float        # relative to predicted [%]

    # DCIR
    dcir_measured_mohm: float
    dcir_predicted_mohm: float
    dcir_residual_mohm: float    # (measured - predicted) [mOhm]
    dcir_residual_pct: float

    # Thermal
    temp_predicted_c: float      # Expected temperature at equilibrium for this current
    temp_residual_c: float       # (measured - expected) [deg C]

    # Anomaly
    anomaly_score: float         # Normalized 0-1 composite severity index


@dataclass
class DeviationReport:
    """
    Summary of measured vs baseline-predicted deviations over a simulation run.
    """
    cell_id: str
    chemistry: str
    total_steps: int
    elapsed_seconds: float

    # Voltage residual statistics
    v_mean_residual_mv: float
    v_max_residual_mv: float
    v_rms_residual_mv: float
    v_std_residual_mv: float

    # DCIR residual statistics
    dcir_mean_residual_mohm: float
    dcir_max_residual_mohm: float
    dcir_rms_residual_mohm: float

    # Thermal deviation statistics
    temp_mean_residual_c: float
    temp_max_residual_c: float

    # Anomaly summary
    anomaly_score_mean: float
    anomaly_score_max: float
    anomaly_score_95th_pct: float

    # Health signal
    effective_capacity_ah: float          # Mean baseline-predicted capacity this run
    soh_estimate_pct: float               # SOH estimate from effective capacity
    capacity_fade_pct: float

    step_deviations: List[StepDeviation] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=" * 68,
            f"     REFERENCE MODEL DEVIATION REPORT -- {self.cell_id} ({self.chemistry})",
            "=" * 68,
            f"  Elapsed Time        : {self.elapsed_seconds:.1f} s | Steps: {self.total_steps}",
            "-" * 68,
            "  VOLTAGE RESIDUALS (measured - predicted)",
            f"    Mean              : {self.v_mean_residual_mv:+.2f} mV",
            f"    RMS               : {self.v_rms_residual_mv:.2f} mV",
            f"    Max Absolute      : {self.v_max_residual_mv:.2f} mV",
            f"    Std Dev           : {self.v_std_residual_mv:.2f} mV",
            "-" * 68,
            "  DCIR RESIDUALS (measured - predicted)",
            f"    Mean              : {self.dcir_mean_residual_mohm:+.2f} mOhm",
            f"    RMS               : {self.dcir_rms_residual_mohm:.2f} mOhm",
            f"    Max Absolute      : {self.dcir_max_residual_mohm:.2f} mOhm",
            "-" * 68,
            "  THERMAL RESIDUALS (measured - predicted equilibrium)",
            f"    Mean              : {self.temp_mean_residual_c:+.2f} deg C",
            f"    Max Absolute      : {self.temp_max_residual_c:.2f} deg C",
            "-" * 68,
            "  ANOMALY SCORE (0 = nominal, 1 = critical)",
            f"    Mean              : {self.anomaly_score_mean:.4f}",
            f"    95th Percentile   : {self.anomaly_score_95th_pct:.4f}",
            f"    Peak              : {self.anomaly_score_max:.4f}",
            "-" * 68,
            "  HEALTH SIGNALS",
            f"    Effective Cap     : {self.effective_capacity_ah:.3f} Ah",
            f"    SOH Estimate      : {self.soh_estimate_pct:.1f} %",
            f"    Capacity Fade     : {self.capacity_fade_pct:.2f} %",
            "=" * 68,
        ]
        return "\n".join(lines)

    def to_csv(self, filepath: str) -> None:
        """Export per-step deviation data to CSV."""
        import csv
        from dataclasses import asdict
        if not self.step_deviations:
            return
        fieldnames = list(asdict(self.step_deviations[0]).keys())
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for sd in self.step_deviations:
                writer.writerow(asdict(sd))

    def to_json(self, filepath: str) -> None:
        """Export full deviation report (including per-step data) to JSON."""
        from dataclasses import asdict
        report_dict = {
            "cell_id": self.cell_id,
            "chemistry": self.chemistry,
            "total_steps": self.total_steps,
            "elapsed_seconds": self.elapsed_seconds,
            "v_mean_residual_mv": self.v_mean_residual_mv,
            "v_max_residual_mv": self.v_max_residual_mv,
            "v_rms_residual_mv": self.v_rms_residual_mv,
            "v_std_residual_mv": self.v_std_residual_mv,
            "dcir_mean_residual_mohm": self.dcir_mean_residual_mohm,
            "dcir_max_residual_mohm": self.dcir_max_residual_mohm,
            "dcir_rms_residual_mohm": self.dcir_rms_residual_mohm,
            "temp_mean_residual_c": self.temp_mean_residual_c,
            "temp_max_residual_c": self.temp_max_residual_c,
            "anomaly_score_mean": self.anomaly_score_mean,
            "anomaly_score_max": self.anomaly_score_max,
            "anomaly_score_95th_pct": self.anomaly_score_95th_pct,
            "effective_capacity_ah": self.effective_capacity_ah,
            "soh_estimate_pct": self.soh_estimate_pct,
            "capacity_fade_pct": self.capacity_fade_pct,
            "step_deviations": [asdict(sd) for sd in self.step_deviations],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)


# -----------------------------------------------------------------------------
# Live Deviation Tracker
# -----------------------------------------------------------------------------

class DeviationTracker:
    """
    Attaches to an active simulation step-by-step.
    After each step, receives the measured telemetry and produces a StepDeviation
    comparing actual vs baseline-predicted values.
    """

    # Thresholds for normalizing anomaly scores (physical engineering bounds)
    _V_THRESHOLD_MV = 80.0          # Voltage residual considered significant [mV]
    _DCIR_THRESHOLD_MOHM = 8.0      # DCIR residual considered significant [mOhm]
    _TEMP_THRESHOLD_C = 5.0         # Temperature residual considered significant [deg C]

    def __init__(self, baseline: CellBaseline, cell: BatteryCell) -> None:
        self.baseline = baseline
        self.model = ReferenceModel(baseline, cell)
        self.cell = cell
        self._step_deviations: List[StepDeviation] = []
        self._last_time_s: Optional[float] = None

    def record(
        self,
        time_s: float,
        current_a: float,
        soc: float,
        v_measured: float,
        dcir_measured_mohm: float,
        cell_temp_c: float,
        ambient_temp_c: float,
        dt: Optional[float] = None,
    ) -> StepDeviation:
        """
        Computes deviation metrics for a single telemetry point and appends to history.
        """
        if dt is None:
            if self._last_time_s is not None and time_s > self._last_time_s:
                dt = time_s - self._last_time_s
            else:
                dt = 1.0
        self._last_time_s = time_s

        # Dynamic model predictions (using 2-RC stateful predictor)
        v_pred = self.model.step_predict_voltage(soc=soc, current=current_a, temp_c=cell_temp_c, dt=dt)
        dcir_pred = self.model.predict_dcir_mohm(soc=soc, temp_c=cell_temp_c)
        cap_pred = self.model.predict_capacity_ah(temp_c=cell_temp_c)

        # Expected steady-state temperature: ambient + (I^2 * R0) / (h * A)
        params = self.cell.params
        r0_pred = dcir_pred / 1000.0
        q_gen_est = (current_a ** 2) * r0_pred
        h_a = params.convective_h * params.surface_area_m2
        t_equilibrium = ambient_temp_c + (q_gen_est / h_a if h_a > 0 else 0.0)

        # Signed residuals
        v_resid_mv = (v_measured - v_pred) * 1000.0
        dcir_resid = dcir_measured_mohm - dcir_pred
        temp_resid = cell_temp_c - t_equilibrium

        # Relative residuals [%]
        v_resid_pct = (v_resid_mv / (abs(v_pred) * 10.0)) if v_pred != 0 else 0.0
        dcir_resid_pct = (dcir_resid / dcir_pred * 100.0) if dcir_pred > 0 else 0.0

        # Anomaly score: normalized L2 combination of clamped sub-scores
        s_v = min(1.0, abs(v_resid_mv) / self._V_THRESHOLD_MV)
        s_r = min(1.0, abs(dcir_resid) / self._DCIR_THRESHOLD_MOHM)
        s_t = min(1.0, abs(temp_resid) / self._TEMP_THRESHOLD_C)
        anomaly_score = math.sqrt((s_v ** 2 + s_r ** 2 + s_t ** 2) / 3.0)

        dev = StepDeviation(
            time_s=round(time_s, 2),
            soc_pct=round(soc * 100.0, 2),
            current_a=round(current_a, 3),
            cell_temp_c=round(cell_temp_c, 2),
            v_measured=round(v_measured, 4),
            v_predicted=round(v_pred, 4),
            v_residual_mv=round(v_resid_mv, 2),
            v_residual_pct=round(v_resid_pct, 3),
            dcir_measured_mohm=round(dcir_measured_mohm, 2),
            dcir_predicted_mohm=round(dcir_pred, 2),
            dcir_residual_mohm=round(dcir_resid, 2),
            dcir_residual_pct=round(dcir_resid_pct, 2),
            temp_predicted_c=round(t_equilibrium, 2),
            temp_residual_c=round(temp_resid, 2),
            anomaly_score=round(anomaly_score, 4),
        )
        self._step_deviations.append(dev)
        return dev

    def finalize(self) -> DeviationReport:
        """
        Aggregates all per-step deviations into a DeviationReport with statistics.
        """
        devs = self._step_deviations
        if not devs:
            raise ValueError("No deviation data recorded yet.")

        v_resids = [d.v_residual_mv for d in devs]
        dcir_resids = [d.dcir_residual_mohm for d in devs]
        temp_resids = [d.temp_residual_c for d in devs]
        scores = [d.anomaly_score for d in devs]

        mean_v = statistics.mean(v_resids)
        max_v = max(abs(v) for v in v_resids)
        rms_v = math.sqrt(statistics.mean(r ** 2 for r in v_resids))
        std_v = statistics.stdev(v_resids) if len(v_resids) > 1 else 0.0

        mean_dcir = statistics.mean(dcir_resids)
        max_dcir = max(abs(r) for r in dcir_resids)
        rms_dcir = math.sqrt(statistics.mean(r ** 2 for r in dcir_resids))

        mean_temp = statistics.mean(temp_resids)
        max_temp = max(abs(r) for r in temp_resids)

        scores_sorted = sorted(scores)
        n = len(scores_sorted)
        idx_95 = min(n - 1, int(0.95 * n))
        score_95 = scores_sorted[idx_95]

        elapsed = devs[-1].time_s if devs else 0.0

        # Effective capacity from baseline at mean observed temperature
        mean_temp_c = statistics.mean(d.cell_temp_c for d in devs)
        eff_cap = self.model.predict_capacity_ah(temp_c=mean_temp_c)
        nominal_cap = self.baseline.nominal_capacity_ah
        soh = (eff_cap / nominal_cap * 100.0) if nominal_cap > 0 else 100.0
        fade = 100.0 - soh

        return DeviationReport(
            cell_id=self.baseline.cell_id,
            chemistry=self.baseline.chemistry,
            total_steps=len(devs),
            elapsed_seconds=elapsed,
            v_mean_residual_mv=round(mean_v, 3),
            v_max_residual_mv=round(max_v, 3),
            v_rms_residual_mv=round(rms_v, 3),
            v_std_residual_mv=round(std_v, 3),
            dcir_mean_residual_mohm=round(mean_dcir, 3),
            dcir_max_residual_mohm=round(max_dcir, 3),
            dcir_rms_residual_mohm=round(rms_dcir, 3),
            temp_mean_residual_c=round(mean_temp, 3),
            temp_max_residual_c=round(max_temp, 3),
            anomaly_score_mean=round(statistics.mean(scores), 4),
            anomaly_score_max=round(max(scores), 4),
            anomaly_score_95th_pct=round(score_95, 4),
            effective_capacity_ah=round(eff_cap, 4),
            soh_estimate_pct=round(soh, 2),
            capacity_fade_pct=round(fade, 2),
            step_deviations=devs,
        )

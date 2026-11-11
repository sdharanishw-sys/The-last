# ============================================================
# TWIN REFERENCE ADAPTIVE BATTERY MANAGEMENT SYSTEM
# WITH DEVIATION ATTRIBUTION FOR PERSONALIZED EV BATTERY HEALTH
#
# battery_engine.py  –  Core simulation engine
# ============================================================

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, Tuple
import json, os, math

# ------------------------------------------------------------------ #
# 1.  DAY-ONE FINGERPRINT  (permanent reference — never changes)      #
# ------------------------------------------------------------------ #

DAY_ONE_FINGERPRINT: Dict = {
    "cell_chemistry":       "NMC Lithium-Ion",
    "nominal_voltage_V":    3.65,
    "rated_capacity_Ah":    100.0,
    "initial_resistance_Ohm": 0.012,
    "initial_SOH_pct":      100.0,
    "initial_SOC_pct":      100.0,
    "max_charge_rate_C":    1.0,
    "max_discharge_rate_C": 2.0,
    "thermal_mass_J_per_K": 5000.0,
    "convection_coeff":     12.0,
    "ambient_temp_C":       25.0,
    "ocv_table": {           # SOC% -> OCV (V) lookup
        0:  3.00, 10: 3.30, 20: 3.50, 30: 3.60,
        40: 3.65, 50: 3.70, 60: 3.72, 70: 3.75,
        80: 3.80, 90: 3.85, 100: 4.20
    },
    "timestamp": "2024-01-01T00:00:00",
    "version":   "1.0"
}


def save_fingerprint(path: str = "fingerprint.json"):
    with open(path, "w") as f:
        json.dump(DAY_ONE_FINGERPRINT, f, indent=2)


def load_fingerprint(path: str = "fingerprint.json") -> Dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return DAY_ONE_FINGERPRINT.copy()


# ------------------------------------------------------------------ #
# 2.  OCV INTERPOLATION                                               #
# ------------------------------------------------------------------ #

def ocv_from_soc(soc_pct: float, fp: Dict = DAY_ONE_FINGERPRINT) -> float:
    """Return open-circuit voltage at given SOC using linear interpolation."""
    table = fp["ocv_table"]
    keys  = sorted([float(k) for k in table.keys()])
    vals  = [table[str(int(k))] for k in keys]
    return float(np.interp(np.clip(soc_pct, 0, 100), keys, vals))


# ------------------------------------------------------------------ #
# 3.  EXPECTED AGING SHADOW CURVE                                     #
# ------------------------------------------------------------------ #

def aging_shadow_curve(cycle_counts: np.ndarray) -> np.ndarray:
    """
    Manufacturer-claimed SOH degradation curve.
    Models SOH decline using a double-exponential fit typical of NMC cells.
    SOH stays near 100% early, then drops, reaching ~80% at 1000 cycles.
    """
    soh = 100.0 * np.exp(-cycle_counts / 4000.0) \
        - 2.0   * (1 - np.exp(-cycle_counts / 500.0))
    return np.clip(soh, 0, 100)


def resistance_aging(cycle_count: float, fp: Dict = DAY_ONE_FINGERPRINT) -> float:
    """Internal resistance grows with cycling and calendar ageing."""
    r0  = fp["initial_resistance_Ohm"]
    # Power-law growth: R(n) = R0 * (1 + 0.0003 * n^0.6)
    return r0 * (1 + 0.0003 * (cycle_count ** 0.6))


def capacity_from_soh(soh_pct: float, fp: Dict = DAY_ONE_FINGERPRINT) -> float:
    return fp["rated_capacity_Ah"] * soh_pct / 100.0


# ------------------------------------------------------------------ #
# 4.  BATTERY STATE DATACLASS                                         #
# ------------------------------------------------------------------ #

@dataclass
class BatteryState:
    soh_pct:            float = 100.0
    soc_pct:            float = 95.0
    voltage_V:          float = 4.10
    current_A:          float = -20.0   # negative = discharging
    temperature_C:      float = 25.0
    resistance_Ohm:     float = 0.012
    capacity_Ah:        float = 100.0
    cycle_count:        int   = 0
    power_kW:           float = 0.0
    charge_status:      str   = "Discharging"
    aging_state:        str   = "New"
    # Derived
    expected_soh_pct:   float = 100.0
    soh_deviation_pct:  float = 0.0
    expected_resist_Ohm: float = 0.012


# ------------------------------------------------------------------ #
# 5.  STAGE PRESETS                                                   #
# ------------------------------------------------------------------ #

def build_state(stage: str, fp: Dict = DAY_ONE_FINGERPRINT) -> BatteryState:
    """
    stage: "new"  | "eol"  | "adaptive"
    """
    s = BatteryState()

    if stage == "new":
        s.cycle_count      = 10
        s.soh_pct          = 99.5
        s.soc_pct          = 95.0
        s.resistance_Ohm   = resistance_aging(10, fp)
        s.capacity_Ah      = capacity_from_soh(s.soh_pct, fp)
        s.current_A        = -20.0
        s.temperature_C    = 26.5
        s.charge_status    = "Discharging"
        s.aging_state      = "New – Day-One Condition"

    elif stage == "eol":
        s.cycle_count      = 1800
        s.soh_pct          = 54.0          # well below 70% threshold
        s.soc_pct          = 42.0
        s.resistance_Ohm   = resistance_aging(1800, fp)
        s.capacity_Ah      = capacity_from_soh(s.soh_pct, fp)
        s.current_A        = -8.0
        s.temperature_C    = 38.5
        s.charge_status    = "Discharging"
        s.aging_state      = "End-of-Life – Severe Degradation"

    elif stage == "adaptive":
        # Same 1800 cycles but adaptive model extended life
        s.cycle_count      = 1800
        s.soh_pct          = 76.4          # 22+ pct points above EOL default
        s.soc_pct          = 71.0
        s.resistance_Ohm   = resistance_aging(1800, fp) * 0.78   # managed well
        s.capacity_Ah      = capacity_from_soh(s.soh_pct, fp)
        s.current_A        = -15.0
        s.temperature_C    = 29.2
        s.charge_status    = "Discharging"
        s.aging_state      = "AI-Adaptive Extended Life"

    # Voltage from ECM: V = OCV - I * R  (I negative when discharging)
    ocv = ocv_from_soc(s.soc_pct, fp)
    s.voltage_V = ocv - s.current_A * s.resistance_Ohm

    # Power
    s.power_kW = abs(s.current_A * s.voltage_V) / 1000.0

    # Aging shadow at this cycle count
    s.expected_soh_pct    = float(aging_shadow_curve(np.array([s.cycle_count]))[0])
    s.soh_deviation_pct   = s.soh_pct - s.expected_soh_pct
    s.expected_resist_Ohm = resistance_aging(s.cycle_count, fp)

    return s


# ------------------------------------------------------------------ #
# 6.  LIVE SENSOR STREAM (simulated, with realistic noise)            #
# ------------------------------------------------------------------ #

def live_stream_snapshot(state: BatteryState,
                         fp: Dict = DAY_ONE_FINGERPRINT,
                         t_step: int = 0) -> BatteryState:
    """
    Advance the battery state by one time-step (1 second equivalent),
    adding realistic sensor noise and slow dynamics.
    """
    rng  = np.random.default_rng(seed=t_step)
    s    = BatteryState(**state.__dict__)   # shallow copy

    # Coulomb counting: dSOC = -I * dt / (3600 * C)
    dt_s = 1.0
    s.soc_pct  -= (s.current_A * dt_s) / (3600.0 * s.capacity_Ah) * 100.0
    s.soc_pct   = float(np.clip(s.soc_pct, 0, 100))

    # Thermal: T += (I^2 * R - h*(T-Tamb)) / (m*Cp) * dt
    heat_gen   = (s.current_A ** 2) * s.resistance_Ohm
    heat_loss  = fp["convection_coeff"] * (s.temperature_C - fp["ambient_temp_C"])
    dT         = (heat_gen - heat_loss) / fp["thermal_mass_J_per_K"] * dt_s
    s.temperature_C = float(np.clip(s.temperature_C + dT, -20, 80))

    # ECM voltage
    ocv         = ocv_from_soc(s.soc_pct, fp)
    s.voltage_V = float(ocv - s.current_A * s.resistance_Ohm)

    # Add sensor noise
    s.voltage_V     += float(rng.normal(0, 0.002))
    s.temperature_C += float(rng.normal(0, 0.05))
    s.current_A     += float(rng.normal(0, 0.1))

    s.power_kW = abs(s.current_A * s.voltage_V) / 1000.0

    return s


# ------------------------------------------------------------------ #
# 7.  DEVIATION ATTRIBUTION LAYER                                     #
# ------------------------------------------------------------------ #

def status_flag(value: float, warn_lo: float, crit_lo: float,
                warn_hi: float = None, crit_hi: float = None) -> str:
    """Return 'NORMAL', 'WARNING', or 'CRITICAL'."""
    if value <= crit_lo:
        return "CRITICAL"
    if value <= warn_lo:
        return "WARNING"
    if warn_hi is not None and value >= warn_hi:
        return "CRITICAL" if (crit_hi and value >= crit_hi) else "WARNING"
    return "NORMAL"


def compute_deviation_attribution(state: BatteryState,
                                  fp: Dict = DAY_ONE_FINGERPRINT) -> pd.DataFrame:
    """
    Compare live readings against Day-One Fingerprint.
    Returns a DataFrame suitable for direct display.
    """
    rows = []

    # SOH
    soh_dev = state.soh_pct - fp["initial_SOH_pct"]
    rows.append({
        "Parameter":    "State of Health (SOH)",
        "Live Value":   f"{state.soh_pct:.1f} %",
        "Reference":    f"{fp['initial_SOH_pct']:.1f} %",
        "Deviation":    f"{soh_dev:+.1f} %",
        "Status":       status_flag(state.soh_pct, 70, 50),
        "Unit":         "%"
    })

    # SOC
    rows.append({
        "Parameter":    "State of Charge (SOC)",
        "Live Value":   f"{state.soc_pct:.1f} %",
        "Reference":    f"{fp['initial_SOC_pct']:.1f} %",
        "Deviation":    f"{state.soc_pct - fp['initial_SOC_pct']:+.1f} %",
        "Status":       status_flag(state.soc_pct, 20, 10),
        "Unit":         "%"
    })

    # Voltage
    ref_v = fp["nominal_voltage_V"]
    rows.append({
        "Parameter":    "Terminal Voltage",
        "Live Value":   f"{state.voltage_V:.3f} V",
        "Reference":    f"{ref_v:.3f} V",
        "Deviation":    f"{state.voltage_V - ref_v:+.3f} V",
        "Status":       status_flag(state.voltage_V, 3.2, 3.0, 4.15, 4.25),
        "Unit":         "V"
    })

    # Temperature
    rows.append({
        "Parameter":    "Battery Temperature",
        "Live Value":   f"{state.temperature_C:.1f} °C",
        "Reference":    f"{fp['ambient_temp_C']:.1f} °C",
        "Deviation":    f"{state.temperature_C - fp['ambient_temp_C']:+.1f} °C",
        "Status":       status_flag(state.temperature_C,
                                    warn_lo=-999, crit_lo=-999,
                                    warn_hi=35.0, crit_hi=45.0),
        "Unit":         "°C"
    })

    # Internal Resistance
    r_dev = (state.resistance_Ohm - fp["initial_resistance_Ohm"]) \
            / fp["initial_resistance_Ohm"] * 100
    rows.append({
        "Parameter":    "Internal Resistance",
        "Live Value":   f"{state.resistance_Ohm*1000:.2f} mΩ",
        "Reference":    f"{fp['initial_resistance_Ohm']*1000:.2f} mΩ",
        "Deviation":    f"{r_dev:+.1f} %",
        "Status":       status_flag(-r_dev, -150, -200),   # inverted: higher R is worse
        "Unit":         "mΩ"
    })

    # Capacity
    cap_dev = (state.capacity_Ah - fp["rated_capacity_Ah"]) \
              / fp["rated_capacity_Ah"] * 100
    rows.append({
        "Parameter":    "Usable Capacity",
        "Live Value":   f"{state.capacity_Ah:.1f} Ah",
        "Reference":    f"{fp['rated_capacity_Ah']:.1f} Ah",
        "Deviation":    f"{cap_dev:+.1f} %",
        "Status":       status_flag(state.capacity_Ah,
                                    0.70 * fp["rated_capacity_Ah"],
                                    0.50 * fp["rated_capacity_Ah"]),
        "Unit":         "Ah"
    })

    # Cycle count (informational)
    rows.append({
        "Parameter":    "Cycle Count",
        "Live Value":   f"{state.cycle_count}",
        "Reference":    "0 (Day-One)",
        "Deviation":    f"+{state.cycle_count}",
        "Status":       status_flag(-state.cycle_count, -1500, -2000),
        "Unit":         "cycles"
    })

    # SOH deviation from expected shadow
    rows.append({
        "Parameter":    "SOH vs Shadow Curve",
        "Live Value":   f"{state.soh_pct:.1f} %",
        "Reference":    f"{state.expected_soh_pct:.1f} % (expected)",
        "Deviation":    f"{state.soh_deviation_pct:+.1f} %",
        "Status":       "NORMAL" if state.soh_deviation_pct >= -5 else
                        ("WARNING" if state.soh_deviation_pct >= -15 else "CRITICAL"),
        "Unit":         "%"
    })

    return pd.DataFrame(rows)


# ------------------------------------------------------------------ #
# 8.  AGING CURVE DATA FOR PLOTTING                                   #
# ------------------------------------------------------------------ #

def aging_curve_data(state: BatteryState) -> pd.DataFrame:
    cycles         = np.arange(0, 2001, 10)
    shadow_soh     = aging_shadow_curve(cycles)

    # Adaptive line: same shadow but performance boosted by AI model
    adaptive_soh   = np.minimum(100, shadow_soh * 1.22 - 2.5)
    adaptive_soh   = np.clip(adaptive_soh, 0, 100)

    df = pd.DataFrame({
        "Cycle Count":          cycles,
        "Shadow (Manufacturer)": shadow_soh,
        "AI-Adaptive Extended": adaptive_soh,
    })
    return df

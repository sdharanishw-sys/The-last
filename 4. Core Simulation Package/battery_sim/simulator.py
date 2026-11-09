"""
Simulation engine for battery electro-thermal analysis.
Executes time-stepping numerical integration, monitors BMS limits,
and generates structured time-series data with clear trajectory accounting.
"""

from __future__ import annotations
import csv
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from .cell_model import BatteryCell, CellParameters
from .profiles import LoadProfile, TemperatureProfile, ConstantCurrentProfile, ConstantTempProfile


@dataclass
class SimulationStep:
    """Individual time-step telemetry data point."""
    time_s: float
    current_a: float
    v_terminal: float
    v_ocv: float
    v_rc1: float
    v_rc2: float
    soc: float
    soc_pct: float
    cell_temp_c: float
    ambient_temp_c: float
    r0_mohm: float
    power_w: float
    q_generated_w: float
    q_dissipated_w: float
    ah_throughput: float
    cumulative_energy_wh: float


class SimulationResult:
    """Encapsulates the recorded data, metrics, and export capabilities of a simulation run."""

    def __init__(
        self,
        steps: List[SimulationStep],
        metadata: Dict[str, Any],
        termination_reason: str,
    ) -> None:
        self.steps = steps
        self.metadata = metadata
        self.termination_reason = termination_reason

    def __len__(self) -> int:
        return len(self.steps)

    def to_dict_series(self) -> Dict[str, List[float]]:
        if not self.steps:
            return {}
        keys = list(asdict(self.steps[0]).keys())
        res: Dict[str, List[float]] = {k: [] for k in keys}
        for s in self.steps:
            d = asdict(s)
            for k in keys:
                res[k].append(d[k])
        return res

    def to_dataframe(self):
        try:
            import pandas as pd
            return pd.DataFrame([asdict(s) for s in self.steps])
        except ImportError:
            raise ImportError("pandas is not installed.")

    def to_csv(self, filepath: str) -> None:
        if not self.steps:
            raise ValueError("No data to export.")
        fieldnames = list(asdict(self.steps[0]).keys())
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for step in self.steps:
                writer.writerow(asdict(step))

    def to_json(self, filepath: str) -> None:
        data = {
            "metadata": self.metadata,
            "termination_reason": self.termination_reason,
            "data": [asdict(s) for s in self.steps],
        }
        with open(filepath, mode="w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def summary(self) -> str:
        m = self.metadata
        dur = m.get("duration_s", 0.0)
        steps_count = m.get("physics_steps_executed", len(self.steps) - 1)
        lines = [
            "=" * 68,
            f"             BATTERY SIMULATION REPORT ({m.get('chemistry', 'NMC')})",
            "=" * 68,
            f"  Termination Reason      : {self.termination_reason}",
            f"  Simulated Elapsed Time  : {dur:.1f} s ({dur/60.0:.2f} min)",
            f"  Physics Steps Executed  : {steps_count} steps (dt = {m.get('dt_s', 1.0):.2f} s)",
            f"  Trajectory Points Saved : {len(self.steps)} (t=0.0s initial state + {steps_count} steps)",
            "-" * 68,
            f"  Initial SOC             : {m.get('initial_soc_pct', 0):.2f} %",
            f"  Final SOC               : {m.get('final_soc_pct', 0):.2f} %",
            f"  Delta SOC               : {m.get('delta_soc_pct', 0):.2f} %",
            "-" * 68,
            f"  Initial Voltage         : {m.get('initial_v', 0):.3f} V",
            f"  Final Voltage           : {m.get('final_v', 0):.3f} V",
            f"  Min / Max Voltage       : {m.get('min_v', 0):.3f} V / {m.get('max_v', 0):.3f} V",
            "-" * 68,
            f"  Initial Cell Temp       : {m.get('initial_temp_c', 0):.1f} C",
            f"  Final Cell Temp         : {m.get('final_temp_c', 0):.1f} C",
            f"  Min / Max Cell Temp     : {m.get('min_temp_c', 0):.1f} C / {m.get('max_temp_c', 0):.1f} C",
            f"  Peak Temp Rise          : {m.get('peak_temp_rise_c', 0):.2f} C",
            "-" * 68,
            f"  Peak Discharge Current  : {m.get('max_discharge_a', 0):.2f} A ({m.get('max_discharge_c_rate', 0):.2f} C-rate)",
            f"  Peak Charge Current     : {m.get('max_charge_a', 0):.2f} A ({m.get('max_charge_c_rate', 0):.2f} C-rate)",
            f"  Total Ah Delivered      : {m.get('discharge_ah', 0):.3f} Ah",
            f"  Total Energy (Wh)       : {m.get('discharge_wh', 0):.3f} Wh (discharge) / {m.get('charge_wh', 0):.3f} Wh (charge)",
            f"  Max Heat Generation     : {m.get('peak_q_gen_w', 0):.2f} W",
            "=" * 68,
        ]
        return "\n".join(lines)


class BatterySimulator:
    """
    Simulation supervisor connecting battery physics, load profiles,
    and ambient environments with BMS safety cutoffs.
    """

    def __init__(
        self,
        cell: Optional[BatteryCell] = None,
        cell_params: Optional[CellParameters] = None,
        load_profile: Optional[LoadProfile] = None,
        temperature_profile: Optional[TemperatureProfile] = None,
        dt: float = 1.0,
        max_duration_s: float = 3600.0,
        v_cutoff_min: Optional[float] = None,
        v_cutoff_max: Optional[float] = None,
        temp_cutoff_max_c: float = 60.0,
        temp_cutoff_min_charge_c: float = 0.0,
        soc_cutoff_min: float = 0.005,
        soc_cutoff_max: float = 1.0,
    ) -> None:
        self.cell = cell if cell is not None else BatteryCell(params=cell_params)
        self.load_profile = load_profile or ConstantCurrentProfile(1.5)
        self.temperature_profile = temperature_profile or ConstantTempProfile(25.0)
        self.dt = float(dt)
        self.max_duration_s = float(max_duration_s)

        # Safety / BMS thresholds
        self.v_cutoff_min = v_cutoff_min if v_cutoff_min is not None else self.cell.params.v_min
        self.v_cutoff_max = v_cutoff_max if v_cutoff_max is not None else (self.cell.params.v_max + 0.05)
        self.temp_cutoff_max_c = float(temp_cutoff_max_c)
        self.temp_cutoff_min_charge_c = float(temp_cutoff_min_charge_c)
        self.soc_cutoff_min = float(soc_cutoff_min)
        self.soc_cutoff_max = float(soc_cutoff_max)

    def run(self) -> SimulationResult:
        """
        Executes time-stepping numerical integration.
        Recording convention:
          - Point 0 at t = 0.0s records initial battery state before applying time steps.
          - Points 1..N at t = k*dt record state after each physics integration interval.
          - Total physical duration simulated = N * dt.
        """
        steps: List[SimulationStep] = []
        initial_soc = self.cell.soc
        initial_temp = self.cell.temperature_c

        # Determine target duration and number of steps
        profile_duration = self.load_profile.duration()
        target_duration = (
            min(self.max_duration_s, profile_duration)
            if profile_duration is not None
            else self.max_duration_s
        )
        total_steps = max(1, int(round(target_duration / self.dt)))

        # 0. Record initial baseline state at t = 0.0s (pre-step)
        i0 = float(self.load_profile.get_current(0.0))
        t_amb0 = float(self.temperature_profile.get_temperature(0.0))
        v_ocv0 = self.cell.open_circuit_voltage()
        r0_0 = self.cell.ohmic_resistance()
        v_term0 = v_ocv0 - (i0 * r0_0) - self.cell.v_rc1 - self.cell.v_rc2

        steps.append(
            SimulationStep(
                time_s=0.0,
                current_a=round(i0, 4),
                v_terminal=round(v_term0, 4),
                v_ocv=round(v_ocv0, 4),
                v_rc1=round(self.cell.v_rc1, 5),
                v_rc2=round(self.cell.v_rc2, 5),
                soc=round(self.cell.soc, 5),
                soc_pct=round(self.cell.soc * 100.0, 3),
                cell_temp_c=round(self.cell.temperature_c, 2),
                ambient_temp_c=round(t_amb0, 2),
                r0_mohm=round(r0_0 * 1000.0, 2),
                power_w=round(v_term0 * i0, 3),
                q_generated_w=0.0,
                q_dissipated_w=0.0,
                ah_throughput=0.0,
                cumulative_energy_wh=0.0,
            )
        )

        termination_reason = "Completed target duration"
        start_perf = time.perf_counter()
        steps_executed = 0

        # Steps 1 to N
        for k in range(1, total_steps + 1):
            t_curr = k * self.dt
            current_requested = float(self.load_profile.get_current(t_curr))
            ambient_temp = float(self.temperature_profile.get_temperature(t_curr))

            # 1. BMS Safety check: sub-zero charging lockout
            if current_requested < -0.1 and self.cell.temperature_c < self.temp_cutoff_min_charge_c:
                termination_reason = (
                    f"BMS Cutoff: Sub-zero charging lockout triggered (Temp={self.cell.temperature_c:.1f}C < {self.temp_cutoff_min_charge_c}C)"
                )
                break

            # 2. BMS Safety check: over-temperature lockout
            if self.cell.temperature_c >= self.temp_cutoff_max_c:
                termination_reason = (
                    f"BMS Cutoff: Over-temperature safety trip ({self.cell.temperature_c:.1f}C >= {self.temp_cutoff_max_c}C)"
                )
                break

            # 3. Advance cell physical state by dt
            diag = self.cell.step(
                current=current_requested,
                ambient_temp_c=ambient_temp,
                dt=self.dt,
            )
            steps_executed += 1

            # 4. Record step telemetry
            step = SimulationStep(
                time_s=round(t_curr, 4),
                current_a=round(diag["current"], 4),
                v_terminal=round(diag["v_terminal"], 4),
                v_ocv=round(diag["v_ocv"], 4),
                v_rc1=round(diag["v_rc1"], 5),
                v_rc2=round(diag["v_rc2"], 5),
                soc=round(diag["soc"], 5),
                soc_pct=round(diag["soc_pct"], 3),
                cell_temp_c=round(diag["cell_temp_c"], 2),
                ambient_temp_c=round(diag["ambient_temp_c"], 2),
                r0_mohm=round(diag["r0_mohm"], 2),
                power_w=round(diag["power_w"], 3),
                q_generated_w=round(diag["q_generated_w"], 3),
                q_dissipated_w=round(diag["q_dissipated_w"], 3),
                ah_throughput=round(self.cell.cumulative_ah_throughput, 4),
                cumulative_energy_wh=round(
                    self.cell.cumulative_energy_wh_discharge - self.cell.cumulative_energy_wh_charge, 4
                ),
            )
            steps.append(step)

            # 5. Check Voltage and SOC Cutoffs
            if diag["v_terminal"] <= self.v_cutoff_min:
                termination_reason = (
                    f"BMS Cutoff: Under-voltage cutoff reached ({diag['v_terminal']:.3f}V <= {self.v_cutoff_min:.3f}V)"
                )
                break
            if diag["v_terminal"] >= self.v_cutoff_max:
                termination_reason = (
                    f"BMS Cutoff: Over-voltage cutoff reached ({diag['v_terminal']:.3f}V >= {self.v_cutoff_max:.3f}V)"
                )
                break
            if self.cell.soc <= self.soc_cutoff_min:
                termination_reason = (
                    f"BMS Cutoff: Minimum State-of-Charge reached ({self.cell.soc*100:.1f}%)"
                )
                break
            if self.cell.soc >= self.soc_cutoff_max and current_requested < 0:
                termination_reason = (
                    f"BMS Cutoff: Battery fully charged (SOC 100%)"
                )
                break

        sim_exec_time = time.perf_counter() - start_perf
        actual_simulated_duration = steps_executed * self.dt

        # Metadata
        v_vals = [s.v_terminal for s in steps]
        t_vals = [s.cell_temp_c for s in steps]
        i_vals = [s.current_a for s in steps]
        q_vals = [s.q_generated_w for s in steps]
        nom_cap = self.cell.params.nominal_capacity_ah
        max_dis = max(0.0, max(i_vals))
        max_chg = max(0.0, -min(i_vals))

        metadata = {
            "chemistry": self.cell.params.chemistry.value,
            "duration_s": actual_simulated_duration,
            "dt_s": self.dt,
            "physics_steps_executed": steps_executed,
            "trajectory_points": len(steps),
            "sim_execution_seconds": round(sim_exec_time, 4),
            "initial_soc_pct": round(initial_soc * 100.0, 2),
            "final_soc_pct": round(steps[-1].soc_pct, 2),
            "delta_soc_pct": round(abs(initial_soc * 100.0 - steps[-1].soc_pct), 2),
            "initial_v": steps[0].v_terminal,
            "final_v": steps[-1].v_terminal,
            "min_v": min(v_vals),
            "max_v": max(v_vals),
            "initial_temp_c": initial_temp,
            "final_temp_c": steps[-1].cell_temp_c,
            "min_temp_c": min(t_vals),
            "max_temp_c": max(t_vals),
            "peak_temp_rise_c": round(max(t_vals) - initial_temp, 2),
            "max_discharge_a": round(max_dis, 2),
            "max_discharge_c_rate": round(max_dis / nom_cap, 2),
            "max_charge_a": round(max_chg, 2),
            "max_charge_c_rate": round(max_chg / nom_cap, 2),
            "discharge_ah": round(self.cell.cumulative_ah_throughput, 3),
            "discharge_wh": round(self.cell.cumulative_energy_wh_discharge, 3),
            "charge_wh": round(self.cell.cumulative_energy_wh_charge, 3),
            "peak_q_gen_w": max(q_vals),
        }

        return SimulationResult(
            steps=steps,
            metadata=metadata,
            termination_reason=termination_reason,
        )

"""
Phase 2: Personalized Reference Model Runner
=============================================
Demonstrates the full pipeline:

  Step 1 — Calibrate: Run standardized characterization protocol on cell to
            extract its unique baseline fingerprint (capacity, DCIR, OCV, thermal).

  Step 2 — Run: Execute an operational simulation (e.g. EV drive cycle or HPPC)
            with the DeviationTracker attached at each step.

  Step 3 — Compare: After the run, finalize the DeviationReport showing
            signed residuals (V_measured − V_predicted), DCIR drift, thermal
            imbalance, and composite anomaly scores at every time step.

Supports multiple cells in the same session to demonstrate per-cell personalization.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import copy
import random
import time

from battery_sim.cell_model import BatteryCell, CellParameters, ChemistryType
from battery_sim.profiles import (
    DriveCycleProfile,
    ConstantCurrentProfile,
    SinusoidalTempProfile,
    ConstantTempProfile,
    PulseProfile,
)
from battery_sim.reference_model import BaselineCalibrator, DeviationTracker
from battery_sim.simulator import BatterySimulator
from battery_sim.visualizer import export_svg, generate_interactive_html


def make_cell(
    nominal_capacity_ah: float = 3.0,
    r0_offset: float = 0.0,
    initial_soc: float = 0.85,
    initial_temp_c: float = 25.0,
    chemistry: ChemistryType = ChemistryType.NMC,
) -> BatteryCell:
    """
    Builds a BatteryCell with optional parameter perturbation to simulate
    individual cell manufacturing spread.
    """
    if chemistry == ChemistryType.NMC:
        params = CellParameters.default_nmc()
    else:
        params = CellParameters.default_lfp()

    params.nominal_capacity_ah = nominal_capacity_ah
    params.r0_ref += r0_offset     # Shift base resistance to simulate an aged or cold cell

    return BatteryCell(params=params, initial_soc=initial_soc, initial_temp_c=initial_temp_c)


def run_phase2_single_cell(
    cell_id: str = "CELL-A",
    nominal_cap: float = 3.0,
    r0_offset: float = 0.0,
    load_profile_name: str = "drive-cycle",
    ambient_temp_c: float = 25.0,
    sim_duration_s: float = 600.0,
    save_json: bool = True,
    save_csv: bool = True,
    save_html: bool = True,
    save_svg: bool = True,
) -> None:
    """
    Full Phase 2 pipeline for a single cell:
      1. Calibrate → build CellBaseline fingerprint
      2. Simulate operational load with DeviationTracker
      3. Report comparison: measured vs baseline-predicted values
    """
    print("=" * 70)
    print(f"  PHASE 2 — PERSONALIZED REFERENCE MODEL  [{cell_id}]")
    print("=" * 70)

    # ── Step 1: Calibration ──────────────────────────────────────────────────
    print(f"\n[1/3] Calibrating {cell_id}...")
    cal_cell = make_cell(
        nominal_capacity_ah=nominal_cap,
        r0_offset=r0_offset,
        initial_soc=1.0,
        initial_temp_c=25.0,
    )
    calibrator = BaselineCalibrator(cal_cell, cell_id=cell_id)
    t0 = time.perf_counter()
    baseline = calibrator.build()
    cal_time = time.perf_counter() - t0

    print(f"    Calibration complete ({cal_time:.2f}s elapsed)")
    print(f"    Nominal Capacity (spec) : {baseline.nominal_capacity_ah:.3f} Ah")
    print(f"    Measured Cap @ 25 deg C : {baseline.capacity.reference_ah:.3f} Ah")
    print(f"    DCIR @ SOC=50%, 25C     : {baseline.impedance.dcir_reference_mohm:.2f} mOhm")
    print(f"    OCV RMS Deviation       : {baseline.ocv.rms_deviation_mv:.2f} mV")
    print(f"    Thermal Time Constant   : {baseline.thermal.thermal_time_constant_s:.1f} s")
    print(f"    State of Health         : {baseline.state_of_health_pct:.1f} %")

    if save_json:
        bsl_path = f"{cell_id}_baseline.json"
        baseline.to_json(bsl_path)
        print(f"    Baseline saved          : {bsl_path}")

    # ── Step 2: Operational Simulation with Tracker ──────────────────────────
    print(f"\n[2/3] Running operational simulation ({load_profile_name}, {sim_duration_s:.0f}s)...")

    op_cell = make_cell(
        nominal_capacity_ah=nominal_cap,
        r0_offset=r0_offset,
        initial_soc=0.85,
        initial_temp_c=ambient_temp_c,
    )

    if load_profile_name == "drive-cycle":
        load = DriveCycleProfile(peak_current_a=6.0, regen_ratio=0.35, duration_s=sim_duration_s)
    elif load_profile_name == "pulse":
        load = PulseProfile(base_current_a=0.5, pulse_current_a=3.0, pulse_width_s=8.0, period_s=30.0, duration_s=sim_duration_s)
    else:
        load = ConstantCurrentProfile(current_a=1.5, duration_s=sim_duration_s)

    temp_prof = SinusoidalTempProfile(mean_temp_c=ambient_temp_c, amplitude_c=5.0, period_s=sim_duration_s)

    # Attach tracker
    tracker = DeviationTracker(baseline=baseline, cell=op_cell)

    # Manual stepping loop — record after every step
    dt = 2.0
    total_steps = max(1, int(sim_duration_s / dt))
    sim_steps_done = 0

    for k in range(total_steps):
        t_curr = (k + 1) * dt
        current = float(load.get_current(t_curr))
        ambient = float(temp_prof.get_temperature(t_curr))

        diag = op_cell.step(current=current, ambient_temp_c=ambient, dt=dt)

        if diag["v_terminal"] <= op_cell.params.v_min:
            break

        tracker.record(
            time_s=t_curr,
            current_a=current,
            soc=diag["soc"],
            v_measured=diag["v_terminal"],
            dcir_measured_mohm=diag["r0_mohm"],
            cell_temp_c=diag["cell_temp_c"],
            ambient_temp_c=ambient,
        )
        sim_steps_done += 1

    print(f"    Simulation steps executed : {sim_steps_done}")
    print(f"    Final SOC                 : {op_cell.soc * 100.0:.1f} %")

    # ── Step 3: Finalize deviation report ────────────────────────────────────
    print(f"\n[3/3] Comparing measured vs predicted values...")
    report = tracker.finalize()
    print()
    print(report.summary())

    if save_csv:
        csv_path = f"{cell_id}_deviations.csv"
        report.to_csv(csv_path)
        print(f"\n    CSV deviation log saved : {csv_path}")

    if save_json:
        json_path = f"{cell_id}_deviation_report.json"
        report.to_json(json_path)
        print(f"    JSON report saved       : {json_path}")


def run_multi_cell_comparison(
    num_cells: int = 3,
    sim_duration_s: float = 600.0,
) -> None:
    """
    Compares the reference model deviations across a fleet of cells
    with different resistance offsets to illustrate cell-specific personalization.
    """
    print("\n" + "=" * 70)
    print("  PHASE 2 — MULTI-CELL FLEET COMPARISON")
    print("=" * 70)

    # Simulate a fleet with varying aging and resistance spread
    fleet_configs = [
        {"cell_id": "FLEET-NMC-NEW",   "r0_offset":  0.000, "cap": 3.00, "label": "Fresh NMC"},
        {"cell_id": "FLEET-NMC-MILD",  "r0_offset":  0.004, "cap": 2.88, "label": "Mildly aged NMC"},
        {"cell_id": "FLEET-NMC-AGED",  "r0_offset":  0.012, "cap": 2.61, "label": "Significantly aged NMC"},
    ]

    print(f"\n{'Cell ID':<22} | {'SOH':>6} | {'DCIR_ref (mOhm)':>16} | {'V_RMS (mV)':>10} | {'AnomalyScore':>12} | {'Label'}")
    print("-" * 90)

    for cfg in fleet_configs:
        # Calibrate
        cal_cell = make_cell(nominal_capacity_ah=cfg["cap"], r0_offset=cfg["r0_offset"])
        calibrator = BaselineCalibrator(cal_cell, cell_id=cfg["cell_id"])
        baseline = calibrator.build()

        # Operational run
        op_cell = make_cell(nominal_capacity_ah=cfg["cap"], r0_offset=cfg["r0_offset"], initial_soc=0.85)
        load = DriveCycleProfile(peak_current_a=5.5, duration_s=sim_duration_s)
        temp = ConstantTempProfile(25.0)
        tracker = DeviationTracker(baseline=baseline, cell=op_cell)

        dt = 2.0
        for k in range(int(sim_duration_s / dt)):
            t = (k + 1) * dt
            current = float(load.get_current(t))
            diag = op_cell.step(current=current, ambient_temp_c=25.0, dt=dt)
            if diag["v_terminal"] <= op_cell.params.v_min:
                break
            tracker.record(
                time_s=t,
                current_a=current,
                soc=diag["soc"],
                v_measured=diag["v_terminal"],
                dcir_measured_mohm=diag["r0_mohm"],
                cell_temp_c=diag["cell_temp_c"],
                ambient_temp_c=25.0,
            )

        report = tracker.finalize()
        print(
            f"{cfg['cell_id']:<22} | {report.soh_estimate_pct:>5.1f}% | "
            f"{baseline.impedance.dcir_reference_mohm:>16.2f} | "
            f"{report.v_rms_residual_mv:>10.2f} | "
            f"{report.anomaly_score_mean:>12.4f} | "
            f"{cfg['label']}"
        )

    print("-" * 90)


def main() -> None:
    # ── Single cell: fresh NMC under drive cycle ─────────────────────────────
    run_phase2_single_cell(
        cell_id="CELL-NMC-001",
        nominal_cap=3.0,
        r0_offset=0.0,
        load_profile_name="drive-cycle",
        ambient_temp_c=25.0,
        sim_duration_s=600.0,
    )

    # ── Single cell: aged NMC (higher R0) under pulse load ───────────────────
    print()
    run_phase2_single_cell(
        cell_id="CELL-NMC-AGED",
        nominal_cap=2.7,
        r0_offset=0.010,
        load_profile_name="pulse",
        ambient_temp_c=10.0,
        sim_duration_s=600.0,
    )

    # ── Fleet comparison table ────────────────────────────────────────────────
    run_multi_cell_comparison(num_cells=3, sim_duration_s=600.0)

    print("\n[+] Phase 2 complete.\n")


if __name__ == "__main__":
    main()

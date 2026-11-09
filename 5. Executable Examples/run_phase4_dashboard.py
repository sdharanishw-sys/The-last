"""
Phase 4: Dashboard & Validation Benchmark Demo
==============================================
Runs an end-to-end demonstration of the Phase 4 validation engine:
  1. Calibrates an electro-thermal reference baseline (CellBaseline).
  2. Runs a realistic dynamic simulation with subtle degradation (+14 mOhm contact corrosion).
  3. Evaluates Fixed-Threshold Baseline vs Adaptive Reference Model in real-time.
  4. Executes the comprehensive 7-scenario validation benchmark suite.
  5. Generates the self-contained interactive HTML dashboard (phase4_dashboard.html).
  6. Exports benchmark metrics to phase4_validation_report.json and alerts to phase4_alerts.csv.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import csv
import json
import time

from battery_sim.cell_model import BatteryCell, CellParameters
from battery_sim.profiles import DriveCycleProfile, LoadProfile
from battery_sim.reference_model import BaselineCalibrator
from battery_sim.fault_attribution import (
    FaultType,
    FaultScenarioConfig,
    FaultyCell,
    FaultAttributionEngine,
)
from battery_sim.validation import (
    FixedThresholdMonitor,
    AdaptiveReferenceMonitor,
    BenchmarkRunner,
    AlertEvent,
)
from battery_sim.visualizer import generate_phase4_dashboard


class DriveCycleWithRest(LoadProfile):
    """EV dynamic load profile with periodic resting intervals (I = 0)."""

    def __init__(self, base_duration_s: float = 480.0) -> None:
        self.base_drive = DriveCycleProfile(peak_current_a=5.5, regen_ratio=0.30, duration_s=base_duration_s)
        self._duration_s = base_duration_s

    def get_current(self, t: float) -> float:
        # Every 80s, insert 15s zero-current rest
        phase = t % 80.0
        if 55.0 <= phase < 70.0:
            return 0.0
        return self.base_drive.get_current(t)

    def duration(self) -> float:
        return self._duration_s


def main():
    print("=" * 76)
    print("      PHASE 4: BATTERY HEALTH DASHBOARD & BENCHMARK VALIDATION")
    print("=" * 76)

    # ── 1. Calibrate Baseline Reference Model ──────────────────────────────────
    print("\n[*] Step 1: Calibrating baseline reference model (NMC 3.0Ah cell)...")
    cal_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=1.0, initial_temp_c=25.0)
    t0 = time.perf_counter()
    calibrator = BaselineCalibrator(cal_cell, cell_id="NMC-PHASE4-REF")
    baseline = calibrator.build()
    print(f"    [+] Reference baseline calibrated in {time.perf_counter() - t0:.2f}s")
    print(f"    [+] Reference DCIR: {baseline.impedance.dcir_reference_mohm:.2f} mOhm (at 50% SOC, 25 deg C)")
    print(f"    [+] Nominal Capacity: {baseline.capacity.reference_ah:.3f} Ah")
    print(f"    [+] Thermal Time Constant: {baseline.thermal.thermal_time_constant_s:.1f} s")

    # ── 2. Run Operational Drive Cycle with Injected Subtle Degradation ────────
    print("\n[*] Step 2: Simulating operational drive cycle with subtle fault injection...")
    fault_cfg = FaultScenarioConfig(
        fault_type=FaultType.INCREASED_RESISTANCE,
        resistance_adder_ohm=0.014,  # +14 mOhm early contact corrosion / degradation
        description="Early contact corrosion (+14 mOhm added impedance)",
    )
    print(f"    [+] Condition: {fault_cfg.description}")

    sim_cell = FaultyCell(
        base_cell=BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.90, initial_temp_c=25.0),
        config=fault_cfg,
        seed=42,
    )
    ref_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.90, initial_temp_c=25.0)

    fixed_mon = FixedThresholdMonitor()
    adapt_mon = AdaptiveReferenceMonitor(baseline=baseline, cell=ref_cell)

    load_profile = DriveCycleWithRest(base_duration_s=420.0)
    dt = 2.0
    total_steps = int(load_profile.duration() / dt)

    sim_history = []
    combined_alerts: list[AlertEvent] = []

    print(f"    [+] Stepping {total_steps} physical integration steps (dt = {dt:.1f}s)...")
    for step_idx in range(total_steps):
        t_curr = (step_idx + 1) * dt
        i_load = load_profile.get_current(t_curr)

        diag = sim_cell.step(current=i_load, ambient_temp_c=25.0, dt=dt)
        sim_history.append(diag)

        if diag["v_terminal"] <= sim_cell.params.v_min:
            print(f"    [!] Cell reached cutoff at t = {t_curr:.1f}s")
            break

        # Check Fixed Threshold Monitor
        fixed_step_alerts = fixed_mon.check_step(
            time_s=t_curr,
            v_measured=diag["v_terminal"],
            current_a=diag["current"],
            cell_temp_c=diag["cell_temp_c"],
            dcir_measured_mohm=diag["r0_mohm"],
        )
        combined_alerts.extend(fixed_step_alerts)

        # Check Adaptive Reference Monitor
        adapt_step_alerts, _ = adapt_mon.check_step(
            time_s=t_curr,
            v_measured=diag["v_terminal"],
            current_a=diag["current"],
            soc=diag["soc"],
            cell_temp_c=diag["cell_temp_c"],
            ambient_temp_c=25.0,
            dcir_measured_mohm=diag["r0_mohm"],
            dt=dt,
        )
        combined_alerts.extend(adapt_step_alerts)

    dev_report = adapt_mon.finalize()
    diag_engine = FaultAttributionEngine(baseline=baseline, cell=ref_cell)
    diagnosis = diag_engine.diagnose(dev_report, sim_history)

    print("\n[*] Operational Test Results:")
    print(f"    Fixed Monitor Tripped?    : {fixed_mon.has_tripped} (Alerts: {len(fixed_mon.alerts)})")
    print(f"    Adaptive Monitor Tripped? : {adapt_mon.has_tripped} (Alerts: {len(adapt_mon.alerts)})")
    print(f"    Adaptive First Alert Time : {adapt_mon.first_detection_time} s")
    print(f"    Attributed Root Cause     : {diagnosis.attributed_fault.value}")
    print(f"    Attribution Confidence    : {diagnosis.confidence * 100.0:.1f}%")
    print(f"    Severity Assessment       : {diagnosis.severity_estimate}")

    # ── 3. Run Validation Benchmark Suite ──────────────────────────────────────
    print("\n[*] Step 3: Executing comprehensive benchmark suite (7 diverse test scenarios)...")
    runner = BenchmarkRunner(baseline=baseline)
    t_bm0 = time.perf_counter()
    summary = runner.run_benchmark(sim_duration_s=360.0, dt=2.0)
    print(f"    [+] Benchmark completed in {time.perf_counter() - t_bm0:.2f}s")
    print(summary.summary())

    # ── 4. Generate Interactive Dashboard ─────────────────────────────────────
    print("\n[*] Step 4: Generating self-contained Phase 4 Dashboard (HTML5 Canvas)...")
    html_path = "phase4_dashboard.html"
    generate_phase4_dashboard(
        telemetry=sim_history,
        deviation_report=dev_report,
        diagnosis=diagnosis,
        benchmark_summary=summary,
        alerts=combined_alerts,
        output_path=html_path,
        title="Battery Simulation & Validation Benchmark Dashboard (Phase 4)",
    )
    print(f"    [+] Dashboard saved: {html_path} (100% offline, zero CDN dependencies)")

    # ── 5. Export JSON Validation Report & CSV Alerts ──────────────────────────
    print("\n[*] Step 5: Exporting validation report & alerts log...")
    report_json_path = "phase4_validation_report.json"
    report_data = {
        "metadata": {
            "timestamp": time.time(),
            "cell_id": "NMC-PHASE4-REF",
            "chemistry": "NMC Lithium-Ion",
            "benchmark_scenarios_count": summary.total_scenarios,
        },
        "benchmark_summary": {
            "fixed_accuracy_pct": summary.fixed_accuracy_pct,
            "fixed_false_positive_rate_pct": summary.fixed_false_positive_rate_pct,
            "fixed_false_negative_rate_pct": summary.fixed_false_negative_rate_pct,
            "fixed_mean_detection_time_s": summary.fixed_mean_detection_time_s,
            "fixed_attribution_capability_pct": summary.fixed_attribution_capability_pct,
            "adaptive_accuracy_pct": summary.adaptive_accuracy_pct,
            "adaptive_false_positive_rate_pct": summary.adaptive_false_positive_rate_pct,
            "adaptive_false_negative_rate_pct": summary.adaptive_false_negative_rate_pct,
            "adaptive_mean_detection_time_s": summary.adaptive_mean_detection_time_s,
            "adaptive_attribution_capability_pct": summary.adaptive_attribution_capability_pct,
        },
        "operational_run": {
            "injected_fault": fault_cfg.description,
            "fixed_monitor_tripped": fixed_mon.has_tripped,
            "adaptive_monitor_tripped": adapt_mon.has_tripped,
            "adaptive_attributed_cause": diagnosis.attributed_fault.value,
            "adaptive_confidence_pct": round(diagnosis.confidence * 100.0, 1),
            "adaptive_severity": diagnosis.severity_estimate,
        },
        "scenarios": [
            {
                "name": sc.scenario_name,
                "description": sc.scenario_description,
                "is_fault": sc.is_fault,
                "ground_truth": sc.ground_truth_fault.value,
                "fixed_detected": sc.fixed_detected,
                "fixed_ttd_s": sc.fixed_detection_time_s,
                "fixed_false_alarm": sc.fixed_false_alarm,
                "adaptive_detected": sc.adaptive_detected,
                "adaptive_ttd_s": sc.adaptive_detection_time_s,
                "adaptive_cause": sc.adaptive_attributed_cause,
                "adaptive_confidence_pct": round(sc.adaptive_confidence_pct, 1),
                "adaptive_severity": sc.adaptive_severity_estimate,
            }
            for sc in summary.scenarios
        ],
    }
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"    [+] Validation report saved: {report_json_path}")

    csv_alerts_path = "phase4_alerts.csv"
    with open(csv_alerts_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time_s",
            "severity",
            "source_monitor",
            "parameter",
            "message",
            "measured_value",
            "threshold_or_expected",
            "residual_or_delta",
        ])
        for a in combined_alerts:
            writer.writerow([
                round(a.time_s, 2),
                a.severity.value if hasattr(a.severity, "value") else str(a.severity),
                a.source_monitor,
                a.parameter,
                a.message,
                round(a.measured_value, 4),
                round(a.threshold_or_expected, 4),
                round(a.residual_or_delta, 4),
            ])
    print(f"    [+] Alerts log saved: {csv_alerts_path} ({len(combined_alerts)} records)")

    print("\n" + "=" * 76)
    print("  PHASE 4 VALIDATION DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("=" * 76)


if __name__ == "__main__":
    main()

"""
Phase 3: Fault Attribution Evaluation & Benchmark
=================================================
Introduces controlled physical and sensory fault scenarios:
  1. Nominal (Healthy baseline with standard measurement noise)
  2. Increased Internal Resistance (Ohmic / contact degradation, SEI growth)
  3. Abnormal Temperature Rise (Cooling failure, micro-short heat flux)
  4. Capacity Fade (Active lithium loss, electrode material degradation)
  5. Voltage Sensor Bias (+45 mV positive calibration drift)
  6. Negative Voltage Sensor Bias (-35 mV negative calibration drift)

Executes each scenario under an operational dynamic profile with resting intervals,
runs the FaultAttributionEngine, and evaluates classification accuracy,
confusion matrix, and parameter severity estimation error.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
from typing import Dict, List, Any

from battery_sim.cell_model import BatteryCell, CellParameters, ChemistryType
from battery_sim.profiles import DriveCycleProfile, ConstantTempProfile, LoadProfile
from battery_sim.reference_model import BaselineCalibrator, DeviationTracker
from battery_sim.fault_attribution import (
    FaultType,
    FaultScenarioConfig,
    FaultyCell,
    FaultAttributionEngine,
    FaultDiagnosis,
)


class DriveCycleWithRest(LoadProfile):
    """
    Combines active dynamic EV drive cycle with periodic equilibrium rest periods (I = 0).
    Rest periods allow the diagnostic engine to separate static sensor offsets
    from current-proportional Ohmic resistance drops!
    """

    def __init__(self, base_duration_s: float = 600.0) -> None:
        self.base_drive = DriveCycleProfile(peak_current_a=5.5, regen_ratio=0.35, duration_s=base_duration_s)
        self._duration_s = base_duration_s

    def get_current(self, t: float) -> float:
        # Every 120s, insert a 25s zero-current rest period
        cycle_phase = t % 120.0
        if 85.0 <= cycle_phase < 110.0:
            return 0.0  # Zero-current rest
        return self.base_drive.get_current(t)

    def duration(self) -> float:
        return self._duration_s


def run_fault_evaluation():
    print("=" * 72)
    print("        PHASE 3: FAULT ATTRIBUTION & DIAGNOSTICS EVALUATION")
    print("=" * 72)

    # ── Step 1: Calibrate Healthy Reference Baseline ──────────────────────────
    print("\n[*] Step 1: Calibrating healthy baseline reference cell (NMC 3.0Ah)...")
    base_params = CellParameters.default_nmc()
    cal_cell = BatteryCell(params=base_params, initial_soc=1.0, initial_temp_c=25.0)
    calibrator = BaselineCalibrator(cal_cell, cell_id="NMC-REF-BASELINE")
    t0 = time.perf_counter()
    baseline = calibrator.build()
    print(f"    Calibration complete in {time.perf_counter() - t0:.2f}s")
    print(f"    Baseline Reference DCIR: {baseline.impedance.dcir_reference_mohm:.2f} mOhm")
    print(f"    Baseline Reference Cap : {baseline.capacity.reference_ah:.3f} Ah")
    print(f"    Baseline Thermal Tau   : {baseline.thermal.thermal_time_constant_s:.1f} s")

    # ── Step 2: Define Controlled Fault Scenarios ─────────────────────────────
    scenarios = [
        FaultScenarioConfig(
            fault_type=FaultType.NOMINAL,
            description="Nominal healthy baseline with standard sensor noise (0 mV bias, 0 mOhm)",
        ),
        FaultScenarioConfig(
            fault_type=FaultType.INCREASED_RESISTANCE,
            description="Increased internal resistance (+22 mOhm contact/electrolyte degradation)",
            resistance_adder_ohm=0.022,
        ),
        FaultScenarioConfig(
            fault_type=FaultType.TEMPERATURE_RISE,
            description="Abnormal thermal rise (80% cooling loss + 2.0W micro-short heat flux)",
            cooling_factor=0.20,
            external_heat_flux_w=2.0,
        ),
        FaultScenarioConfig(
            fault_type=FaultType.CAPACITY_FADE,
            description="Capacity fade (22% active lithium loss, retention = 0.78)",
            capacity_retention_factor=0.78,
        ),
        FaultScenarioConfig(
            fault_type=FaultType.VOLTAGE_SENSOR_BIAS,
            description="Positive voltage sensor bias (+45 mV ADC calibration offset)",
            voltage_bias_v=0.045,
        ),
        FaultScenarioConfig(
            fault_type=FaultType.VOLTAGE_SENSOR_BIAS,
            description="Negative voltage sensor bias (-35 mV ADC reference drop)",
            voltage_bias_v=-0.035,
        ),
    ]

    sim_duration = 600.0  # 10 minutes operational run
    dt = 2.0
    total_steps = int(sim_duration / dt)

    results_table = []
    confusion_matrix: Dict[str, Dict[str, int]] = {
        ft.value: {ft2.value: 0 for ft2 in FaultType if ft2 != FaultType.CURRENT_SENSOR_BIAS}
        for ft in FaultType if ft != FaultType.CURRENT_SENSOR_BIAS
    }

    print("\n[*] Step 2: Running operational evaluations across all controlled scenarios...\n")

    for i, scen in enumerate(scenarios, 1):
        # Create fresh physical cell
        p = CellParameters.default_nmc()
        physical_cell = BatteryCell(params=p, initial_soc=0.90, initial_temp_c=25.0)

        # Wrap in FaultyCell
        faulty_cell = FaultyCell(base_cell=physical_cell, config=scen, seed=100 + i)

        # Operational simulation profile
        load_prof = DriveCycleWithRest(base_duration_s=sim_duration)
        temp_prof = ConstantTempProfile(25.0)

        # Attach DeviationTracker to monitor against healthy baseline
        ref_cell_for_tracker = BatteryCell(params=CellParameters.default_nmc())
        tracker = DeviationTracker(baseline=baseline, cell=ref_cell_for_tracker)

        # Run simulation loop
        sim_steps_history = []
        for step_idx in range(total_steps):
            t_curr = (step_idx + 1) * dt
            i_load = float(load_prof.get_current(t_curr))
            t_amb = float(temp_prof.get_temperature(t_curr))

            diag = faulty_cell.step(current=i_load, ambient_temp_c=t_amb, dt=dt)
            sim_steps_history.append(diag)

            if diag["v_terminal"] <= faulty_cell.params.v_min:
                break

            tracker.record(
                time_s=t_curr,
                current_a=diag["current"],
                soc=diag["soc"],
                v_measured=diag["v_terminal"],
                dcir_measured_mohm=diag["r0_mohm"],
                cell_temp_c=diag["cell_temp_c"],
                ambient_temp_c=t_amb,
                dt=dt,
            )

        # Finalize deviation report
        dev_report = tracker.finalize()

        # Run Fault Attribution Engine
        engine = FaultAttributionEngine(baseline=baseline, cell=ref_cell_for_tracker)
        diagnosis: FaultDiagnosis = engine.diagnose(dev_report, sim_steps_history)

        actual_fault = scen.fault_type.value
        diagnosed_fault = diagnosis.attributed_fault.value
        is_match = (actual_fault == diagnosed_fault)

        # Update confusion matrix
        if actual_fault in confusion_matrix and diagnosed_fault in confusion_matrix[actual_fault]:
            confusion_matrix[actual_fault][diagnosed_fault] += 1

        results_table.append({
            "scenario": f"#{i}: {scen.fault_type.value}",
            "description": scen.description,
            "actual_fault": actual_fault,
            "diagnosed_fault": diagnosed_fault,
            "match": is_match,
            "confidence": diagnosis.confidence,
            "severity_estimate": diagnosis.severity_estimate,
            "features": diagnosis.features,
            "diagnosis": diagnosis,
        })

        status_sym = "[MATCH]" if is_match else "[MISMATCH]"
        print(f"  Scenario #{i}: {scen.description}")
        print(f"    Actual: {actual_fault:<20} -> Diagnosed: {diagnosed_fault:<20} {status_sym}")
        print(f"    Confidence: {diagnosis.confidence * 100:.1f}% | Severity: {diagnosis.severity_estimate}")
        print(f"    Discriminators: dV/dI={diagnosis.features.v_current_slope_mohm:+.2f} mOhm, "
              f"Rest V_res={diagnosis.features.v_rest_residual_mv:+.1f} mV, "
              f"Temp Excess={diagnosis.features.temp_excess_mean_c:+.1f} C, "
              f"Fade={diagnosis.features.capacity_fade_pct:.1f}%\n")

    # ── Step 3: Summary & Performance Metrics ─────────────────────────────────
    total_evals = len(results_table)
    correct_evals = sum(1 for r in results_table if r["match"])
    accuracy = (correct_evals / total_evals) * 100.0

    print("=" * 72)
    print("                    EVALUATION SUMMARY & METRICS")
    print("=" * 72)
    print(f"  Total Scenarios Evaluated: {total_evals}")
    print(f"  Correctly Attributed     : {correct_evals} / {total_evals}")
    print(f"  Classification Accuracy  : {accuracy:.1f} %\n")

    # Confusion matrix display
    categories = [ft.value for ft in FaultType if ft != FaultType.CURRENT_SENSOR_BIAS]
    header_str = f"{'Actual \\ Diagnosed':<22} | " + " | ".join(f"{c[:10]:>10}" for c in categories)
    print(header_str)
    print("-" * len(header_str))
    for act in categories:
        row_str = f"{act:<22} | " + " | ".join(f"{confusion_matrix[act][pred]:>10}" for pred in categories)
        print(row_str)

    print("\n" + "=" * 72)
    print("                 DETAILED DIAGNOSIS DEEP-DIVE")
    print("=" * 72)
    for r in results_table:
        print(f"\n---> Scenario: {r['description']}")
        print(r["diagnosis"].summary())

    # Export report to JSON
    export_data = {
        "evaluation_timestamp": time.time(),
        "total_scenarios": total_evals,
        "correct_attributions": correct_evals,
        "accuracy_pct": accuracy,
        "confusion_matrix": confusion_matrix,
        "scenarios": [
            {
                "description": r["description"],
                "actual_fault": r["actual_fault"],
                "diagnosed_fault": r["diagnosed_fault"],
                "match": r["match"],
                "confidence": r["confidence"],
                "severity_estimate": r["severity_estimate"],
                "hypotheses_scores": r["diagnosis"].hypotheses_scores,
                "explanation": r["diagnosis"].explanation,
            }
            for r in results_table
        ],
    }

    report_path = "phase3_fault_attribution_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)
    print(f"\n[+] Full evaluation saved to: {report_path}\n")


if __name__ == "__main__":
    run_fault_evaluation()

"""
Unit tests for Phase 4: Validation & Benchmark Engine
=====================================================
Verifies:
  1. Fixed-Threshold Monitor false alarm on cold sub-zero cell (-10 deg C).
  2. Fixed-Threshold Monitor silent failure / missed detection on voltage sensor bias (+35 mV).
  3. Adaptive Reference Monitor context-aware detection & alert generation.
  4. BenchmarkRunner execution and aggregate metric calculation.
  5. Phase 4 Dashboard 100% offline air-gapped integrity (zero CDN / external script dependencies).
"""

from __future__ import annotations
import os
import unittest
from pathlib import Path

from battery_sim.cell_model import BatteryCell, CellParameters
from battery_sim.reference_model import BaselineCalibrator
from battery_sim.fault_attribution import (
    FaultType,
    FaultScenarioConfig,
    FaultyCell,
    FaultAttributionEngine,
)
from battery_sim.validation import (
    AlertSeverity,
    AlertEvent,
    FixedThresholdConfig,
    FixedThresholdMonitor,
    AdaptiveMonitorConfig,
    AdaptiveReferenceMonitor,
    BenchmarkRunner,
    BenchmarkSummary,
    BinaryMetrics,
    calculate_binary_metrics,
    wilson_score_interval,
    MultiClassConfusionMatrix,
    ExpandedBenchmarkSuite,
)
from battery_sim.visualizer import generate_phase4_dashboard


class TestValidationBenchmark(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Calibrate a standard reference baseline once for fast unit tests
        cal_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=1.0, initial_temp_c=25.0)
        cls.baseline = BaselineCalibrator(cal_cell, cell_id="TEST-REF").build()

    def test_fixed_threshold_cold_false_alarm(self):
        """
        At -10 deg C sub-zero ambient temperature, a healthy cell's resistance naturally
        rises ~2.5x due to standard Arrhenius kinetics.
        Static threshold monitor (cutoff = 55 mOhm) trips a false alarm on healthy cells.
        The Adaptive Reference Model anticipates Arrhenius rise and avoids false alarms.
        """
        # Healthy nominal cell at -10 deg C
        cold_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.8, initial_temp_c=-10.0)
        fixed_mon = FixedThresholdMonitor()
        ref_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.8, initial_temp_c=-10.0)
        adapt_mon = AdaptiveReferenceMonitor(baseline=self.baseline, cell=ref_cell)

        # Step healthy cell under light discharge at -10 deg C
        diag = cold_cell.step(current=2.0, ambient_temp_c=-10.0, dt=2.0)

        # Fixed monitor check
        fixed_alerts = fixed_mon.check_step(
            time_s=2.0,
            v_measured=diag["v_terminal"],
            current_a=diag["current"],
            cell_temp_c=diag["cell_temp_c"],
            dcir_measured_mohm=diag["r0_mohm"],
        )

        # Adaptive monitor check
        adapt_alerts, dev = adapt_mon.check_step(
            time_s=2.0,
            v_measured=diag["v_terminal"],
            current_a=diag["current"],
            soc=diag["soc"],
            cell_temp_c=diag["cell_temp_c"],
            ambient_temp_c=-10.0,
            dcir_measured_mohm=diag["r0_mohm"],
            dt=2.0,
        )

        # Cold DCIR should be high (> 55 mOhm)
        self.assertGreater(diag["r0_mohm"], 55.0)
        # Fixed monitor trips false alarm on healthy cell
        self.assertTrue(fixed_mon.has_tripped)
        self.assertTrue(any(a.parameter == "IMPEDANCE" for a in fixed_alerts))

        # Adaptive monitor knows expected cold DCIR (Arrhenius factor) so relative residual is low
        self.assertLess(abs(dev.dcir_residual_pct), 20.0)

    def test_fixed_threshold_voltage_bias_missed(self):
        """
        A +35 mV ADC voltage sensor bias leaves voltage at ~3.835V, well within
        static BMS limits (2.75V - 4.25V). Fixed threshold monitor misses it (false negative).
        The Adaptive Reference Model detects the 35 mV residual against expected baseline.
        """
        base_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.8, initial_temp_c=25.0)
        faulty = FaultyCell(
            base_cell=base_cell,
            config=FaultScenarioConfig(fault_type=FaultType.VOLTAGE_SENSOR_BIAS, voltage_bias_v=0.035),
            seed=1,
        )
        ref_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.8, initial_temp_c=25.0)

        fixed_mon = FixedThresholdMonitor()
        adapt_mon = AdaptiveReferenceMonitor(baseline=self.baseline, cell=ref_cell)

        # Simulate 10 steps
        for step in range(10):
            t = (step + 1) * 2.0
            diag = faulty.step(current=1.5, ambient_temp_c=25.0, dt=2.0)
            fixed_mon.check_step(
                time_s=t,
                v_measured=diag["v_terminal"],
                current_a=diag["current"],
                cell_temp_c=diag["cell_temp_c"],
                dcir_measured_mohm=diag["r0_mohm"],
            )
            adapt_mon.check_step(
                time_s=t,
                v_measured=diag["v_terminal"],
                current_a=diag["current"],
                soc=diag["soc"],
                cell_temp_c=diag["cell_temp_c"],
                ambient_temp_c=25.0,
                dcir_measured_mohm=diag["r0_mohm"],
                dt=2.0,
            )

        # Fixed monitor never trips (silent failure)
        self.assertFalse(fixed_mon.has_tripped)
        self.assertEqual(len(fixed_mon.alerts), 0)

        # Adaptive monitor trips on voltage residual drift
        self.assertTrue(adapt_mon.has_tripped)
        self.assertTrue(any(a.parameter == "VOLTAGE" for a in adapt_mon.alerts))

    def test_adaptive_monitor_alert_generation(self):
        """Verifies AdaptiveReferenceMonitor generates properly structured AlertEvents."""
        cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.8, initial_temp_c=25.0)
        ref_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.8, initial_temp_c=25.0)
        config = AdaptiveMonitorConfig(v_residual_warn_mv=30.0, v_residual_crit_mv=70.0)
        mon = AdaptiveReferenceMonitor(baseline=self.baseline, cell=ref_cell, config=config)

        # Force a large voltage residual by passing high v_measured
        alerts, dev = mon.check_step(
            time_s=10.0,
            v_measured=4.10,  # ~150 mV above expected ~3.95V
            current_a=0.0,
            soc=0.80,
            cell_temp_c=25.0,
            ambient_temp_c=25.0,
            dcir_measured_mohm=25.0,
            dt=1.0,
        )

        self.assertTrue(len(alerts) > 0)
        evt = alerts[0]
        self.assertIsInstance(evt, AlertEvent)
        self.assertEqual(evt.source_monitor, "ADAPTIVE_MODEL")
        self.assertEqual(evt.parameter, "VOLTAGE")
        self.assertIn(evt.severity, (AlertSeverity.WARNING, AlertSeverity.CRITICAL))
        self.assertGreater(abs(evt.residual_or_delta), 30.0)

    def test_benchmark_runner_execution(self):
        """Executes BenchmarkRunner and validates quantitative comparison metrics."""
        runner = BenchmarkRunner(baseline=self.baseline)
        summary = runner.run_benchmark(sim_duration_s=360.0, dt=2.0)

        self.assertIsInstance(summary, BenchmarkSummary)
        self.assertEqual(summary.total_scenarios, 7)
        self.assertEqual(summary.fault_scenarios_count, 5)
        self.assertEqual(summary.nominal_scenarios_count, 2)

        # Adaptive method must outperform fixed threshold in accuracy and attribution
        self.assertGreaterEqual(summary.adaptive_accuracy_pct, 95.0)
        self.assertLessEqual(summary.adaptive_false_positive_rate_pct, 5.0)
        self.assertLessEqual(summary.adaptive_false_negative_rate_pct, 5.0)
        self.assertGreaterEqual(summary.adaptive_attribution_capability_pct, 95.0)

        # Fixed threshold must exhibit 0% attribution capability
        self.assertEqual(summary.fixed_attribution_capability_pct, 0.0)
        # Fixed threshold false negative rate should be high due to missed subtle faults
        self.assertGreater(summary.fixed_false_negative_rate_pct, 50.0)

    def test_phase4_dashboard_html_offline_integrity(self):
        """
        Generates Phase 4 dashboard and verifies 100% offline air-gapped guarantee:
        No CDN URLs, no external scripts or remote stylesheets.
        """
        output_file = "test_phase4_offline_check.html"
        try:
            sample_telemetry = [
                {
                    "time_s": float(t),
                    "v_terminal": 3.9 - 0.001 * t,
                    "current": 2.0,
                    "soc": 0.9 - 0.0005 * t,
                    "cell_temp_c": 25.0 + 0.02 * t,
                    "ambient_temp_c": 25.0,
                    "r0_mohm": 26.0,
                    "power_w": 7.8,
                }
                for t in range(0, 100, 2)
            ]

            path = generate_phase4_dashboard(
                telemetry=sample_telemetry,
                output_path=output_file,
                title="Test Offline Dashboard",
            )
            self.assertTrue(os.path.exists(path))

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Ensure non-trivial content
            self.assertGreater(len(content), 5000)

            # Air-gapped / offline verification: Zero CDN references
            self.assertNotIn("cdn.jsdelivr.net", content)
            self.assertNotIn("cdnjs.cloudflare.com", content)
            self.assertNotIn("unpkg.com", content)

            # Ensure no remote scripts: `<script src="http`
            self.assertNotIn('<script src="http', content)
            self.assertNotIn('<link rel="stylesheet" href="http', content)

            # Ensure HTML5 Canvas elements exist
            self.assertIn("<canvas id=\"canvas-v\">", content)
            self.assertIn("<canvas id=\"canvas-dcir\">", content)
            self.assertIn("<canvas id=\"canvas-temp\">", content)
            self.assertIn("<canvas id=\"canvas-soc\">", content)
        finally:
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except OSError:
                    pass

    def test_fixed_monitor_telemetry_nan_and_infinity_rejection(self):
        """
        Fix 2 Regression: FixedThresholdMonitor must reject NaN, +inf, -inf
        independently across Voltage, Current, and Temperature.
        Must generate an explicit CRITICAL SENSOR alert and trip the monitor.
        """
        invalid_values = [float("nan"), float("inf"), float("-inf")]
        input_fields = ["voltage", "current", "temperature"]

        for field_name in input_fields:
            for bad_val in invalid_values:
                mon = FixedThresholdMonitor()
                v = bad_val if field_name == "voltage" else 3.80
                i = bad_val if field_name == "current" else 1.0
                t = bad_val if field_name == "temperature" else 25.0
                r = 25.0

                alerts = mon.check_step(time_s=1.0, v_measured=v, current_a=i, cell_temp_c=t, dcir_measured_mohm=r)
                self.assertTrue(mon.has_tripped, f"Failed to trip on bad {field_name}={bad_val}")
                self.assertGreater(len(alerts), 0, f"No alerts for bad {field_name}={bad_val}")
                self.assertTrue(
                    any(a.parameter == "SENSOR" and a.severity == AlertSeverity.CRITICAL for a in alerts),
                    f"Missing CRITICAL SENSOR alert for {field_name}={bad_val}"
                )

    def test_adaptive_monitor_telemetry_nan_and_infinity_rejection(self):
        """
        Fix 2 Regression: AdaptiveReferenceMonitor must reject NaN, +inf, -inf
        independently across Voltage, Current, and Temperature without corrupting
        internal predictor or tracker state.
        """
        ref_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.8, initial_temp_c=25.0)
        invalid_values = [float("nan"), float("inf"), float("-inf")]
        input_fields = ["voltage", "current", "temperature"]

        for field_name in input_fields:
            for bad_val in invalid_values:
                mon = AdaptiveReferenceMonitor(baseline=self.baseline, cell=ref_cell)
                v = bad_val if field_name == "voltage" else 3.80
                i = bad_val if field_name == "current" else 1.0
                t = bad_val if field_name == "temperature" else 25.0
                soc = 0.80
                r = 25.0

                alerts, dev = mon.check_step(
                    time_s=1.0,
                    v_measured=v,
                    current_a=i,
                    soc=soc,
                    cell_temp_c=t,
                    ambient_temp_c=25.0,
                    dcir_measured_mohm=r,
                    dt=1.0,
                )
                self.assertTrue(mon.has_tripped, f"Failed to trip on bad {field_name}={bad_val}")
                self.assertIsNone(dev, f"StepDeviation must be None for bad {field_name}={bad_val}")
                self.assertEqual(len(mon.tracker._step_deviations), 0, "Tracker state was corrupted by invalid input")
                self.assertTrue(
                    any(a.parameter == "SENSOR" and a.severity == AlertSeverity.CRITICAL for a in alerts),
                    f"Missing CRITICAL SENSOR alert for {field_name}={bad_val}"
                )

    def test_valid_telemetry_and_safety_limits_preserved(self):
        """
        Fix 2 Regression: Confirm valid telemetry continues to work normally and
        real safety limit violations (Over-Voltage, Under-Voltage, Over-Temp) are preserved.
        """
        # 1. Normal benign point: must NOT trip
        normal_mon = FixedThresholdMonitor()
        alerts = normal_mon.check_step(time_s=1.0, v_measured=3.80, current_a=2.0, cell_temp_c=25.0, dcir_measured_mohm=25.0)
        self.assertFalse(normal_mon.has_tripped)
        self.assertEqual(len(alerts), 0)

        # 2. Over-Voltage violation (v=4.30V >= 4.25V): must trip CRITICAL VOLTAGE
        ov_mon = FixedThresholdMonitor()
        ov_alerts = ov_mon.check_step(time_s=1.0, v_measured=4.30, current_a=0.0, cell_temp_c=25.0, dcir_measured_mohm=25.0)
        self.assertTrue(ov_mon.has_tripped)
        self.assertTrue(any(a.parameter == "VOLTAGE" and a.severity == AlertSeverity.CRITICAL for a in ov_alerts))

        # 3. Under-Voltage violation (v=2.50V <= 2.75V): must trip CRITICAL VOLTAGE
        uv_mon = FixedThresholdMonitor()
        uv_alerts = uv_mon.check_step(time_s=1.0, v_measured=2.50, current_a=2.0, cell_temp_c=25.0, dcir_measured_mohm=25.0)
        self.assertTrue(uv_mon.has_tripped)
        self.assertTrue(any(a.parameter == "VOLTAGE" and a.severity == AlertSeverity.CRITICAL for a in uv_alerts))

        # 4. Critical Over-Temperature (T=62C >= 60C): must trip FAULT TEMPERATURE
        ot_mon = FixedThresholdMonitor()
        ot_alerts = ot_mon.check_step(time_s=1.0, v_measured=3.70, current_a=2.0, cell_temp_c=62.0, dcir_measured_mohm=25.0)
        self.assertTrue(ot_mon.has_tripped)
        self.assertTrue(any(a.parameter == "TEMPERATURE" for a in ot_alerts))

    def test_healthy_aggressive_driving_no_false_voltage_bias(self):
        """
        Fix 1 Regression: Aggressive/Sport driving on a healthy cell must NOT trigger
        false VOLTAGE_SENSOR_BIAS attribution. Polarization compensation and dwell
        filtering ensure classification remains NOMINAL across multiple seeds.
        """
        from verification_suite import AggressiveSportProfile
        prof = AggressiveSportProfile(duration_s=300.0)
        dt = 2.0

        for seed in [1, 42, 100]:
            ref_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.90, initial_temp_c=25.0)
            healthy_cell = FaultyCell(
                base_cell=BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.90, initial_temp_c=25.0),
                config=FaultScenarioConfig(fault_type=FaultType.NOMINAL),
                seed=seed,
            )
            adapt_mon = AdaptiveReferenceMonitor(baseline=self.baseline, cell=ref_cell)
            sim_steps = []
            for step in range(int(prof.duration() / dt)):
                t = (step + 1) * dt
                curr = prof.get_current(t)
                diag = healthy_cell.step(current=curr, ambient_temp_c=25.0, dt=dt)
                sim_steps.append(diag)
                adapt_mon.check_step(t, diag["v_terminal"], diag["current"], diag["soc"], diag["cell_temp_c"], 25.0, diag["r0_mohm"], dt)

            dev_report = adapt_mon.finalize()
            engine = FaultAttributionEngine(baseline=self.baseline, cell=ref_cell)
            diagnosis = engine.diagnose(dev_report, sim_steps)

            self.assertEqual(diagnosis.attributed_fault, FaultType.NOMINAL, f"False alarm on seed {seed}: got {diagnosis.attributed_fault}")
            self.assertGreater(diagnosis.confidence, 0.90)

    def test_binary_metrics_manual_confusion_matrix(self):
        """
        Manually verifies exact formula implementations:
          Accuracy = (TP + TN) / (TP + TN + FP + FN)
          Precision = TP / (TP + FP)
          Sensitivity / Recall = TP / (TP + FN)
          Specificity = TN / (TN + FP)
          FPR = FP / (FP + TN)
          FNR = FN / (FN + TP)
        Using a known manual confusion matrix: TP=50, TN=35, FP=5, FN=10 (Total=100).
        """
        tp = 50
        tn = 35
        fp = 5
        fn = 10
        bm = calculate_binary_metrics(tp=tp, tn=tn, fp=fp, fn=fn)

        # Expected manual calculations
        expected_accuracy = (50 + 35) / 100.0                   # 0.85
        expected_precision = 50.0 / (50.0 + 5.0)                # 50/55 = 0.9090909...
        expected_sensitivity = 50.0 / (50.0 + 10.0)             # 50/60 = 0.8333333...
        expected_specificity = 35.0 / (35.0 + 5.0)              # 35/40 = 0.875
        expected_fpr = 5.0 / (5.0 + 35.0)                       # 5/40  = 0.125
        expected_fnr = 10.0 / (10.0 + 50.0)                     # 10/60 = 0.1666666...

        self.assertAlmostEqual(bm.accuracy, expected_accuracy, places=7)
        self.assertAlmostEqual(bm.precision, expected_precision, places=7)
        self.assertAlmostEqual(bm.sensitivity_recall, expected_sensitivity, places=7)
        self.assertAlmostEqual(bm.specificity, expected_specificity, places=7)
        self.assertAlmostEqual(bm.false_positive_rate, expected_fpr, places=7)
        self.assertAlmostEqual(bm.false_negative_rate, expected_fnr, places=7)

        # Critical mathematical complements
        self.assertAlmostEqual(bm.specificity + bm.false_positive_rate, 1.0, places=7)
        self.assertAlmostEqual(bm.sensitivity_recall + bm.false_negative_rate, 1.0, places=7)

        # Specificity != Sensitivity proof
        self.assertNotEqual(bm.specificity, bm.sensitivity_recall)

    def test_binary_metrics_edge_cases_and_zero_division(self):
        """
        Tests mathematical edge cases and validates documented zero-division handling:
          - All TN (TP=0, FP=0, FN=0, TN=20)
          - All TP (TN=0, FP=0, FN=0, TP=20)
          - All FP (TP=0, TN=0, FN=0, FP=10)
          - All FN (TP=0, TN=0, FP=0, FN=10)
          - Empty matrix (all 0)
        """
        # Case A: All True Negatives
        bm_tn = calculate_binary_metrics(tp=0, tn=20, fp=0, fn=0)
        self.assertEqual(bm_tn.accuracy, 1.0)
        self.assertEqual(bm_tn.specificity, 1.0)
        self.assertEqual(bm_tn.false_positive_rate, 0.0)
        self.assertEqual(bm_tn.precision, 0.0) # documented: no positive predictions made
        self.assertEqual(bm_tn.sensitivity_recall, 1.0) # documented: 0 missed faults
        self.assertTrue(len(bm_tn.zero_division_notes) > 0)

        # Case B: All True Positives
        bm_tp = calculate_binary_metrics(tp=20, tn=0, fp=0, fn=0)
        self.assertEqual(bm_tp.accuracy, 1.0)
        self.assertEqual(bm_tp.sensitivity_recall, 1.0)
        self.assertEqual(bm_tp.false_negative_rate, 0.0)
        self.assertEqual(bm_tp.precision, 1.0)
        self.assertEqual(bm_tp.specificity, 1.0) # documented: no negative ground truth
        self.assertEqual(bm_tp.false_positive_rate, 0.0)

        # Case C: All False Positives
        bm_fp = calculate_binary_metrics(tp=0, tn=0, fp=10, fn=0)
        self.assertEqual(bm_fp.accuracy, 0.0)
        self.assertEqual(bm_fp.precision, 0.0)
        self.assertEqual(bm_fp.specificity, 0.0)
        self.assertEqual(bm_fp.false_positive_rate, 1.0)

        # Case D: All False Negatives
        bm_fn = calculate_binary_metrics(tp=0, tn=0, fp=0, fn=10)
        self.assertEqual(bm_fn.accuracy, 0.0)
        self.assertEqual(bm_fn.sensitivity_recall, 0.0)
        self.assertEqual(bm_fn.false_negative_rate, 1.0)

        # Case E: Empty Matrix (0/0)
        bm_empty = calculate_binary_metrics(tp=0, tn=0, fp=0, fn=0)
        self.assertEqual(bm_empty.accuracy, 0.0)
        self.assertEqual(bm_empty.precision, 0.0)
        self.assertEqual(bm_empty.total, 0)
        self.assertTrue(any("empty evaluation sample set" in n for n in bm_empty.zero_division_notes))

    def test_standard_benchmark_recalculated_metrics(self):
        """
        Recalculates every metric on the standard 7-scenario benchmark from raw outputs:
          Adaptive: TP=5, TN=2, FP=0, FN=0 -> Acc=100.0%, Precision=100.0%, Recall=100.0%, Spec=100.0%, FPR=0.0%
          Fixed:    TP=1, TN=1, FP=1, FN=4 -> Acc=28.6%, Precision=50.0%, Recall=20.0%, Spec=50.0%, FPR=50.0%
        Verifies that Specificity is properly calculated as TN/(TN+FP) and distinct from Attribution Recall.
        """
        runner = BenchmarkRunner(baseline=self.baseline)
        summary = runner.run_benchmark(sim_duration_s=360.0, dt=2.0)

        # Raw scenario counts
        total = summary.total_scenarios
        faults = summary.fault_scenarios_count
        noms = summary.nominal_scenarios_count
        self.assertEqual(total, 7)
        self.assertEqual(faults, 5)
        self.assertEqual(noms, 2)

        # Adaptive metrics verification
        self.assertEqual(summary.adaptive_accuracy_pct, 100.0)
        self.assertEqual(summary.adaptive_precision_pct, 100.0)
        self.assertEqual(summary.adaptive_sensitivity_recall_pct, 100.0)
        self.assertEqual(summary.adaptive_specificity_pct, 100.0)
        self.assertEqual(summary.adaptive_false_positive_rate_pct, 0.0)
        self.assertEqual(summary.adaptive_false_negative_rate_pct, 0.0)
        self.assertEqual(summary.adaptive_attribution_recall_pct, 100.0)

        # Fixed baseline metrics verification
        self.assertEqual(summary.fixed_accuracy_pct, 28.6)
        self.assertEqual(summary.fixed_precision_pct, 50.0)
        self.assertEqual(summary.fixed_sensitivity_recall_pct, 20.0)
        self.assertEqual(summary.fixed_specificity_pct, 50.0)
        self.assertEqual(summary.fixed_false_positive_rate_pct, 50.0)
        self.assertEqual(summary.fixed_false_negative_rate_pct, 80.0)
        self.assertEqual(summary.fixed_attribution_capability_pct, 0.0)

        # Proof of resolved specificity bug:
        # Fixed Specificity = TN/(TN+FP) = 1/(1+1) = 50.0%, NOT 0.0%!
        self.assertEqual(summary.fixed_specificity_pct, 50.0)
        self.assertAlmostEqual(summary.fixed_specificity_pct + summary.fixed_false_positive_rate_pct, 100.0, places=1)
        self.assertAlmostEqual(summary.fixed_sensitivity_recall_pct + summary.fixed_false_negative_rate_pct, 100.0, places=1)

    def test_wilson_score_confidence_intervals(self):
        """
        Verifies mathematical correctness of Wilson 95% confidence intervals:
          - Bounded in [0.0, 1.0].
          - Handles k=0 and k=n without collapsing to zero width.
          - Monotonicity: larger sample sizes yield narrower intervals.
        """
        # Small sample edge: k=0, n=10
        low_0, high_0 = wilson_score_interval(0, 10)
        self.assertEqual(low_0, 0.0)
        self.assertGreater(high_0, 0.0)
        self.assertLess(high_0, 0.35)

        # Small sample edge: k=10, n=10
        low_1, high_1 = wilson_score_interval(10, 10)
        self.assertGreater(low_1, 0.65)
        self.assertAlmostEqual(high_1, 1.0, places=7)

        # Standard sample: k=50, n=100
        low_50, high_50 = wilson_score_interval(50, 100)
        self.assertAlmostEqual(low_50, 0.4038, places=2)
        self.assertAlmostEqual(high_50, 0.5962, places=2)

        # Width comparison: N=100 is narrower than N=10
        width_100 = high_50 - low_50
        low_5, high_5 = wilson_score_interval(5, 10)
        width_10 = high_5 - low_5
        self.assertLess(width_100, width_10)

    def test_multiclass_confusion_matrix_accumulation(self):
        """Tests MultiClassConfusionMatrix accumulation and One-vs-Rest calculation."""
        cm = MultiClassConfusionMatrix()
        cm.record("NOMINAL", "NOMINAL")
        cm.record("NOMINAL", "NOMINAL")
        cm.record("VOLTAGE_SENSOR_BIAS", "VOLTAGE_SENSOR_BIAS")
        cm.record("INCREASED_RESISTANCE", "INCREASED_RESISTANCE")
        cm.record("TEMPERATURE_RISE", "NOMINAL") # 1 misclassification

        self.assertEqual(cm.total_samples, 5)
        self.assertEqual(cm.overall_accuracy_pct, 80.0) # 4/5
        self.assertAlmostEqual(cm.fault_attribution_recall_pct, 66.67, places=1) # 2/3 faults

        ovr_nom = cm.get_one_vs_rest("NOMINAL")
        self.assertEqual(ovr_nom.tp, 2)
        self.assertEqual(ovr_nom.fp, 1) # TEMPERATURE_RISE predicted as NOMINAL
        self.assertEqual(ovr_nom.fn, 0)
        self.assertEqual(ovr_nom.tn, 2)

        table_str = cm.render_table()
        self.assertIn("NOMINAL", table_str)
        self.assertIn("V_BIAS", table_str)

    def test_expanded_benchmark_suite_reproducibility(self):
        """
        Executes ExpandedBenchmarkSuite on tuning scenarios and asserts deterministic reproducibility:
        Two runs with identical seeds must produce identical results.
        """
        suite = ExpandedBenchmarkSuite(baseline=self.baseline)
        tuning_scenarios = suite.generate_tuning_scenarios(seed_start=1000, count=25)
        self.assertEqual(len(tuning_scenarios), 25)

        run1 = suite.run_suite(tuning_scenarios, dataset_name="tuning_run1", sim_duration_s=120.0, dt=2.0)
        run2 = suite.run_suite(tuning_scenarios, dataset_name="tuning_run2", sim_duration_s=120.0, dt=2.0)

        self.assertEqual(run1.total_scenarios, run2.total_scenarios)
        self.assertEqual(run1.binary_metrics_adaptive["accuracy_pct"], run2.binary_metrics_adaptive["accuracy_pct"])
        self.assertEqual(run1.multi_class_confusion_matrix["matrix"], run2.multi_class_confusion_matrix["matrix"])



if __name__ == "__main__":
    unittest.main()

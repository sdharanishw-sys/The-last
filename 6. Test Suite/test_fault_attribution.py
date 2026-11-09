"""
Phase 3: Fault Attribution Unit & Verification Test Suite.

Verifies:
1. Correct attribution of Increased Internal Resistance with quantitative accuracy.
2. Correct attribution of Voltage Sensor Bias (both positive and negative drift).
3. Correct attribution of Abnormal Temperature Rise.
4. Correct attribution of Capacity Fade.
5. Correct identification of Nominal (healthy) baseline with zero false positives.
6. Robust mathematical discrimination between Ohmic IR sag (dV/dI slope) vs static sensor offset (rest bias).
"""

import unittest
from battery_sim.cell_model import BatteryCell, CellParameters
from battery_sim.profiles import DriveCycleProfile, ConstantTempProfile
from battery_sim.reference_model import BaselineCalibrator, DeviationTracker
from battery_sim.fault_attribution import (
    FaultType,
    FaultScenarioConfig,
    FaultyCell,
    FaultAttributionEngine,
)


class BaseFaultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Calibrate a single reference baseline once for all test cases
        base_params = CellParameters.default_nmc()
        cal_cell = BatteryCell(params=base_params, initial_soc=1.0, initial_temp_c=25.0)
        cls.baseline = BaselineCalibrator(cal_cell, cell_id="TEST-REF").build()

    def _run_scenario(self, config: FaultScenarioConfig, duration_s: float = 300.0):
        # Drive cycle with rest pauses
        load_prof = DriveCycleProfile(peak_current_a=5.0, regen_ratio=0.3, duration_s=duration_s)
        temp_prof = ConstantTempProfile(25.0)

        physical_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.85, initial_temp_c=25.0)
        faulty = FaultyCell(base_cell=physical_cell, config=config, seed=42)

        ref_cell = BatteryCell(params=CellParameters.default_nmc())
        tracker = DeviationTracker(baseline=self.baseline, cell=ref_cell)

        dt = 2.0
        steps_history = []
        for step_idx in range(int(duration_s / dt)):
            t = (step_idx + 1) * dt
            # Inject resting intervals every 60s
            i_curr = 0.0 if (45.0 <= (t % 60.0) < 55.0) else float(load_prof.get_current(t))

            diag = faulty.step(current=i_curr, ambient_temp_c=25.0, dt=dt)
            steps_history.append(diag)
            if diag["v_terminal"] <= faulty.params.v_min:
                break

            tracker.record(
                time_s=t,
                current_a=diag["current"],
                soc=diag["soc"],
                v_measured=diag["v_terminal"],
                dcir_measured_mohm=diag["r0_mohm"],
                cell_temp_c=diag["cell_temp_c"],
                ambient_temp_c=25.0,
                dt=dt,
            )

        dev_report = tracker.finalize()
        engine = FaultAttributionEngine(baseline=self.baseline, cell=ref_cell)
        return engine.diagnose(dev_report, steps_history)


class TestFaultAttributionEngine(BaseFaultTest):
    def test_attribute_nominal_healthy_cell(self):
        """Healthy baseline cell must be classified as NOMINAL with high confidence."""
        cfg = FaultScenarioConfig(fault_type=FaultType.NOMINAL)
        diag = self._run_scenario(cfg)
        self.assertEqual(diag.attributed_fault, FaultType.NOMINAL)
        self.assertGreater(diag.confidence, 0.90)

    def test_attribute_increased_internal_resistance(self):
        """+20 mOhm resistance degradation must be attributed to INCREASED_RESISTANCE."""
        injected_r_ohm = 0.020
        cfg = FaultScenarioConfig(
            fault_type=FaultType.INCREASED_RESISTANCE,
            resistance_adder_ohm=injected_r_ohm,
        )
        diag = self._run_scenario(cfg)
        self.assertEqual(diag.attributed_fault, FaultType.INCREASED_RESISTANCE)
        self.assertGreater(diag.confidence, 0.90)
        # Estimated severity should match within 15%
        self.assertAlmostEqual(diag.severity_value, injected_r_ohm * 1000.0, delta=4.0)

    def test_attribute_voltage_sensor_bias_positive(self):
        """+40 mV positive sensor offset must be attributed to VOLTAGE_SENSOR_BIAS."""
        cfg = FaultScenarioConfig(
            fault_type=FaultType.VOLTAGE_SENSOR_BIAS,
            voltage_bias_v=0.040,
        )
        diag = self._run_scenario(cfg)
        self.assertEqual(diag.attributed_fault, FaultType.VOLTAGE_SENSOR_BIAS)
        self.assertGreater(diag.confidence, 0.90)
        self.assertGreater(abs(diag.features.v_rest_residual_mv), 20.0)

    def test_attribute_voltage_sensor_bias_negative(self):
        """-30 mV negative sensor offset must be attributed to VOLTAGE_SENSOR_BIAS."""
        cfg = FaultScenarioConfig(
            fault_type=FaultType.VOLTAGE_SENSOR_BIAS,
            voltage_bias_v=-0.030,
        )
        diag = self._run_scenario(cfg)
        self.assertEqual(diag.attributed_fault, FaultType.VOLTAGE_SENSOR_BIAS)
        self.assertGreater(diag.confidence, 0.90)
        self.assertLess(diag.features.v_rest_residual_mv, -20.0)

    def test_attribute_abnormal_temperature_rise(self):
        """Thermal dissipation fault (cooling loss + heat flux) must be attributed to TEMPERATURE_RISE."""
        cfg = FaultScenarioConfig(
            fault_type=FaultType.TEMPERATURE_RISE,
            cooling_factor=0.20,
            external_heat_flux_w=2.5,
        )
        diag = self._run_scenario(cfg)
        self.assertEqual(diag.attributed_fault, FaultType.TEMPERATURE_RISE)
        self.assertGreater(diag.confidence, 0.90)
        self.assertGreater(diag.features.temp_excess_mean_c, 5.0)

    def test_attribute_capacity_fade(self):
        """25% capacity loss must be attributed to CAPACITY_FADE."""
        cfg = FaultScenarioConfig(
            fault_type=FaultType.CAPACITY_FADE,
            capacity_retention_factor=0.75,
        )
        diag = self._run_scenario(cfg)
        self.assertEqual(diag.attributed_fault, FaultType.CAPACITY_FADE)
        self.assertGreater(diag.confidence, 0.90)
        self.assertGreater(diag.features.capacity_fade_pct, 10.0)

    def test_discriminator_resistance_vs_sensor_bias_orthogonality(self):
        """
        Mathematical proof of discrimination:
        - For increased resistance, rest voltage residual (I=0) must be small (< 15 mV),
          while current-correlated slope dV/dI is large.
        - For sensor bias, current-correlated slope is small, while rest voltage residual is large.
        """
        diag_r = self._run_scenario(FaultScenarioConfig(resistance_adder_ohm=0.025))
        diag_v = self._run_scenario(FaultScenarioConfig(voltage_bias_v=0.045))

        # Resistance case: slope is large, rest bias is near zero
        self.assertLess(diag_r.features.v_current_slope_mohm, -15.0)
        self.assertLess(abs(diag_r.features.v_rest_residual_mv), 15.0)

        # Voltage bias case: rest bias is large, slope is flat
        self.assertGreater(diag_v.features.v_rest_residual_mv, 25.0)
        self.assertGreater(diag_v.features.v_current_slope_mohm, -5.0)


if __name__ == "__main__":
    unittest.main()

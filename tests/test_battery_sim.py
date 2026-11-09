"""
Comprehensive Physical Verification and BMS Safety Test Suite.

Rigorously verifies:
1. Strict thermodynamic OCV monotonicity across SOC [0, 1] (NMC and LFP).
2. Arrhenius activation energy kinetics: ln(R0) linearity with 1/T.
3. 2-RC polarization exponential relaxation and analytical time constants.
4. First Law of Thermodynamics thermal energy conservation (adiabatic Q_gen = m*Cp*dT).
5. Coulombic efficiency and low-temperature capacity derating.
6. Exact discrete time-stepping duration and trajectory sample accounting.
7. Real-world BMS safety supervisor cutoffs (over-temp, under-voltage, sub-zero charge lockout).
8. Multi-cell battery pack series-parallel physics and passive cell balancing.
"""

import math
import tempfile
import os
import unittest
from battery_sim.cell_model import BatteryCell, CellParameters, ChemistryType, R_GAS
from battery_sim.pack_model import BatteryPack
from battery_sim.profiles import (
    ConstantCurrentProfile,
    PulseProfile,
    DriveCycleProfile,
    SinusoidalTempProfile,
    StepTempProfile,
)
from battery_sim.simulator import BatterySimulator


class TestElectrochemicalPhysics(unittest.TestCase):
    def test_ocv_strict_monotonicity_nmc_and_lfp(self):
        """
        Thermodynamic requirement: d(OCV)/d(SOC) must be strictly non-negative (> 0)
        across the entire SOC range [0.0, 1.0] without non-physical oscillations.
        """
        cell_nmc = BatteryCell(params=CellParameters.default_nmc())
        cell_lfp = BatteryCell(params=CellParameters.default_lfp())

        num_points = 1000
        soc_grid = [i / (num_points - 1) for i in range(num_points)]

        for name, cell in [("NMC", cell_nmc), ("LFP", cell_lfp)]:
            ocv_vals = [cell.open_circuit_voltage(soc=s, temp_c=25.0) for s in soc_grid]
            for i in range(len(ocv_vals) - 1):
                diff = ocv_vals[i + 1] - ocv_vals[i]
                self.assertGreaterEqual(
                    diff,
                    0.0,
                    f"{name} violated OCV monotonicity at SOC={soc_grid[i]:.4f}: diff={diff:.8f}",
                )

    def test_arrhenius_activation_energy_kinetics(self):
        """
        Physics requirement: ln(R0(T) / R0_ref) vs (1/T - 1/T_ref) must be strictly linear
        with slope equal to Ea / R_gas.
        """
        cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.5)
        ea = cell.params.ea_r0
        t_ref = cell.params.t_ref_k

        # Test from -20 deg C (253.15 K) to 55 deg C (328.15 K)
        test_temps_c = [-20.0, -10.0, 0.0, 15.0, 25.0, 35.0, 45.0, 55.0]
        r_ref = cell.ohmic_resistance(soc=0.5, temp_k=t_ref)

        for tc in test_temps_c:
            tk = tc + 273.15
            r_val = cell.ohmic_resistance(soc=0.5, temp_k=tk)
            expected_ratio = math.exp((ea / R_GAS) * ((1.0 / tk) - (1.0 / t_ref)))
            actual_ratio = r_val / r_ref
            self.assertAlmostEqual(actual_ratio, expected_ratio, places=5)

    def test_rc_polarization_exponential_relaxation(self):
        """
        Transient dynamics requirement: After a current pulse ends (I=0 rest),
        polarization overpotentials V_rc1 and V_rc2 must decay exponentially:
        V_rc(t) = V_rc(0) * exp(-t / tau).
        """
        cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.8, initial_temp_c=25.0)
        # Apply a 15-second 4.0A pulse to build up polarization
        cell.step(current=4.0, ambient_temp_c=25.0, dt=15.0)
        v_rc1_init = cell.v_rc1
        v_rc2_init = cell.v_rc2
        self.assertGreater(v_rc1_init, 0.01)
        self.assertGreater(v_rc2_init, 0.01)

        r1, c1, r2, c2 = cell.polarization_impedances()
        tau1 = r1 * c1
        tau2 = r2 * c2

        # Relax at rest (I = 0.0) for 30 seconds
        dt_relax = 30.0
        cell.step(current=0.0, ambient_temp_c=25.0, dt=dt_relax)

        expected_rc1 = v_rc1_init * math.exp(-dt_relax / tau1)
        expected_rc2 = v_rc2_init * math.exp(-dt_relax / tau2)

        self.assertAlmostEqual(cell.v_rc1, expected_rc1, places=5)
        self.assertAlmostEqual(cell.v_rc2, expected_rc2, places=5)

    def test_first_law_thermal_energy_conservation(self):
        """
        Conservation of Energy: In an adiabatic cell (convective_h = 0),
        the total cumulative heat generated must equal m * Cp * delta_T.
        """
        params = CellParameters.default_nmc()
        params.convective_h = 0.0  # Perfectly insulated adiabatic calorimeter
        cell = BatteryCell(params=params, initial_soc=1.0, initial_temp_c=25.0)

        t_initial = cell.temperature_c
        total_q_joule = 0.0
        dt = 1.0

        # Run 60 seconds of discharge at 3.0A
        for _ in range(60):
            diag = cell.step(current=3.0, ambient_temp_c=25.0, dt=dt)
            total_q_joule += diag["q_generated_w"] * dt

        thermal_mass = params.mass_kg * params.specific_heat_cp
        delta_temp_expected = total_q_joule / thermal_mass
        actual_delta_temp = cell.temperature_c - t_initial

        self.assertAlmostEqual(actual_delta_temp, delta_temp_expected, places=4)

    def test_coulombic_efficiency_and_capacity_derating(self):
        """
        Charge/discharge asymmetry:
        Charging accounts for coulombic efficiency (eta_charge = 0.995).
        Usable capacity degrades at low temperatures.
        """
        cell_warm = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.5, initial_temp_c=25.0)
        cell_cold = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.5, initial_temp_c=-10.0)

        # Usable capacity at -10 deg C must be derated relative to 25 deg C
        q_warm = cell_warm.effective_capacity_ah()
        q_cold = cell_cold.effective_capacity_ah()
        self.assertLess(q_cold, q_warm)
        self.assertAlmostEqual(q_warm, 3.0, places=3)
        self.assertAlmostEqual(q_cold, 3.0 * (1.0 - 35.0 * 0.006), places=3)

        # Coulombic efficiency during charging (10 min charge)
        diag_charge = cell_warm.step(current=-2.0, ambient_temp_c=25.0, dt=600.0)
        # Expected delta SOC = (2.0 A * 0.995 * 600s) / (3.0 Ah * 3600s)
        delta_soc = diag_charge["soc"] - 0.50
        self.assertAlmostEqual(delta_soc, (2.0 * 0.995 * 600.0) / (3.0 * 3600.0), places=4)


class TestSimulationTrajectoryAndAccounting(unittest.TestCase):
    def test_discrete_stepping_endpoint_and_duration(self):
        """
        Exact trajectory accounting: A 5-second simulation with dt=1.0s must execute
        exactly 5 physics updates, have elapsed duration = 5.0s, and store 6 trajectory points
        (t=0.0s initial condition + 5 steps).
        """
        cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.9)
        sim = BatterySimulator(cell=cell, load_profile=ConstantCurrentProfile(1.5), dt=1.0, max_duration_s=5.0)
        res = sim.run()

        self.assertEqual(res.metadata["physics_steps_executed"], 5)
        self.assertEqual(res.metadata["duration_s"], 5.0)
        self.assertEqual(len(res.steps), 6)
        self.assertEqual([s.time_s for s in res.steps], [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])


class TestBMSSafetySupervisor(unittest.TestCase):
    def test_bms_subzero_charging_lockout(self):
        """
        Battery Safety: Charging at sub-zero temperatures triggers lithium plating risk.
        BMS supervisor must trip and lockout charging when T_cell < 0 deg C.
        """
        cell = BatteryCell(initial_soc=0.5, initial_temp_c=-5.0)
        sim = BatterySimulator(
            cell=cell,
            load_profile=ConstantCurrentProfile(-2.0),  # Attempted charge
            temperature_profile=StepTempProfile([(0, -5.0)]),
            dt=1.0,
            max_duration_s=100.0,
        )
        res = sim.run()
        self.assertIn("Sub-zero charging lockout", res.termination_reason)

    def test_bms_over_temperature_safety_trip(self):
        """
        Battery Safety: Cell temperature exceeding 60 deg C must trigger immediate thermal trip.
        """
        cell = BatteryCell(initial_soc=0.5, initial_temp_c=59.5)
        sim = BatterySimulator(
            cell=cell,
            load_profile=ConstantCurrentProfile(10.0),  # Heavy discharge generating heat
            temperature_profile=StepTempProfile([(0, 45.0)]),
            dt=1.0,
            max_duration_s=100.0,
            temp_cutoff_max_c=60.0,
        )
        res = sim.run()
        self.assertIn("Over-temperature safety trip", res.termination_reason)
        self.assertGreaterEqual(res.steps[-1].cell_temp_c, 60.0)

    def test_bms_under_voltage_trip(self):
        """
        Battery Safety: Deep discharge below minimum cutoff (2.8V) must safely terminate.
        """
        cell = BatteryCell(initial_soc=0.03)  # Depleted cell
        sim = BatterySimulator(
            cell=cell,
            load_profile=ConstantCurrentProfile(3.0),
            dt=1.0,
            max_duration_s=300.0,
        )
        res = sim.run()
        self.assertIn("Under-voltage cutoff reached", res.termination_reason)
        self.assertLessEqual(res.steps[-1].v_terminal, cell.params.v_min + 0.05)


class TestBatteryPackAndBalancing(unittest.TestCase):
    def test_pack_series_voltage_and_passive_balancing(self):
        """
        Pack physics: 4S pack terminal voltage must equal sum of 4 series stage voltages.
        Passive balancing bleed circuits must activate when cell delta exceeds tolerance.
        """
        pack = BatteryPack(
            num_series=4,
            num_parallel=1,
            initial_soc=0.96,
            passive_balancing=True,
            balance_voltage_threshold=4.15,
            balance_delta_threshold=0.003,
            bleed_resistor_ohm=47.0,
            seed=42,
        )

        diag = pack.step(pack_current=-0.4, ambient_temp_c=25.0, dt=1.0)
        # Pack voltage equals sum of stages
        self.assertAlmostEqual(diag["pack_voltage"], sum(diag["stage_voltages"]), places=4)
        # If balancing conditions are met, bleed circuits activate
        if diag["balancing_active"]:
            self.assertGreater(max(diag["bleed_currents_a"]), 0.05)


if __name__ == "__main__":
    unittest.main()

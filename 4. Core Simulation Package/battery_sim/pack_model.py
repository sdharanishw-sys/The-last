"""
Multi-Cell Battery Pack Model with Cell-to-Cell Variation and Passive Balancing.

Models series-parallel battery topologies (Ns x Np), manufacturing parameter dispersion,
cell voltage imbalance (Delta V = V_max - V_min), thermal gradients,
and dissipative passive cell balancing (bleed resistor bypass).
"""

from __future__ import annotations
import copy
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from .cell_model import BatteryCell, CellParameters, ChemistryType


@dataclass
class BalancingStatus:
    """Status of passive cell balancing circuits across series cells."""
    active_bleed_flags: List[bool]
    bleed_currents_a: List[float]
    v_delta_v: float
    v_max_cell: float
    v_min_cell: float
    max_temp_cell: float


class BatteryPack:
    """
    Multi-cell series-parallel battery pack with cell variation and passive balancing.
    
    Topology:
      - num_series (Ns): Number of cell stages connected in series.
      - num_parallel (Np): Number of cells in parallel per stage.
      - Total pack voltage = sum of stage voltages.
      - Pack current = current through each series stage.
      - Stage current is divided across parallel cells.
    """

    def __init__(
        self,
        num_series: int = 4,
        num_parallel: int = 1,
        base_params: Optional[CellParameters] = None,
        initial_soc: float = 0.90,
        initial_temp_c: float = 25.0,
        capacity_dispersion_std: float = 0.015,   # 1.5% cell manufacturing capacity variance
        resistance_dispersion_std: float = 0.040, # 4.0% cell internal resistance variance
        passive_balancing: bool = True,
        balance_voltage_threshold: float = 4.15,  # Threshold to activate balancing [V]
        balance_delta_threshold: float = 0.015,   # Minimum cell delta to activate balancing [V] (15mV)
        bleed_resistor_ohm: float = 47.0,         # Shunt bleed resistor (~88 mA at 4.15V)
        seed: int = 42,
    ) -> None:
        self.num_series = int(num_series)
        self.num_parallel = int(num_parallel)
        self.base_params = base_params or CellParameters.default_nmc()
        self.passive_balancing = passive_balancing
        self.balance_voltage_threshold = float(balance_voltage_threshold)
        self.balance_delta_threshold = float(balance_delta_threshold)
        self.bleed_resistor_ohm = float(bleed_resistor_ohm)

        # Generate individual series stage cells with realistic manufacturing dispersion
        rng = random.Random(seed)
        self.cells: List[BatteryCell] = []
        for i in range(self.num_series):
            # Perturb capacity and internal resistance for each stage
            p = copy.deepcopy(self.base_params)
            cap_mult = max(0.85, 1.0 + rng.gauss(0.0, capacity_dispersion_std))
            r_mult = max(0.80, 1.0 + rng.gauss(0.0, resistance_dispersion_std))
            
            p.nominal_capacity_ah *= cap_mult
            p.r0_ref *= r_mult
            p.r1_ref *= r_mult
            p.r2_ref *= r_mult
            
            # Slight initial SOC dispersion (e.g. slight imbalance from previous charge history)
            stage_soc = min(1.0, max(0.05, initial_soc + rng.gauss(0.0, 0.008)))
            # Interior cells run slightly warmer in packed modules
            thermal_bias = 0.5 if (0 < i < self.num_series - 1) else 0.0

            cell = BatteryCell(
                params=p,
                initial_soc=stage_soc,
                initial_temp_c=initial_temp_c + thermal_bias,
            )
            self.cells.append(cell)

        # Balancing state
        self.bleed_active = [False] * self.num_series
        self.cumulative_balancing_energy_wh = 0.0

    @property
    def nominal_pack_voltage(self) -> float:
        return self.num_series * self.base_params.nominal_voltage

    @property
    def nominal_pack_capacity_ah(self) -> float:
        return self.num_parallel * self.base_params.nominal_capacity_ah

    def get_pack_voltages(self) -> List[float]:
        return [c.calculate_terminal_voltage(0.0) for c in self.cells]

    def step(
        self,
        pack_current: float,
        ambient_temp_c: float,
        dt: float,
    ) -> Dict[str, Any]:
        """
        Advances the battery pack by time dt seconds.
        Handles current division among parallel cells, series voltage summation,
        and dissipative passive balancing.
        """
        # Current flowing into each series stage
        stage_current = pack_current
        # Current per parallel cell
        cell_base_current = stage_current / float(self.num_parallel)

        # Determine cell balancing actions before step
        v_estimates = [c.calculate_terminal_voltage(cell_base_current) for c in self.cells]
        v_min_cell = min(v_estimates)
        v_max_cell = max(v_estimates)
        v_delta = v_max_cell - v_min_cell

        bleed_currents = [0.0] * self.num_series
        self.bleed_active = [False] * self.num_series

        # Passive Balancing Logic:
        # Activated when pack is charging (pack_current < 0) or resting near top of charge,
        # cell voltage exceeds balance threshold, and delta exceeds tolerance.
        if self.passive_balancing and (pack_current <= 0.2):
            for i, v_c in enumerate(v_estimates):
                if (v_c >= self.balance_voltage_threshold) and ((v_c - v_min_cell) >= self.balance_delta_threshold):
                    # Bleed resistor discharges the higher cell
                    i_bleed = v_c / self.bleed_resistor_ohm
                    bleed_currents[i] = i_bleed
                    self.bleed_active[i] = True
                    self.cumulative_balancing_energy_wh += (v_c * i_bleed) * (dt / 3600.0)

        # Advance each cell with its effective current (base current + balancing bleed)
        stage_terminal_voltages: List[float] = []
        cell_socs: List[float] = []
        cell_temps: List[float] = []

        for i, cell in enumerate(self.cells):
            # Bleed resistor acts as an extra discharge load (+ current) on that stage
            eff_current = cell_base_current + bleed_currents[i]
            diag = cell.step(current=eff_current, ambient_temp_c=ambient_temp_c, dt=dt)
            stage_terminal_voltages.append(diag["v_terminal"])
            cell_socs.append(diag["soc_pct"])
            cell_temps.append(diag["cell_temp_c"])

        # Pack-level totals
        pack_voltage = sum(stage_terminal_voltages)
        pack_power = pack_voltage * pack_current

        return {
            "pack_voltage": pack_voltage,
            "pack_current": pack_current,
            "pack_power_w": pack_power,
            "stage_voltages": stage_terminal_voltages,
            "v_max_cell": max(stage_terminal_voltages),
            "v_min_cell": min(stage_terminal_voltages),
            "v_delta": max(stage_terminal_voltages) - min(stage_terminal_voltages),
            "cell_socs": cell_socs,
            "mean_soc_pct": sum(cell_socs) / len(cell_socs),
            "cell_temps": cell_temps,
            "max_cell_temp_c": max(cell_temps),
            "balancing_active": any(self.bleed_active),
            "bleed_active_flags": list(self.bleed_active),
            "bleed_currents_a": bleed_currents,
            "cumulative_balance_wh": self.cumulative_balancing_energy_wh,
        }

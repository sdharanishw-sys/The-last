"""
Example: Ambient Temperature Sweep
Compares battery discharge performance at -15°C, 0°C, 25°C, and 45°C.
Demonstrates internal resistance Arrhenius escalation, capacity loss, and thermal runaway limits.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from battery_sim.cell_model import BatteryCell, CellParameters
from battery_sim.profiles import ConstantCurrentProfile, ConstantTempProfile
from battery_sim.simulator import BatterySimulator


def main():
    test_temps = [-15.0, 0.0, 25.0, 45.0]
    discharge_current = 3.0  # 1C discharge for 3.0 Ah cell

    print("=" * 72)
    print(f"       TEMPERATURE SWEEP EXPERIMENT (1C = {discharge_current:.1f}A Discharge)")
    print("=" * 72)
    print(f"{'Ambient (C)':<14} | {'Delivered (Ah)':<16} | {'Energy (Wh)':<14} | {'Final Temp (C)':<16} | {'Min Volt (V)':<12}")
    print("-" * 72)

    for temp in test_temps:
        cell = BatteryCell(
            params=CellParameters.default_nmc(),
            initial_soc=1.0,
            initial_temp_c=temp,
        )
        sim = BatterySimulator(
            cell=cell,
            load_profile=ConstantCurrentProfile(discharge_current),
            temperature_profile=ConstantTempProfile(temp),
            dt=1.0,
            max_duration_s=3600.0,
        )
        res = sim.run()
        meta = res.metadata
        print(
            f"{temp:<14.1f} | "
            f"{meta.get('discharge_ah', 0):<16.3f} | "
            f"{meta.get('discharge_wh', 0):<14.2f} | "
            f"{meta.get('final_temp_c', 0):<16.1f} | "
            f"{meta.get('min_v', 0):<12.3f}"
        )
    print("=" * 72)


if __name__ == "__main__":
    main()

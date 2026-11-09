"""
Example: Multi-Cell Battery Pack (4S1P) with Passive Balancing
Demonstrates cell voltage dispersion (Delta V = V_max - V_min) due to manufacturing variation,
and dissipative passive cell balancing (bleed resistor bypass) during top-of-charge CV stage.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from battery_sim.cell_model import CellParameters
from battery_sim.pack_model import BatteryPack


def main():
    print("=" * 70)
    print("  MULTI-CELL BATTERY PACK SIMULATION (4S1P with Passive Balancing)")
    print("=" * 70)

    pack = BatteryPack(
        num_series=4,
        num_parallel=1,
        base_params=CellParameters.default_nmc(),
        initial_soc=0.96,                 # Near top of charge
        capacity_dispersion_std=0.02,     # 2% capacity variation between cells
        resistance_dispersion_std=0.05,   # 5% internal resistance variation
        passive_balancing=True,
        balance_voltage_threshold=4.18,   # Balance above 4.18V
        balance_delta_threshold=0.004,    # Trigger if cell delta > 4mV
        bleed_resistor_ohm=47.0,          # ~88mA bleed current
        seed=123,
    )

    print(f"[*] Pack configuration: 4S1P ({pack.nominal_pack_voltage:.1f}V Nominal)")
    print(f"[*] Initial cell voltages: {[round(v, 3) for v in pack.get_pack_voltages()]}")
    print(f"[*] Charging at 0.5A into top of charge...\n")

    print(f"{'Time(s)':<8} | {'Pack V':<8} | {'Cell Voltages (V)':<28} | {'Delta(mV)':<10} | {'Balancing'}")
    print("-" * 70)

    # Simulate 300 seconds of charging into top-of-charge
    charge_current = -0.5  # 0.5A charge
    for t in range(0, 301, 1):
        diag = pack.step(pack_current=charge_current, ambient_temp_c=25.0, dt=1.0)
        if t % 50 == 0:
            c_v_str = "[" + ", ".join(f"{v:.3f}" for v in diag["stage_voltages"]) + "]"
            bal_str = "ACTIVE (Bleed: " + str([round(i*1000, 1) for i in diag["bleed_currents_a"]]) + " mA)" if diag["balancing_active"] else "OFF"
            print(f"{t:<8} | {diag['pack_voltage']:<8.2f} | {c_v_str:<28} | {diag['v_delta']*1000:<10.1f} | {bal_str}")

    print("=" * 70)
    print(f"[+] Total balancing energy dissipated: {pack.cumulative_balancing_energy_wh:.3f} Wh")


if __name__ == "__main__":
    main()

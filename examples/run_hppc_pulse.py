"""
Example: Hybrid Pulse Power Characterization (HPPC) Test
Standard battery testing protocol used to measure Ohmic IR drop,
charge-transfer resistance, and diffusion polarization time constants.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from battery_sim.cell_model import BatteryCell, CellParameters
from battery_sim.profiles import HPPCProfile, ConstantTempProfile
from battery_sim.simulator import BatterySimulator
from battery_sim.visualizer import export_svg, generate_interactive_html


def main():
    print("[*] Running Hybrid Pulse Power Characterization (HPPC) Simulation...")

    cell = BatteryCell(
        params=CellParameters.default_nmc(),
        initial_soc=0.90,
        initial_temp_c=25.0,
    )

    # 4 consecutive HPPC cycles
    load = HPPCProfile(nominal_capacity_ah=3.0, discharge_c_rate=2.0, charge_c_rate=1.0, repeat_cycles=4)
    ambient = ConstantTempProfile(25.0)

    sim = BatterySimulator(
        cell=cell,
        load_profile=load,
        temperature_profile=ambient,
        dt=0.5,
        max_duration_s=1200.0,
    )
    res = sim.run()

    print(res.summary())

    res.to_csv("hppc_telemetry.csv")
    export_svg(res, "hppc_plot.svg")
    generate_interactive_html(res, "hppc_dashboard.html", title="HPPC Pulse Characterization Test")
    print("\n[+] Generated outputs: hppc_telemetry.csv, hppc_plot.svg, hppc_dashboard.html")


if __name__ == "__main__":
    main()

"""
Example: EV Dynamic Drive Cycle Simulation
Demonstrates battery response to rapid acceleration spikes and regenerative braking pulses
under sinusoidal ambient temperature variations.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from battery_sim.cell_model import BatteryCell, CellParameters
from battery_sim.profiles import DriveCycleProfile, SinusoidalTempProfile
from battery_sim.simulator import BatterySimulator
from battery_sim.visualizer import export_svg, generate_interactive_html


def main():
    print("[*] Running EV Drive Cycle Simulation...")

    # Configure 3.0 Ah NMC cell
    cell = BatteryCell(
        params=CellParameters.default_nmc(),
        initial_soc=0.90,       # Start at 90% SOC
        initial_temp_c=25.0,    # 25 deg C initial temp
    )

    # Dynamic load: 6A peak acceleration, 30% regen braking
    load = DriveCycleProfile(peak_current_a=6.0, regen_ratio=0.35, duration_s=1800.0)

    # Ambient temperature fluctuating between 15 deg C and 35 deg C
    ambient = SinusoidalTempProfile(mean_temp_c=25.0, amplitude_c=10.0, period_s=1800.0)

    # Set up and run simulation
    sim = BatterySimulator(
        cell=cell,
        load_profile=load,
        temperature_profile=ambient,
        dt=1.0,
        max_duration_s=1800.0,
    )
    result = sim.run()

    # Print summary
    print(result.summary())

    # Export outputs
    result.to_csv("drive_cycle_telemetry.csv")
    export_svg(result, "drive_cycle_plot.svg")
    generate_interactive_html(result, "drive_cycle_dashboard.html")
    print("\nOutputs generated: drive_cycle_telemetry.csv, drive_cycle_plot.svg, drive_cycle_dashboard.html")


if __name__ == "__main__":
    main()

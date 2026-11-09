"""
Command-Line Interface for the Battery Electro-Thermal Simulator.
Allows running predefined or custom simulation scenarios from the terminal,
with export to CSV, JSON, PNG plots, Interactive HTML dashboards,
and automatic Phase 3 Fault Attribution diagnostics.
"""

from __future__ import annotations
import argparse
import sys
from typing import Tuple, Optional

from .cell_model import BatteryCell, CellParameters, ChemistryType
from .profiles import (
    LoadProfile,
    TemperatureProfile,
    ConstantCurrentProfile,
    PulseProfile,
    HPPCProfile,
    DriveCycleProfile,
    DynamicStochasticProfile,
    ConstantTempProfile,
    SinusoidalTempProfile,
    StepTempProfile,
    RampTempProfile,
)
from .reference_model import BaselineCalibrator, DeviationTracker
from .fault_attribution import (
    FaultType,
    FaultScenarioConfig,
    FaultyCell,
    FaultAttributionEngine,
)
from .simulator import BatterySimulator
from .visualizer import export_plots, export_svg, generate_interactive_html, generate_phase4_dashboard
from .validation import (
    FixedThresholdMonitor,
    AdaptiveReferenceMonitor,
    BenchmarkRunner,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Physics-informed Battery Electro-Thermal Simulation & Fault Diagnostics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Battery chemistry and properties
    parser.add_argument(
        "--chemistry",
        type=str,
        default="NMC",
        choices=["NMC", "LFP", "LCO"],
        help="Battery chemistry model",
    )
    parser.add_argument(
        "--capacity",
        type=float,
        default=3.0,
        help="Nominal cell capacity in Ampere-hours (Ah)",
    )
    parser.add_argument(
        "--initial-soc",
        type=float,
        default=1.0,
        help="Initial State of Charge (0.0 to 1.0)",
    )
    parser.add_argument(
        "--initial-temp",
        type=float,
        default=25.0,
        help="Initial cell temperature in degrees Celsius",
    )

    # Load profile options
    parser.add_argument(
        "--profile",
        type=str,
        default="drive-cycle",
        choices=["drive-cycle", "constant-current", "pulse", "hppc", "stochastic"],
        help="Dynamic load current profile type",
    )
    parser.add_argument(
        "--current",
        type=float,
        default=2.5,
        help="Base / constant discharge current (Amps) for constant-current or pulse profiles",
    )
    parser.add_argument(
        "--peak-current",
        type=float,
        default=6.0,
        help="Peak current (Amps) for drive-cycle or stochastic profiles",
    )

    # Temperature profile options
    parser.add_argument(
        "--temp-profile",
        type=str,
        default="constant",
        choices=["constant", "sinusoidal", "step", "ramp"],
        help="Ambient temperature environment profile",
    )
    parser.add_argument(
        "--ambient-temp",
        type=float,
        default=25.0,
        help="Ambient temperature (°C) for constant profile or base temp",
    )
    parser.add_argument(
        "--temp-min",
        type=float,
        default=-10.0,
        help="Target cold temp (°C) for ramp / step profile",
    )
    parser.add_argument(
        "--temp-max",
        type=float,
        default=45.0,
        help="Target warm temp (°C) for ramp / step profile",
    )

    # Simulation control
    parser.add_argument(
        "--dt",
        type=float,
        default=1.0,
        help="Simulation time step in seconds",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=1800.0,
        help="Maximum simulation duration in seconds",
    )

    # Phase 3 Fault Injection & Attribution options
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run reference model calibration and automated fault attribution analysis",
    )
    parser.add_argument(
        "--fault",
        type=str,
        default="none",
        choices=["none", "resistance", "temperature", "capacity-fade", "sensor-bias"],
        help="Inject controlled fault scenario",
    )
    parser.add_argument(
        "--resistance-adder",
        type=float,
        default=0.020,
        help="Added Ohmic resistance in Ohm for resistance fault (e.g. 0.020 = +20mOhm)",
    )
    parser.add_argument(
        "--voltage-bias",
        type=float,
        default=0.040,
        help="Voltage sensor bias in Volts (e.g. 0.040 = +40mV offset)",
    )
    parser.add_argument(
        "--cooling-factor",
        type=float,
        default=0.20,
        help="Cooling multiplier for thermal fault (0.20 = 80%% cooling loss)",
    )
    parser.add_argument(
        "--capacity-retention",
        type=float,
        default=0.80,
        help="Capacity retention factor for capacity fade (0.80 = 20%% loss)",
    )

    # Outputs
    parser.add_argument(
        "--csv",
        type=str,
        default="battery_telemetry.csv",
        help="Path to export telemetry CSV (set to '' to skip)",
    )
    parser.add_argument(
        "--json",
        type=str,
        default="",
        help="Path to export telemetry JSON (optional)",
    )
    parser.add_argument(
        "--svg",
        type=str,
        default="battery_plot.svg",
        help="Path to save publication-quality standalone SVG vector chart (set to '' to skip)",
    )
    parser.add_argument(
        "--plot",
        type=str,
        default="",
        help="Path to save Matplotlib PNG plot (optional, requires matplotlib)",
    )
    parser.add_argument(
        "--html",
        type=str,
        default="battery_dashboard.html",
        help="Path to save interactive HTML dashboard (set to '' to skip)",
    )
    parser.add_argument(
        "--phase4-dashboard",
        type=str,
        default="",
        help="Path to save Phase 4 interactive health & validation dashboard (100%% offline, zero CDN)",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run Phase 4 quantitative benchmark comparing Adaptive Reference Model vs Fixed-Threshold Baseline",
    )

    return parser


def setup_simulation_components(args: argparse.Namespace) -> Tuple[BatteryCell, LoadProfile, TemperatureProfile, Optional[FaultScenarioConfig]]:
    chem = ChemistryType(args.chemistry)
    if chem == ChemistryType.NMC:
        params = CellParameters.default_nmc()
    elif chem == ChemistryType.LFP:
        params = CellParameters.default_lfp()
    else:
        params = CellParameters(chemistry=chem)
    params.nominal_capacity_ah = args.capacity

    cell = BatteryCell(
        params=params,
        initial_soc=args.initial_soc,
        initial_temp_c=args.initial_temp,
    )

    # Load profile
    if args.profile == "constant-current":
        load = ConstantCurrentProfile(current_a=args.current, duration_s=args.duration)
    elif args.profile == "pulse":
        load = PulseProfile(
            base_current_a=0.5,
            pulse_current_a=args.current,
            pulse_width_s=10.0,
            period_s=40.0,
            duration_s=args.duration,
        )
    elif args.profile == "hppc":
        load = HPPCProfile(nominal_capacity_ah=args.capacity)
    elif args.profile == "stochastic":
        load = DynamicStochasticProfile(
            base_current_a=args.current,
            spike_magnitude_a=args.peak_current,
            duration_s=args.duration,
        )
    else:  # drive-cycle
        load = DriveCycleProfile(peak_current_a=args.peak_current, duration_s=args.duration)

    # Temperature profile
    if args.temp_profile == "sinusoidal":
        temp_prof = SinusoidalTempProfile(
            mean_temp_c=args.ambient_temp,
            amplitude_c=10.0,
            period_s=args.duration,
        )
    elif args.temp_profile == "step":
        mid = args.duration / 2.0
        temp_prof = StepTempProfile([(0, args.ambient_temp), (mid, args.temp_min)])
    elif args.temp_profile == "ramp":
        temp_prof = RampTempProfile(
            start_temp_c=args.temp_min,
            end_temp_c=args.temp_max,
            ramp_duration_s=args.duration,
        )
    else:
        temp_prof = ConstantTempProfile(temp_c=args.ambient_temp)

    # Fault configuration
    fault_cfg = None
    if args.fault != "none":
        if args.fault == "resistance":
            fault_cfg = FaultScenarioConfig(
                fault_type=FaultType.INCREASED_RESISTANCE,
                description=f"Injected +{args.resistance_adder*1000:.1f} mOhm resistance degradation",
                resistance_adder_ohm=args.resistance_adder,
            )
        elif args.fault == "temperature":
            fault_cfg = FaultScenarioConfig(
                fault_type=FaultType.TEMPERATURE_RISE,
                description=f"Injected thermal dissipation fault ({args.cooling_factor*100:.0f}%% cooling)",
                cooling_factor=args.cooling_factor,
                external_heat_flux_w=2.0,
            )
        elif args.fault == "capacity-fade":
            fault_cfg = FaultScenarioConfig(
                fault_type=FaultType.CAPACITY_FADE,
                description=f"Injected {(1-args.capacity_retention)*100:.1f}%% capacity fade",
                capacity_retention_factor=args.capacity_retention,
            )
        elif args.fault == "sensor-bias":
            fault_cfg = FaultScenarioConfig(
                fault_type=FaultType.VOLTAGE_SENSOR_BIAS,
                description=f"Injected {args.voltage_bias*1000:+.1f} mV voltage sensor bias",
                voltage_bias_v=args.voltage_bias,
            )

    return cell, load, temp_prof, fault_cfg


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print(f"\n[+] Initializing Battery Simulation...")
    print(f"    Chemistry: {args.chemistry} | Capacity: {args.capacity:.2f} Ah | Initial SOC: {args.initial_soc*100:.1f}%")
    print(f"    Load Profile: {args.profile} | Ambient Profile: {args.temp_profile} ({args.ambient_temp} deg C)")
    print(f"    Step size (dt): {args.dt:.2f}s | Target duration: {args.duration:.1f}s")
    if args.fault != "none":
        print(f"    [!] Fault Injection ACTIVE: {args.fault}")

    cell, load_prof, temp_prof, fault_cfg = setup_simulation_components(args)

    # If diagnosis or fault active, wrap cell and calibrate baseline
    baseline = None
    tracker = None
    if args.diagnose or fault_cfg is not None:
        print("\n[*] Calibrating baseline reference model for diagnostic comparison...")
        cal_cell = BatteryCell(params=cell.params, initial_soc=1.0, initial_temp_c=25.0)
        baseline = BaselineCalibrator(cal_cell, cell_id=f"{args.chemistry}-BASELINE").build()
        ref_cell = BatteryCell(params=cell.params)
        tracker = DeviationTracker(baseline=baseline, cell=ref_cell)

    if fault_cfg is not None:
        sim_cell = FaultyCell(base_cell=cell, config=fault_cfg, seed=42)
    else:
        sim_cell = cell

    simulator = BatterySimulator(
        cell=sim_cell,
        load_profile=load_prof,
        temperature_profile=temp_prof,
        dt=args.dt,
        max_duration_s=args.duration,
    )

    # Run simulation
    result = simulator.run()

    # If tracking is active, pass telemetry into tracker and run diagnostic attribution
    if tracker is not None:
        for s in result.steps:
            tracker.record(
                time_s=s.time_s,
                current_a=s.current_a,
                soc=s.soc,
                v_measured=s.v_terminal,
                dcir_measured_mohm=s.r0_mohm,
                cell_temp_c=s.cell_temp_c,
                ambient_temp_c=s.ambient_temp_c,
                dt=args.dt,
            )
        dev_report = tracker.finalize()
        engine = FaultAttributionEngine(baseline=baseline, cell=ref_cell)
        diagnosis = engine.diagnose(dev_report, result.steps)

    # Print summary
    print(result.summary())

    if tracker is not None and diagnosis is not None:
        print("\n" + diagnosis.summary() + "\n")

    # Export CSV
    if args.csv:
        result.to_csv(args.csv)
        print(f"[+] Telemetry exported to CSV: {args.csv}")

    # Export JSON
    if args.json:
        result.to_json(args.json)
        print(f"[+] Telemetry exported to JSON: {args.json}")

    # Export SVG Plot (zero-dependency)
    if args.svg:
        export_svg(result, args.svg)
        print(f"[+] Vector Plot saved: {args.svg}")

    # Export Interactive HTML
    if args.html:
        generate_interactive_html(result, args.html, title=f"Battery Digital Twin ({args.chemistry} - {args.profile})")
        print(f"[+] Interactive HTML Dashboard saved: {args.html}")

    # Phase 4 Benchmark Execution
    bm_summary = None
    if args.benchmark:
        print("\n[*] Executing Phase 4 Benchmark (Adaptive vs Fixed-Threshold)...")
        runner = BenchmarkRunner(baseline=baseline)
        bm_summary = runner.run_benchmark(sim_duration_s=360.0)
        print("\n" + bm_summary.summary() + "\n")

    # Export Phase 4 Dashboard (100% offline, zero CDN)
    if args.phase4_dashboard:
        generate_phase4_dashboard(
            telemetry=result,
            deviation_report=dev_report if 'dev_report' in locals() else None,
            diagnosis=diagnosis if 'diagnosis' in locals() else None,
            benchmark_summary=bm_summary,
            output_path=args.phase4_dashboard,
            title=f"Battery Validation Dashboard ({args.chemistry} - {args.profile})",
        )
        print(f"[+] Phase 4 Health & Validation Dashboard saved: {args.phase4_dashboard}")

    # Export Static Plot (optional matplotlib)
    if args.plot:
        try:
            export_plots(result, args.plot)
            print(f"[+] Matplotlib Plot saved: {args.plot}")
        except Exception as e:
            print(f"[!] Could not generate static plot: {e}")

    print("\n[+] Simulation completed successfully!\n")


if __name__ == "__main__":
    main()

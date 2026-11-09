import sys
from pathlib import Path
sys.path.insert(0, r'D:\Python Battery Simulation Model')

from battery_sim.cell_model import BatteryCell, CellParameters
from battery_sim.profiles import DriveCycleProfile, LoadProfile
from battery_sim.reference_model import BaselineCalibrator
from battery_sim.fault_attribution import (
    FaultType,
    FaultScenarioConfig,
    FaultyCell,
    FixedThresholdMonitor,
    AdaptiveReferenceMonitor,
)

class OneHourDriveCycle(LoadProfile):
    def __init__(self, duration_s: float = 3600.0):
        self.base_drive = DriveCycleProfile(peak_current_a=2.6, regen_ratio=0.28, duration_s=duration_s, seed=42)
        self._duration_s = duration_s

    def get_current(self, t: float) -> float:
        # Periodic highway cruising and rest intervals
        phase = t % 120.0
        if 90.0 <= phase < 105.0:
            return 0.0 # Red light / rest
        return self.base_drive.get_current(t)

    def duration(self) -> float:
        return self._duration_s

cal_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=1.0, initial_temp_c=25.0)
calibrator = BaselineCalibrator(cal_cell, cell_id="NMC-PHASE4-REF")
baseline = calibrator.build()

fault_cfg = FaultScenarioConfig(
    fault_type=FaultType.INCREASED_RESISTANCE,
    resistance_adder_ohm=0.014,
    description="Early contact corrosion (+14 mOhm added impedance)",
)

sim_cell = FaultyCell(
    base_cell=BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.98, initial_temp_c=25.0),
    config=fault_cfg,
    seed=42,
)
ref_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.98, initial_temp_c=25.0)

profile = OneHourDriveCycle(duration_s=3600.0)
dt = 6.0 # 600 steps over 1 hour
total_steps = int(profile.duration() / dt)
print(f"Total steps for 1 hour: {total_steps}, dt={dt}s")

reached_cutoff = False
for step_idx in range(total_steps):
    t_curr = (step_idx + 1) * dt
    i_load = profile.get_current(t_curr)
    diag = sim_cell.step(current=i_load, ambient_temp_c=25.0, dt=dt)
    if diag["v_terminal"] <= sim_cell.params.v_min:
        print(f"Reached cutoff at {t_curr}s")
        reached_cutoff = True
        break

if not reached_cutoff:
    print(f"SUCCESS: Simulated 1 full hour ({profile.duration()}s / 60 mins)!")
    print(f"Final SOC: {diag['soc']*100:.1f}%, Final Voltage: {diag['v_terminal']:.3f}V, Final Temp: {diag['temp_cell_c']:.1f}C")

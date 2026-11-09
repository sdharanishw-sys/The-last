"""
Dynamic Load and Ambient Temperature Profiles for Battery Simulation.
Generates realistic electrical loads (EV drive cycles, HPPC pulses, stochastic loads)
and ambient thermal environments (diurnal swings, thermal shock, chamber ramps).
"""

from __future__ import annotations
import math
import random
from typing import Callable, List, Tuple, Optional


class LoadProfile:
    """Base class for current load profiles [Amperes]. Positive = discharge, negative = charge."""

    def get_current(self, t: float) -> float:
        raise NotImplementedError

    def duration(self) -> Optional[float]:
        return None

    def __call__(self, t: float) -> float:
        return self.get_current(t)


class ConstantCurrentProfile(LoadProfile):
    """Constant current charge (negative) or discharge (positive)."""

    def __init__(self, current_a: float, duration_s: Optional[float] = None) -> None:
        self.current_a = float(current_a)
        self._duration_s = duration_s

    def get_current(self, t: float) -> float:
        return self.current_a

    def duration(self) -> Optional[float]:
        return self._duration_s


class PulseProfile(LoadProfile):
    """Pulsed load (e.g. telecom transmit bursts, pulsed power devices)."""

    def __init__(
        self,
        base_current_a: float = 0.5,
        pulse_current_a: float = 4.0,
        pulse_width_s: float = 5.0,
        period_s: float = 20.0,
        duration_s: Optional[float] = 1200.0,
    ) -> None:
        self.base_current_a = base_current_a
        self.pulse_current_a = pulse_current_a
        self.pulse_width_s = pulse_width_s
        self.period_s = period_s
        self._duration_s = duration_s

    def get_current(self, t: float) -> float:
        phase = t % self.period_s
        if phase < self.pulse_width_s:
            return self.pulse_current_a
        return self.base_current_a

    def duration(self) -> Optional[float]:
        return self._duration_s


class HPPCProfile(LoadProfile):
    """
    Hybrid Pulse Power Characterization (HPPC) profile used in automotive battery testing.
    Consists of repeating test blocks:
      - Rest (relaxation)
      - 10s Discharge Pulse (e.g. 1C - 3C)
      - 40s Rest
      - 10s Charge/Regen Pulse (e.g. 0.75C)
      - Rest
      - Constant current discharge step to lower SOC to next test point.
    """

    def __init__(
        self,
        nominal_capacity_ah: float = 3.0,
        discharge_c_rate: float = 2.0,
        charge_c_rate: float = 1.0,
        repeat_cycles: int = 5,
    ) -> None:
        self.c_discharge = discharge_c_rate * nominal_capacity_ah
        self.c_charge = -charge_c_rate * nominal_capacity_ah
        self.c_step = 0.5 * nominal_capacity_ah
        self.repeat_cycles = repeat_cycles
        self.cycle_period = 300.0  # 5 minutes per HPPC SOC decade

    def get_current(self, t: float) -> float:
        phase = t % self.cycle_period
        if phase < 30.0:
            return 0.0  # Initial rest
        elif phase < 40.0:
            return self.c_discharge  # 10s high discharge pulse
        elif phase < 80.0:
            return 0.0  # 40s relaxation
        elif phase < 90.0:
            return self.c_charge  # 10s regen pulse
        elif phase < 120.0:
            return 0.0  # 30s relaxation
        elif phase < 260.0:
            return self.c_step  # Step down SOC
        else:
            return 0.0  # Rest before next pulse set

    def duration(self) -> Optional[float]:
        return self.cycle_period * self.repeat_cycles


class DriveCycleProfile(LoadProfile):
    """
    Synthetic Electric Vehicle / Drone dynamic drive cycle profile.
    Simulates high-demand accelerations, highway cruises, stops, and regenerative braking.
    """

    def __init__(
        self,
        peak_current_a: float = 6.0,
        regen_ratio: float = 0.35,
        duration_s: float = 1800.0,
        seed: int = 101,
    ) -> None:
        self.peak_current_a = peak_current_a
        self.max_regen_a = -peak_current_a * regen_ratio
        self._duration_s = duration_s
        
        # Precompute repeatable smooth dynamic waveform with multi-frequency harmonics
        rng = random.Random(seed)
        self.frequencies = [0.005, 0.012, 0.035, 0.08, 0.15]
        self.amplitudes = [0.4, 0.3, 0.2, 0.15, 0.1]
        self.phases = [rng.uniform(0, 2 * math.pi) for _ in self.frequencies]
        self.micro_noise = [rng.gauss(0, 0.08) for _ in range(int(duration_s) + 1)]

    def get_current(self, t: float) -> float:
        # Sum of Fourier-like components to create drive cycle behavior
        val = 0.45  # Baseline cruising draw
        for freq, amp, phase in zip(self.frequencies, self.amplitudes, self.phases):
            val += amp * math.sin(2 * math.pi * freq * t + phase)
        
        idx = min(int(t), len(self.micro_noise) - 1)
        val += self.micro_noise[idx]
        
        # Inject occasional sharp accelerations and braking events
        accel_burst = math.sin(0.04 * t) ** 4
        brake_burst = math.sin(0.02 * t + 1.2) ** 8
        val = val * (1.0 + 1.2 * accel_burst) - (0.8 * brake_burst)

        # Scale to peak current and clip
        scaled = val * self.peak_current_a
        return float(min(self.peak_current_a, max(self.max_regen_a, scaled)))

    def duration(self) -> Optional[float]:
        return self._duration_s


class DynamicStochasticProfile(LoadProfile):
    """Stochastic random-walk load profile simulating unpredictable consumer electronics / IoT tasks."""

    def __init__(
        self,
        base_current_a: float = 1.0,
        sigma_a: float = 0.8,
        spike_probability: float = 0.05,
        spike_magnitude_a: float = 4.0,
        duration_s: float = 1200.0,
        seed: int = 42,
    ) -> None:
        self._duration_s = duration_s
        self.values: List[float] = []
        rng = random.Random(seed)
        
        # Generate random-walk Markov process
        curr = base_current_a
        for _ in range(int(duration_s) + 5):
            curr = 0.95 * curr + 0.05 * base_current_a + rng.gauss(0, sigma_a * 0.2)
            val = max(0.05, curr)
            if rng.random() < spike_probability:
                val += rng.uniform(spike_magnitude_a * 0.5, spike_magnitude_a)
            self.values.append(val)

    def get_current(self, t: float) -> float:
        idx = min(int(t), len(self.values) - 1)
        return self.values[idx]

    def duration(self) -> Optional[float]:
        return self._duration_s


class MultiStepProfile(LoadProfile):
    """Sequence of constant current steps: list of (duration_seconds, current_amperes)."""

    def __init__(self, steps: List[Tuple[float, float]]) -> None:
        self.steps = steps
        self._total_duration = sum(dur for dur, _ in steps)

    def get_current(self, t: float) -> float:
        cumulative = 0.0
        for dur, curr in self.steps:
            cumulative += dur
            if t <= cumulative:
                return curr
        return self.steps[-1][1] if self.steps else 0.0

    def duration(self) -> Optional[float]:
        return self._total_duration


# =========================================================================
# Ambient Temperature Profiles
# =========================================================================

class TemperatureProfile:
    """Base class for ambient temperature profiles [deg C]."""

    def get_temperature(self, t: float) -> float:
        raise NotImplementedError

    def __call__(self, t: float) -> float:
        return self.get_temperature(t)


class ConstantTempProfile(TemperatureProfile):
    """Constant ambient temperature."""

    def __init__(self, temp_c: float = 25.0) -> None:
        self.temp_c = float(temp_c)

    def get_temperature(self, t: float) -> float:
        return self.temp_c


class SinusoidalTempProfile(TemperatureProfile):
    """Diurnal ambient temperature fluctuation (e.g. outdoor deployment / day-night cycles)."""

    def __init__(
        self,
        mean_temp_c: float = 25.0,
        amplitude_c: float = 12.0,
        period_s: float = 1800.0,  # Scaled period for simulation observation
    ) -> None:
        self.mean_temp_c = mean_temp_c
        self.amplitude_c = amplitude_c
        self.period_s = period_s

    def get_temperature(self, t: float) -> float:
        return self.mean_temp_c + self.amplitude_c * math.sin(2 * math.pi * t / self.period_s)


class StepTempProfile(TemperatureProfile):
    """Thermal shock / multi-environment step transitions (e.g. room temp -> freezing outdoor)."""

    def __init__(self, schedule: List[Tuple[float, float]]) -> None:
        """
        schedule: list of (transition_time_seconds, target_temp_c).
        Sorted by transition time.
        """
        self.schedule = sorted(schedule, key=lambda x: x[0])

    def get_temperature(self, t: float) -> float:
        current_temp = self.schedule[0][1] if self.schedule else 25.0
        for transition_time, temp in self.schedule:
            if t >= transition_time:
                current_temp = temp
            else:
                break
        return current_temp


class RampTempProfile(TemperatureProfile):
    """Linear thermal ramp (e.g. environmental chamber testing)."""

    def __init__(
        self,
        start_temp_c: float = -10.0,
        end_temp_c: float = 50.0,
        ramp_duration_s: float = 1800.0,
    ) -> None:
        self.start_temp_c = start_temp_c
        self.end_temp_c = end_temp_c
        self.ramp_duration_s = ramp_duration_s

    def get_temperature(self, t: float) -> float:
        fraction = min(1.0, max(0.0, t / self.ramp_duration_s))
        return self.start_temp_c + fraction * (self.end_temp_c - self.start_temp_c)


class BuiltinProfiles:
    """Helper factory for commonly used load and temperature combinations."""

    @staticmethod
    def ev_urban_drive(peak_current: float = 6.0) -> Tuple[LoadProfile, TemperatureProfile]:
        return DriveCycleProfile(peak_current_a=peak_current, duration_s=1800.0), ConstantTempProfile(25.0)

    @staticmethod
    def winter_drive(peak_current: float = 5.0) -> Tuple[LoadProfile, TemperatureProfile]:
        # Sub-zero drive cycle with sudden thermal drop
        return (
            DriveCycleProfile(peak_current_a=peak_current, duration_s=1800.0),
            StepTempProfile([(0, 15.0), (300, -10.0), (1200, -15.0)]),
        )

    @staticmethod
    def hot_desert_fast_discharge() -> Tuple[LoadProfile, TemperatureProfile]:
        return ConstantCurrentProfile(current_a=4.5, duration_s=2400.0), ConstantTempProfile(42.0)

    @staticmethod
    def hppc_characterization(nominal_ah: float = 3.0) -> Tuple[LoadProfile, TemperatureProfile]:
        return HPPCProfile(nominal_capacity_ah=nominal_ah, repeat_cycles=4), ConstantTempProfile(25.0)


class AggressiveSportProfile(LoadProfile):
    """Aggressive / Sport EV profile: peak 6.0A (2C), rapid ramps, high regen."""

    def __init__(self, duration_s: float = 600.0) -> None:
        self.base = DriveCycleProfile(peak_current_a=6.0, regen_ratio=0.45, duration_s=duration_s)
        self._duration_s = duration_s

    def get_current(self, t: float) -> float:
        # Periodic 5s high acceleration burst (6.0A) then 5s strong regen (-2.5A)
        phase = t % 60.0
        if 20.0 <= phase < 26.0:
            return 6.0
        elif 26.0 <= phase < 31.0:
            return -2.5
        return self.base.get_current(t)

    def duration(self) -> Optional[float]:
        return self._duration_s


class EcoConservativeProfile(LoadProfile):
    """Eco / Conservative profile: gentle demand (< 1.5A, 0.5C), smooth ramps."""

    def __init__(self, duration_s: float = 600.0) -> None:
        self.base = DriveCycleProfile(peak_current_a=1.5, regen_ratio=0.15, duration_s=duration_s)
        self._duration_s = duration_s

    def get_current(self, t: float) -> float:
        return self.base.get_current(t) * 0.7

    def duration(self) -> Optional[float]:
        return self._duration_s


class StopAndGoUrbanProfile(LoadProfile):
    """Stop-and-Go Urban profile: repeated 15s zero-current stops and short 3.2A bursts."""

    def __init__(self, duration_s: float = 600.0) -> None:
        self._duration_s = duration_s

    def get_current(self, t: float) -> float:
        phase = t % 45.0
        if phase < 15.0:
            return 0.0   # Stop at traffic light / idling
        elif phase < 25.0:
            return 3.2   # Acceleration
        elif phase < 35.0:
            return 1.2   # Low speed crawl
        else:
            return -1.0  # Deceleration regen

    def duration(self) -> Optional[float]:
        return self._duration_s


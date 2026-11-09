"""
Physics-informed 2-RC Thevenin Electro-Thermal Cell Model.
Models dynamic terminal voltage, internal polarization, SOC tracking, and lumped thermal balance.
Strict thermodynamic monotonicity of Open Circuit Voltage (OCV) is guaranteed via Monotone Cubic Spline.
"""

from __future__ import annotations
import bisect
import math
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Dict, Any, List

# Universal gas constant [J / (mol * K)]
R_GAS = 8.314462


class ChemistryType(str, Enum):
    NMC = "NMC"  # Lithium Nickel Manganese Cobalt Oxide
    LFP = "LFP"  # Lithium Iron Phosphate
    LCO = "LCO"  # Lithium Cobalt Oxide


class MonotonicSpline:
    """
    Fritsch-Carlson Monotone Cubic Spline Interpolation.
    Guarantees strict monotonicity: d(OCV)/d(SOC) >= 0 everywhere without Runge-phenomenon wiggles.
    """

    def __init__(self, x_pts: List[float], y_pts: List[float]) -> None:
        if len(x_pts) != len(y_pts) or len(x_pts) < 2:
            raise ValueError("Spline requires at least 2 points of identical length.")
        self.x = [float(v) for v in x_pts]
        self.y = [float(v) for v in y_pts]
        self.n = len(self.x)

        # Secants
        dx = [self.x[i + 1] - self.x[i] for i in range(self.n - 1)]
        dy = [self.y[i + 1] - self.y[i] for i in range(self.n - 1)]
        m = [dy[i] / dx[i] for i in range(self.n - 1)]

        # Slopes at knots
        c1s = [m[0]]
        for i in range(self.n - 2):
            m1 = m[i]
            m2 = m[i + 1]
            if m1 * m2 <= 0.0:
                c1s.append(0.0)
            else:
                dx1 = dx[i]
                dx2 = dx[i + 1]
                w1 = 2.0 * dx2 + dx1
                w2 = dx2 + 2.0 * dx1
                c1s.append((w1 + w2) / (w1 / m1 + w2 / m2))
        c1s.append(m[-1])
        self.c1s = c1s
        self.dx = dx

    def evaluate(self, x_val: float) -> float:
        x_val = min(max(float(x_val), self.x[0]), self.x[-1])
        idx = bisect.bisect_right(self.x, x_val) - 1
        idx = min(max(idx, 0), self.n - 2)

        h = self.dx[idx]
        t = (x_val - self.x[idx]) / h
        h00 = (1.0 + 2.0 * t) * ((1.0 - t) ** 2)
        h10 = t * ((1.0 - t) ** 2)
        h01 = (t ** 2) * (3.0 - 2.0 * t)
        h11 = (t ** 2) * (t - 1.0)

        return (
            h00 * self.y[idx]
            + h10 * h * self.c1s[idx]
            + h01 * self.y[idx + 1]
            + h11 * h * self.c1s[idx + 1]
        )


# Monotonic experimental OCV curves
_NMC_SOC = [0.0, 0.01, 0.03, 0.05, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.90, 0.96, 1.0]
_NMC_OCV = [2.75, 2.95, 3.20, 3.42, 3.56, 3.65, 3.72, 3.78, 3.88, 4.02, 4.12, 4.18, 4.20]
_NMC_SPLINE = MonotonicSpline(_NMC_SOC, _NMC_OCV)

_LFP_SOC = [0.0, 0.01, 0.03, 0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 0.90, 0.95, 1.0]
_LFP_OCV = [2.50, 2.75, 3.05, 3.18, 3.24, 3.28, 3.29, 3.31, 3.33, 3.38, 3.48, 3.65]
_LFP_SPLINE = MonotonicSpline(_LFP_SOC, _LFP_OCV)


@dataclass
class CellParameters:
    """Electrical and thermal parameters for a battery cell."""
    chemistry: ChemistryType = ChemistryType.NMC
    nominal_capacity_ah: float = 3.0       # Rated capacity at 25 deg C [Ah]
    nominal_voltage: float = 3.7           # Nominal cell voltage [V]
    v_max: float = 4.20                    # Maximum cutoff voltage [V]
    v_min: float = 2.80                    # Minimum cutoff voltage [V]
    
    # Internal impedance parameters at reference temperature (25 deg C)
    r0_ref: float = 0.026                  # Ohmic resistance [Ohm]
    r1_ref: float = 0.014                  # RC1 activation resistance [Ohm]
    c1_ref: float = 1200.0                 # RC1 activation capacitance [Farad] (~17s time constant)
    r2_ref: float = 0.018                  # RC2 diffusion resistance [Ohm]
    c2_ref: float = 4500.0                 # RC2 diffusion capacitance [Farad] (~81s time constant)
    
    # Arrhenius activation energies [J / mol]
    ea_r0: float = 22000.0                 # Activation energy for R0
    ea_r1: float = 20000.0                 # Activation energy for R1
    ea_r2: float = 18000.0                 # Activation energy for R2
    t_ref_k: float = 298.15                # Reference temp: 25 deg C in Kelvin (273.15 + 25)
    
    # Thermal characteristics (typical 18650 / 21700 cylindrical cell)
    mass_kg: float = 0.048                 # Cell mass [kg] (~48 grams)
    specific_heat_cp: float = 920.0        # Specific heat capacity [J / (kg * K)]
    surface_area_m2: float = 0.0042        # Heat dissipation surface area [m^2]
    convective_h: float = 12.0             # Convective heat transfer coefficient [W / (m^2 * K)]
    
    # Entropic heat coefficient [V / K] (temperature sensitivity of OCV)
    d_ocv_d_t: float = -0.00022
    
    # Efficiency & capacity temperature derating
    coulombic_efficiency_charge: float = 0.995
    temp_capacity_derating_per_c: float = 0.006  # 0.6% capacity loss per deg C below 25C

    @classmethod
    def default_nmc(cls) -> "CellParameters":
        """Factory for a standard 18650 NMC cell (e.g. Samsung 30Q / LG HG2)."""
        return cls(
            chemistry=ChemistryType.NMC,
            nominal_capacity_ah=3.0,
            nominal_voltage=3.7,
            v_max=4.20,
            v_min=2.80,
            r0_ref=0.026,
            r1_ref=0.014,
            c1_ref=1200.0,
            r2_ref=0.018,
            c2_ref=4500.0,
            mass_kg=0.048,
        )

    @classmethod
    def default_lfp(cls) -> "CellParameters":
        """Factory for a standard LFP cell (e.g. 26650 Lithium Iron Phosphate)."""
        return cls(
            chemistry=ChemistryType.LFP,
            nominal_capacity_ah=3.2,
            nominal_voltage=3.2,
            v_max=3.65,
            v_min=2.50,
            r0_ref=0.020,
            r1_ref=0.010,
            c1_ref=1500.0,
            r2_ref=0.015,
            c2_ref=6000.0,
            mass_kg=0.085,
            surface_area_m2=0.0065,
            d_ocv_d_t=-0.00010,
        )


class BatteryCell:
    """
    Simulation of a lithium-ion battery cell using a 2-RC Thevenin equivalent circuit
    coupled with a 1D lumped-parameter thermal balance model.
    """

    def __init__(
        self,
        params: CellParameters | None = None,
        initial_soc: float = 1.0,
        initial_temp_c: float = 25.0,
    ) -> None:
        self.params = params or CellParameters.default_nmc()
        
        # State variables
        self.soc = float(min(max(initial_soc, 0.0), 1.0))
        self.v_rc1 = 0.0  # Voltage across fast RC network (charge-transfer polarization)
        self.v_rc2 = 0.0  # Voltage across slow RC network (diffusion polarization)
        self.temperature_c = float(initial_temp_c)
        
        # Cumulative tracking
        self.cumulative_energy_wh_discharge = 0.0
        self.cumulative_energy_wh_charge = 0.0
        self.cumulative_ah_throughput = 0.0

    @property
    def temperature_k(self) -> float:
        """Cell temperature in Kelvin."""
        return self.temperature_c + 273.15

    def effective_capacity_ah(self, temp_c: float | None = None) -> float:
        """
        Calculates usable capacity derated by cell temperature.
        Batteries lose usable capacity at low temperatures due to sluggish kinetics.
        """
        t = self.temperature_c if temp_c is None else temp_c
        if t >= 25.0:
            boost = min(0.05, (t - 25.0) * 0.002)
            return self.params.nominal_capacity_ah * (1.0 + boost)
        else:
            delta_t = 25.0 - t
            factor = max(0.40, 1.0 - (delta_t * self.params.temp_capacity_derating_per_c))
            return self.params.nominal_capacity_ah * factor

    def open_circuit_voltage(self, soc: float | None = None, temp_c: float | None = None) -> float:
        """
        Computes the thermodynamic Open Circuit Voltage (OCV) as a function of SOC and Temperature.
        Guarantees strict monotonicity across all SOC values [0, 1].
        """
        s = self.soc if soc is None else float(soc)
        s = float(min(max(s, 0.0), 1.0))
        t = self.temperature_c if temp_c is None else float(temp_c)
        
        if self.params.chemistry == ChemistryType.NMC:
            v_base = _NMC_SPLINE.evaluate(s)
        elif self.params.chemistry == ChemistryType.LFP:
            v_base = _LFP_SPLINE.evaluate(s)
        else:
            v_base = 3.50 + 0.70 * s

        # Entropic thermal contribution: dOCV/dT * (T - T_ref)
        entropic_shift = self.params.d_ocv_d_t * (t - 25.0)
        return float(v_base + entropic_shift)

    def _arrhenius_scaling(self, ea: float, temp_k: float) -> float:
        """Calculates Arrhenius resistance multiplier based on temperature."""
        temp_k = max(233.15, temp_k)  # Cap at -40 deg C minimum for numerical stability
        exponent = (ea / R_GAS) * ((1.0 / temp_k) - (1.0 / self.params.t_ref_k))
        exponent = max(-5.0, min(8.0, exponent))
        return math.exp(exponent)

    def ohmic_resistance(self, soc: float | None = None, temp_k: float | None = None) -> float:
        """
        Calculates dynamic Ohmic internal resistance R0(SOC, T).
        Strictly follows Arrhenius kinetics with respect to temperature.
        """
        s = self.soc if soc is None else float(min(max(soc, 0.0), 1.0))
        tk = self.temperature_k if temp_k is None else float(temp_k)

        temp_mult = self._arrhenius_scaling(self.params.ea_r0, tk)
        soc_mult = 1.0 + 0.45 * ((1.0 - s) ** 3) + 0.25 * (s ** 4)
        return float(self.params.r0_ref * temp_mult * soc_mult)

    def polarization_impedances(
        self, temp_k: float | None = None
    ) -> Tuple[float, float, float, float]:
        """Returns scaled (R1, C1, R2, C2) under cell temperature."""
        tk = self.temperature_k if temp_k is None else float(temp_k)
        
        mult_r1 = self._arrhenius_scaling(self.params.ea_r1, tk)
        mult_r2 = self._arrhenius_scaling(self.params.ea_r2, tk)
        
        r1 = self.params.r1_ref * mult_r1
        r2 = self.params.r2_ref * mult_r2
        c1 = self.params.c1_ref / math.sqrt(mult_r1)
        c2 = self.params.c2_ref / math.sqrt(mult_r2)
        return r1, c1, r2, c2

    def calculate_terminal_voltage(self, current: float) -> float:
        """
        Calculates instantaneous terminal voltage V_term for a candidate current.
        Current sign convention:
          I > 0: Discharge (current flows out of battery, decreases voltage)
          I < 0: Charge (current flows into battery, raises voltage)
        """
        v_ocv = self.open_circuit_voltage()
        r0 = self.ohmic_resistance()
        return v_ocv - (current * r0) - self.v_rc1 - self.v_rc2

    def step(
        self,
        current: float,
        ambient_temp_c: float,
        dt: float,
    ) -> Dict[str, Any]:
        """
        Advances the cell simulation by time interval dt (seconds) under current (Amperes)
        and ambient temperature (deg C).
        """
        dt = float(dt)
        if dt <= 0:
            raise ValueError(f"dt must be positive, got {dt}")

        v_ocv = self.open_circuit_voltage()
        r0 = self.ohmic_resistance()
        r1, c1, r2, c2 = self.polarization_impedances()

        # 1. Instantaneous Terminal Voltage
        v_terminal = v_ocv - (current * r0) - self.v_rc1 - self.v_rc2

        # 2. Coulomb Counting for State of Charge (SOC)
        eff = 1.0 if current >= 0 else self.params.coulombic_efficiency_charge
        q_eff_ah = self.effective_capacity_ah()
        delta_soc = -(current * eff * dt) / (q_eff_ah * 3600.0)
        self.soc = min(max(self.soc + delta_soc, 0.0), 1.0)

        # 3. Dynamic Polarization Voltage integration (analytical exponential solution)
        tau1 = max(1e-4, r1 * c1)
        exp1 = math.exp(-dt / tau1)
        self.v_rc1 = self.v_rc1 * exp1 + current * r1 * (1.0 - exp1)

        tau2 = max(1e-4, r2 * c2)
        exp2 = math.exp(-dt / tau2)
        self.v_rc2 = self.v_rc2 * exp2 + current * r2 * (1.0 - exp2)

        # 4. Thermal Balance & Heat Generation
        q_joule = (current ** 2) * r0
        q_polarization = ((self.v_rc1 ** 2) / r1) + ((self.v_rc2 ** 2) / r2)
        q_reversible = -current * self.temperature_k * self.params.d_ocv_d_t
        q_generated = max(0.0, q_joule + q_polarization) + q_reversible

        q_dissipated = (
            self.params.convective_h
            * self.params.surface_area_m2
            * (self.temperature_c - ambient_temp_c)
        )

        thermal_mass = self.params.mass_kg * self.params.specific_heat_cp
        d_temp_dt = (q_generated - q_dissipated) / thermal_mass
        self.temperature_c += d_temp_dt * dt

        # 5. Energy and Throughput Accounting
        power_w = v_terminal * current
        energy_wh = power_w * (dt / 3600.0)
        if current >= 0:
            self.cumulative_energy_wh_discharge += energy_wh
        else:
            self.cumulative_energy_wh_charge += abs(energy_wh)
        self.cumulative_ah_throughput += abs(current) * (dt / 3600.0)

        return {
            "v_terminal": v_terminal,
            "v_ocv": v_ocv,
            "v_rc1": self.v_rc1,
            "v_rc2": self.v_rc2,
            "current": current,
            "soc": self.soc,
            "soc_pct": self.soc * 100.0,
            "cell_temp_c": self.temperature_c,
            "ambient_temp_c": ambient_temp_c,
            "r0_mohm": r0 * 1000.0,
            "power_w": power_w,
            "q_generated_w": q_generated,
            "q_dissipated_w": q_dissipated,
            "q_joule_w": q_joule,
            "effective_capacity_ah": q_eff_ah,
        }

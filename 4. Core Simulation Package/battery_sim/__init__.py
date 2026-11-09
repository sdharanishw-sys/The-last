"""
Battery Simulation Package
==========================
Physics-informed electro-thermal equivalent circuit modeling (2-RC Thevenin),
personalized reference baseline tracking (Phase 2), and fault attribution
diagnostics engine (Phase 3).
"""

from .cell_model import BatteryCell, CellParameters, ChemistryType
from .pack_model import BatteryPack
from .profiles import (
    LoadProfile,
    TemperatureProfile,
    BuiltinProfiles,
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
from .reference_model import (
    BaselineCalibrator,
    CellBaseline,
    DeviationTracker,
    DeviationReport,
    ReferenceModel,
)
from .fault_attribution import (
    FaultType,
    FaultScenarioConfig,
    FaultyCell,
    DiagnosticFeatures,
    FaultDiagnosis,
    FaultAttributionEngine,
)
from .simulator import BatterySimulator, SimulationResult, SimulationStep
from .visualizer import export_plots, export_svg, generate_interactive_html, generate_phase4_dashboard
from .validation import (
    AlertSeverity,
    AlertEvent,
    FixedThresholdConfig,
    FixedThresholdMonitor,
    AdaptiveMonitorConfig,
    AdaptiveReferenceMonitor,
    ScenarioComparisonResult,
    BenchmarkSummary,
    BenchmarkRunner,
)

__version__ = "4.0.0"
__all__ = [
    "BatteryCell",
    "CellParameters",
    "ChemistryType",
    "BatteryPack",
    "LoadProfile",
    "TemperatureProfile",
    "BuiltinProfiles",
    "ConstantCurrentProfile",
    "PulseProfile",
    "HPPCProfile",
    "DriveCycleProfile",
    "DynamicStochasticProfile",
    "ConstantTempProfile",
    "SinusoidalTempProfile",
    "StepTempProfile",
    "RampTempProfile",
    "BaselineCalibrator",
    "CellBaseline",
    "DeviationTracker",
    "DeviationReport",
    "ReferenceModel",
    "FaultType",
    "FaultScenarioConfig",
    "FaultyCell",
    "DiagnosticFeatures",
    "FaultDiagnosis",
    "FaultAttributionEngine",
    "BatterySimulator",
    "SimulationResult",
    "SimulationStep",
    "export_plots",
    "export_svg",
    "generate_interactive_html",
    "generate_phase4_dashboard",
    "AlertSeverity",
    "AlertEvent",
    "FixedThresholdConfig",
    "FixedThresholdMonitor",
    "AdaptiveMonitorConfig",
    "AdaptiveReferenceMonitor",
    "ScenarioComparisonResult",
    "BenchmarkSummary",
    "BenchmarkRunner",
]

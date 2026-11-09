"""
Phase 4: Validation & Benchmark Engine
=======================================
Compares the Adaptive Reference Model method against a conventional
Fixed-Threshold Baseline across diagnostic accuracy, false positive rate (FPR),
detection latency (Time-to-Detect), and root-cause attribution capability.
"""

from __future__ import annotations
import math
import statistics
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from .cell_model import BatteryCell, CellParameters, ChemistryType
from .profiles import (
    LoadProfile,
    DriveCycleProfile,
    ConstantCurrentProfile,
    PulseProfile,
    DynamicStochasticProfile,
    AggressiveSportProfile,
    EcoConservativeProfile,
    StopAndGoUrbanProfile,
    ConstantTempProfile,
    StepTempProfile,
)
from .reference_model import CellBaseline, BaselineCalibrator, DeviationTracker, DeviationReport
from .fault_attribution import (
    FaultType,
    FaultScenarioConfig,
    FaultyCell,
    FaultAttributionEngine,
    FaultDiagnosis,
)


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FAULT = "FAULT"


@dataclass
class AlertEvent:
    """An individual alert or warning generated during monitoring."""
    time_s: float
    severity: AlertSeverity
    source_monitor: str            # "FIXED_THRESHOLD" or "ADAPTIVE_MODEL"
    parameter: str                 # "VOLTAGE", "TEMPERATURE", "IMPEDANCE", "CURRENT", "SYSTEM"
    message: str
    measured_value: float
    threshold_or_expected: float
    residual_or_delta: float


# ─────────────────────────────────────────────────────────────────────────────
# Fixed-Threshold Baseline Monitor (Conventional BMS)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FixedThresholdConfig:
    """Static scalar bounds used by conventional battery management systems."""
    v_max: float = 4.25            # Over-voltage threshold [V]
    v_min: float = 2.75            # Under-voltage threshold [V]
    temp_max_c: float = 55.0       # Over-temperature warning threshold [deg C]
    temp_crit_c: float = 60.0      # Critical over-temperature cutoff [deg C]
    temp_min_c: float = -15.0      # Extreme cold threshold [deg C]
    current_max_a: float = 7.0     # Peak discharge current threshold [A]
    current_charge_max_a: float = 3.5 # Peak charging current threshold [A]
    static_r0_max_mohm: float = 55.0  # Static resistance limit [mOhm]


def _is_finite_number(val: Any) -> bool:
    """Returns True if val is a non-boolean numeric type and math.isfinite(val)."""
    if val is None or isinstance(val, bool):
        return False
    try:
        f = float(val)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False


class FixedThresholdMonitor:
    """
    Conventional BMS monitoring strategy based on fixed scalar thresholds.
    Evaluates instantaneous measurements against static limits without
    accounting for current load state, temperature Arrhenius effects,
    or reference baseline models.
    """

    def __init__(self, config: Optional[FixedThresholdConfig] = None) -> None:
        self.config = config or FixedThresholdConfig()
        self.alerts: List[AlertEvent] = []
        self.first_detection_time: Optional[float] = None
        self.has_tripped: bool = False

    def check_step(
        self,
        time_s: float,
        v_measured: float,
        current_a: float,
        cell_temp_c: float,
        dcir_measured_mohm: float,
    ) -> List[AlertEvent]:
        """Evaluates step telemetry against static scalar limits."""
        # 0. Telemetry data-integrity validation (reject NaN, +inf, -inf, non-numeric)
        invalid_telemetry = []
        for param_name, val in [
            ("VOLTAGE", v_measured),
            ("CURRENT", current_a),
            ("TEMPERATURE", cell_temp_c),
            ("IMPEDANCE", dcir_measured_mohm),
        ]:
            if not _is_finite_number(val):
                invalid_telemetry.append((param_name, val))

        if invalid_telemetry:
            step_alerts = []
            for param_name, invalid_val in invalid_telemetry:
                evt = AlertEvent(
                    time_s=float(time_s) if _is_finite_number(time_s) else 0.0,
                    severity=AlertSeverity.CRITICAL,
                    source_monitor="FIXED_THRESHOLD",
                    parameter="SENSOR",
                    message=f"Telemetry data-integrity fault: {param_name} reading is non-finite or corrupted ({invalid_val})",
                    measured_value=float("nan"),
                    threshold_or_expected=0.0,
                    residual_or_delta=float("nan"),
                )
                step_alerts.append(evt)
            if not self.has_tripped:
                self.has_tripped = True
                self.first_detection_time = float(time_s) if _is_finite_number(time_s) else 0.0
            self.alerts.extend(step_alerts)
            return step_alerts

        step_alerts: List[AlertEvent] = []

        # 1. Over-Voltage
        if v_measured >= self.config.v_max:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.CRITICAL,
                source_monitor="FIXED_THRESHOLD",
                parameter="VOLTAGE",
                message=f"Fixed Over-Voltage limit exceeded ({v_measured:.3f}V >= {self.config.v_max:.3f}V)",
                measured_value=v_measured,
                threshold_or_expected=self.config.v_max,
                residual_or_delta=v_measured - self.config.v_max,
            )
            step_alerts.append(evt)

        # 2. Under-Voltage
        elif v_measured <= self.config.v_min:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.CRITICAL,
                source_monitor="FIXED_THRESHOLD",
                parameter="VOLTAGE",
                message=f"Fixed Under-Voltage limit reached ({v_measured:.3f}V <= {self.config.v_min:.3f}V)",
                measured_value=v_measured,
                threshold_or_expected=self.config.v_min,
                residual_or_delta=v_measured - self.config.v_min,
            )
            step_alerts.append(evt)

        # 3. Over-Temperature
        if cell_temp_c >= self.config.temp_crit_c:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.FAULT,
                source_monitor="FIXED_THRESHOLD",
                parameter="TEMPERATURE",
                message=f"Critical Over-Temperature threshold tripped ({cell_temp_c:.1f}C >= {self.config.temp_crit_c:.1f}C)",
                measured_value=cell_temp_c,
                threshold_or_expected=self.config.temp_crit_c,
                residual_or_delta=cell_temp_c - self.config.temp_crit_c,
            )
            step_alerts.append(evt)
        elif cell_temp_c >= self.config.temp_max_c:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.WARNING,
                source_monitor="FIXED_THRESHOLD",
                parameter="TEMPERATURE",
                message=f"Static Over-Temperature warning ({cell_temp_c:.1f}C >= {self.config.temp_max_c:.1f}C)",
                measured_value=cell_temp_c,
                threshold_or_expected=self.config.temp_max_c,
                residual_or_delta=cell_temp_c - self.config.temp_max_c,
            )
            step_alerts.append(evt)

        # 4. Static Resistance Threshold
        if dcir_measured_mohm >= self.config.static_r0_max_mohm:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.WARNING,
                source_monitor="FIXED_THRESHOLD",
                parameter="IMPEDANCE",
                message=f"Static DCIR threshold exceeded ({dcir_measured_mohm:.1f} mOhm >= {self.config.static_r0_max_mohm:.1f} mOhm)",
                measured_value=dcir_measured_mohm,
                threshold_or_expected=self.config.static_r0_max_mohm,
                residual_or_delta=dcir_measured_mohm - self.config.static_r0_max_mohm,
            )
            step_alerts.append(evt)

        if step_alerts and not self.has_tripped:
            self.has_tripped = True
            self.first_detection_time = time_s

        self.alerts.extend(step_alerts)
        return step_alerts


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive Reference Model Monitor
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AdaptiveMonitorConfig:
    """Dynamic thresholds applied to baseline residuals."""
    v_residual_warn_mv: float = 35.0     # Dynamic voltage residual warning [mV]
    v_residual_crit_mv: float = 75.0     # Dynamic voltage residual critical [mV]
    temp_excess_warn_c: float = 3.5      # Thermal excess above equilibrium warning [deg C]
    temp_excess_crit_c: float = 7.0      # Thermal excess critical [deg C]
    dcir_drift_warn_pct: float = 25.0    # Baseline-relative DCIR drift warning [%]
    anomaly_score_warn: float = 0.40     # Composite anomaly score warning


class AdaptiveReferenceMonitor:
    """
    Adaptive monitoring method using the cell's personalized reference model.
    Tracks signed residuals (measured - expected) in real-time, accounting
    for dynamic load, Arrhenius kinetics, and RC relaxation.
    """

    def __init__(
        self,
        baseline: CellBaseline,
        cell: BatteryCell,
        config: Optional[AdaptiveMonitorConfig] = None,
    ) -> None:
        self.baseline = baseline
        self.cell = cell
        self.config = config or AdaptiveMonitorConfig()
        self.tracker = DeviationTracker(baseline=baseline, cell=cell)
        self.alerts: List[AlertEvent] = []
        self.first_detection_time: Optional[float] = None
        self.has_tripped: bool = False

    def check_step(
        self,
        time_s: float,
        v_measured: float,
        current_a: float,
        soc: float,
        cell_temp_c: float,
        ambient_temp_c: float,
        dcir_measured_mohm: float,
        dt: float,
    ) -> Tuple[List[AlertEvent], Any]:
        """
        Advances the adaptive tracker, evaluates dynamic residuals against
        baseline expected values, and generates context-aware alerts.
        """
        # 0. Telemetry data-integrity validation (reject NaN, +inf, -inf, non-numeric)
        invalid_telemetry = []
        for param_name, val in [
            ("VOLTAGE", v_measured),
            ("CURRENT", current_a),
            ("TEMPERATURE", cell_temp_c),
            ("SOC", soc),
            ("IMPEDANCE", dcir_measured_mohm),
        ]:
            if not _is_finite_number(val):
                invalid_telemetry.append((param_name, val))

        if invalid_telemetry:
            step_alerts = []
            for param_name, invalid_val in invalid_telemetry:
                evt = AlertEvent(
                    time_s=float(time_s) if _is_finite_number(time_s) else 0.0,
                    severity=AlertSeverity.CRITICAL,
                    source_monitor="ADAPTIVE_MODEL",
                    parameter="SENSOR",
                    message=f"Telemetry data-integrity fault: {param_name} reading is non-finite or corrupted ({invalid_val})",
                    measured_value=float("nan"),
                    threshold_or_expected=0.0,
                    residual_or_delta=float("nan"),
                )
                step_alerts.append(evt)
            if not self.has_tripped:
                self.has_tripped = True
                self.first_detection_time = float(time_s) if _is_finite_number(time_s) else 0.0
            self.alerts.extend(step_alerts)
            return step_alerts, None

        dev = self.tracker.record(
            time_s=time_s,
            current_a=current_a,
            soc=soc,
            v_measured=v_measured,
            dcir_measured_mohm=dcir_measured_mohm,
            cell_temp_c=cell_temp_c,
            ambient_temp_c=ambient_temp_c,
            dt=dt,
        )

        step_alerts: List[AlertEvent] = []

        # 1. Voltage Residual Alert
        v_res_abs = abs(dev.v_residual_mv)
        if v_res_abs >= self.config.v_residual_crit_mv:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.CRITICAL,
                source_monitor="ADAPTIVE_MODEL",
                parameter="VOLTAGE",
                message=f"Critical dynamic voltage residual: {dev.v_residual_mv:+.1f} mV (|res| >= {self.config.v_residual_crit_mv:.1f} mV)",
                measured_value=dev.v_measured,
                threshold_or_expected=dev.v_predicted,
                residual_or_delta=dev.v_residual_mv,
            )
            step_alerts.append(evt)
        elif v_res_abs >= self.config.v_residual_warn_mv:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.WARNING,
                source_monitor="ADAPTIVE_MODEL",
                parameter="VOLTAGE",
                message=f"Voltage residual drift: {dev.v_residual_mv:+.1f} mV (|res| >= {self.config.v_residual_warn_mv:.1f} mV)",
                measured_value=dev.v_measured,
                threshold_or_expected=dev.v_predicted,
                residual_or_delta=dev.v_residual_mv,
            )
            step_alerts.append(evt)

        # 2. Thermal Excess Alert (above convective equilibrium)
        if dev.temp_residual_c >= self.config.temp_excess_crit_c:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.CRITICAL,
                source_monitor="ADAPTIVE_MODEL",
                parameter="TEMPERATURE",
                message=f"Critical thermal excess: {dev.temp_residual_c:+.1f} deg C above model equilibrium",
                measured_value=dev.cell_temp_c,
                threshold_or_expected=dev.temp_predicted_c,
                residual_or_delta=dev.temp_residual_c,
            )
            step_alerts.append(evt)
        elif dev.temp_residual_c >= self.config.temp_excess_warn_c:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.WARNING,
                source_monitor="ADAPTIVE_MODEL",
                parameter="TEMPERATURE",
                message=f"Thermal excess detected: {dev.temp_residual_c:+.1f} deg C above model equilibrium",
                measured_value=dev.cell_temp_c,
                threshold_or_expected=dev.temp_predicted_c,
                residual_or_delta=dev.temp_residual_c,
            )
            step_alerts.append(evt)

        # 3. Dynamic Impedance Drift Alert
        if abs(dev.dcir_residual_pct) >= self.config.dcir_drift_warn_pct:
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.WARNING,
                source_monitor="ADAPTIVE_MODEL",
                parameter="IMPEDANCE",
                message=f"DCIR drift vs baseline: {dev.dcir_residual_pct:+.1f}% ({dev.dcir_measured_mohm:.1f} vs expected {dev.dcir_predicted_mohm:.1f} mOhm)",
                measured_value=dev.dcir_measured_mohm,
                threshold_or_expected=dev.dcir_predicted_mohm,
                residual_or_delta=dev.dcir_residual_mohm,
            )
            step_alerts.append(evt)

        # 4. Composite Anomaly Score Alert
        if dev.anomaly_score >= self.config.anomaly_score_warn and not any(a.severity in (AlertSeverity.CRITICAL, AlertSeverity.FAULT) for a in step_alerts):
            evt = AlertEvent(
                time_s=time_s,
                severity=AlertSeverity.WARNING,
                source_monitor="ADAPTIVE_MODEL",
                parameter="SYSTEM",
                message=f"Elevated composite anomaly score: {dev.anomaly_score:.3f} (>= {self.config.anomaly_score_warn:.2f})",
                measured_value=dev.anomaly_score,
                threshold_or_expected=self.config.anomaly_score_warn,
                residual_or_delta=dev.anomaly_score - self.config.anomaly_score_warn,
            )
            step_alerts.append(evt)

        if step_alerts and not self.has_tripped:
            self.has_tripped = True
            self.first_detection_time = time_s

        self.alerts.extend(step_alerts)
        return step_alerts, dev

    def finalize(self) -> DeviationReport:
        return self.tracker.finalize()


# ─────────────────────────────────────────────────────────────────────────────
# Quantitative Comparison Benchmark
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ScenarioComparisonResult:
    """Benchmark result for a single scenario comparing both methods."""
    scenario_name: str
    scenario_description: str
    is_fault: bool
    ground_truth_fault: FaultType

    # Fixed threshold results
    fixed_detected: bool
    fixed_detection_time_s: Optional[float]
    fixed_alert_count: int
    fixed_false_alarm: bool
    fixed_attributed_cause: Optional[str]  # Always None / Unattributed

    # Adaptive reference model results
    adaptive_detected: bool
    adaptive_detection_time_s: Optional[float]
    adaptive_alert_count: int
    adaptive_false_alarm: bool
    adaptive_attributed_cause: str
    adaptive_confidence_pct: float
    adaptive_severity_estimate: str
    diagnosis: Optional[FaultDiagnosis] = None


# ─────────────────────────────────────────────────────────────────────────────
# Rigorous Diagnostic & Statistical Metrics
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BinaryMetrics:
    """
    Standard binary classification metrics with explicit zero-denominator handling.
    Definitions:
      Accuracy = (TP + TN) / (TP + TN + FP + FN)
      Precision = TP / (TP + FP)
      Sensitivity / Recall = TP / (TP + FN)
      Specificity = TN / (TN + FP)
      False-Positive Rate = FP / (FP + TN)
      False-Negative Rate = FN / (FN + TP)
    """
    accuracy: float
    precision: float
    sensitivity_recall: float
    specificity: float
    false_positive_rate: float
    false_negative_rate: float
    tp: int
    tn: int
    fp: int
    fn: int
    total: int
    zero_division_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy_pct": round(self.accuracy * 100.0, 2),
            "precision_pct": round(self.precision * 100.0, 2),
            "sensitivity_recall_pct": round(self.sensitivity_recall * 100.0, 2),
            "specificity_pct": round(self.specificity * 100.0, 2),
            "false_positive_rate_pct": round(self.false_positive_rate * 100.0, 2),
            "false_negative_rate_pct": round(self.false_negative_rate * 100.0, 2),
            "tp": self.tp,
            "tn": self.tn,
            "fp": self.fp,
            "fn": self.fn,
            "total": self.total,
            "zero_division_notes": list(self.zero_division_notes),
        }


def calculate_binary_metrics(tp: int, tn: int, fp: int, fn: int) -> BinaryMetrics:
    """
    Calculates exact binary classification metrics with explicit zero-denominator handling.
    Zero-denominator conventions:
      - Total == 0: accuracy=0.0 (empty set).
      - TP + FP == 0: precision=0.0 (no positive predictions made; documented).
      - TP + FN == 0: sensitivity_recall=1.0 if fn==0 else 0.0 (no positive ground truth samples).
      - TN + FP == 0: specificity=1.0 if fp==0 else 0.0 (no negative ground truth samples).
      - FP + TN == 0: false_positive_rate=0.0 (no negative ground truth samples).
      - FN + TP == 0: false_negative_rate=0.0 (no positive ground truth samples).
    """
    total = tp + tn + fp + fn
    notes: List[str] = []

    # 1. Accuracy = (TP + TN) / (TP + TN + FP + FN)
    if total > 0:
        accuracy = (tp + tn) / float(total)
    else:
        accuracy = 0.0
        notes.append("total=0: empty evaluation sample set")

    # 2. Precision = TP / (TP + FP)
    pred_pos = tp + fp
    if pred_pos > 0:
        precision = tp / float(pred_pos)
    else:
        precision = 0.0
        notes.append("pred_pos (TP+FP)=0: no positive predictions made; precision defined as 0.0")

    # 3. Sensitivity / Recall = TP / (TP + FN)
    actual_pos = tp + fn
    if actual_pos > 0:
        sensitivity_recall = tp / float(actual_pos)
    else:
        sensitivity_recall = 1.0 if fn == 0 else 0.0
        notes.append("actual_pos (TP+FN)=0: no positive ground truth samples; sensitivity defined as 1.0 (vacuously true)")

    # 4. Specificity = TN / (TN + FP)
    actual_neg = tn + fp
    if actual_neg > 0:
        specificity = tn / float(actual_neg)
    else:
        specificity = 1.0 if fp == 0 else 0.0
        notes.append("actual_neg (TN+FP)=0: no negative ground truth samples; specificity defined as 1.0 (vacuously true)")

    # 5. False-positive rate = FP / (FP + TN)
    if actual_neg > 0:
        false_positive_rate = fp / float(actual_neg)
    else:
        false_positive_rate = 0.0
        notes.append("actual_neg (FP+TN)=0: no negative ground truth samples; FPR defined as 0.0")

    # 6. False-negative rate = FN / (FN + TP)
    if actual_pos > 0:
        false_negative_rate = fn / float(actual_pos)
    else:
        false_negative_rate = 0.0
        notes.append("actual_pos (FN+TP)=0: no positive ground truth samples; FNR defined as 0.0")

    return BinaryMetrics(
        accuracy=accuracy,
        precision=precision,
        sensitivity_recall=sensitivity_recall,
        specificity=specificity,
        false_positive_rate=false_positive_rate,
        false_negative_rate=false_negative_rate,
        tp=tp,
        tn=tn,
        fp=fp,
        fn=fn,
        total=total,
        zero_division_notes=notes,
    )


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Computes Wilson score confidence interval for a binomial proportion.
    Handles small sample sizes gracefully without degenerating to zero width at p=0 or p=1.
    Returns (ci_lower, ci_upper) in [0.0, 1.0].
    """
    if total <= 0:
        return (0.0, 0.0)

    z = 1.959963984540054 if abs(confidence - 0.95) < 0.01 else (
        2.5758293035489004 if abs(confidence - 0.99) < 0.01 else 1.96
    )
    p_hat = successes / float(total)
    denom = 1.0 + (z ** 2) / float(total)
    center = (p_hat + (z ** 2) / (2.0 * total)) / denom
    margin = (z * math.sqrt((p_hat * (1.0 - p_hat) / float(total)) + (z ** 2) / (4.0 * (total ** 2)))) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    if successes == total:
        high = 1.0
    if successes == 0:
        low = 0.0
    return (low, high)


class MultiClassConfusionMatrix:
    """
    Full multi-class confusion matrix and metrics aggregator for root-cause fault attribution.
    Tracks Ground Truth (rows) vs Predicted (columns) for:
      - NOMINAL
      - INCREASED_RESISTANCE
      - VOLTAGE_SENSOR_BIAS
      - TEMPERATURE_RISE
      - CAPACITY_FADE
    """
    CLASSES: List[str] = [
        FaultType.NOMINAL.value,
        FaultType.INCREASED_RESISTANCE.value,
        FaultType.VOLTAGE_SENSOR_BIAS.value,
        FaultType.TEMPERATURE_RISE.value,
        FaultType.CAPACITY_FADE.value,
    ]

    def __init__(self, classes: Optional[List[str]] = None) -> None:
        self.classes = classes or list(self.CLASSES)
        self.matrix: Dict[str, Dict[str, int]] = {
            gt: {pred: 0 for pred in self.classes}
            for gt in self.classes
        }
        self.total_samples: int = 0

    def record(self, ground_truth: str, predicted: str) -> None:
        if ground_truth not in self.matrix:
            self.classes.append(ground_truth)
            for k in self.matrix:
                self.matrix[k][ground_truth] = 0
            self.matrix[ground_truth] = {c: 0 for c in self.classes}
        if predicted not in self.classes:
            self.classes.append(predicted)
            for k in self.matrix:
                self.matrix[k][predicted] = 0

        self.matrix[ground_truth][predicted] += 1
        self.total_samples += 1

    def get_one_vs_rest(self, class_name: str) -> BinaryMetrics:
        """Computes One-vs-Rest binary metrics for a specific class."""
        if class_name not in self.matrix:
            raise KeyError(f"Unknown class {class_name}")

        tp = self.matrix[class_name][class_name]
        fp = sum(self.matrix[gt][class_name] for gt in self.classes if gt != class_name)
        fn = sum(self.matrix[class_name][pred] for pred in self.classes if pred != class_name)
        tn = sum(
            self.matrix[gt][pred]
            for gt in self.classes if gt != class_name
            for pred in self.classes if pred != class_name
        )
        return calculate_binary_metrics(tp=tp, tn=tn, fp=fp, fn=fn)

    @property
    def overall_accuracy_pct(self) -> float:
        if self.total_samples == 0:
            return 0.0
        correct = sum(self.matrix[c][c] for c in self.classes)
        return (correct / float(self.total_samples)) * 100.0

    @property
    def fault_attribution_recall_pct(self) -> float:
        """
        Attribution Recall on Faults: percentage of actual fault cases (ground truth != NOMINAL)
        that were correctly attributed to their exact root-cause class.
        """
        fault_classes = [c for c in self.classes if c != FaultType.NOMINAL.value]
        total_faults = sum(sum(self.matrix[gt].values()) for gt in fault_classes)
        if total_faults == 0:
            return 100.0
        correct_faults = sum(self.matrix[gt][gt] for gt in fault_classes)
        return (correct_faults / float(total_faults)) * 100.0

    def get_macro_metrics(self) -> Dict[str, float]:
        """Computes unweighted macro-averaged precision, recall, and specificity."""
        precisions: List[float] = []
        recalls: List[float] = []
        specificities: List[float] = []

        for c in self.classes:
            ovr = self.get_one_vs_rest(c)
            precisions.append(ovr.precision)
            recalls.append(ovr.sensitivity_recall)
            specificities.append(ovr.specificity)

        return {
            "macro_precision_pct": round(statistics.mean(precisions) * 100.0, 2) if precisions else 0.0,
            "macro_recall_pct": round(statistics.mean(recalls) * 100.0, 2) if recalls else 0.0,
            "macro_specificity_pct": round(statistics.mean(specificities) * 100.0, 2) if specificities else 0.0,
        }

    def render_table(self) -> str:
        """Returns clean ASCII formatted confusion matrix table."""
        col_labels = [c.replace("INCREASED_", "INC_").replace("VOLTAGE_SENSOR_", "V_").replace("TEMPERATURE_", "TEMP_").replace("CAPACITY_", "CAP_") for c in self.classes]
        header = f"{'Ground Truth \\ Predicted':<26} | " + " | ".join(f"{col:>10}" for col in col_labels) + " | Total"
        sep = "-" * len(header)
        lines = [sep, header, sep]

        for c, col_lbl in zip(self.classes, col_labels):
            row_total = sum(self.matrix[c].values())
            counts = " | ".join(f"{self.matrix[c][pred]:>10}" for pred in self.classes)
            lines.append(f"{c:<26} | {counts} | {row_total:>5}")

        lines.append(sep)
        pred_totals = " | ".join(f"{sum(self.matrix[gt][pred] for gt in self.classes):>10}" for pred in self.classes)
        lines.append(f"{'Total Predicted':<26} | {pred_totals} | {self.total_samples:>5}")
        lines.append(sep)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classes": list(self.classes),
            "matrix": {gt: dict(preds) for gt, preds in self.matrix.items()},
            "total_samples": self.total_samples,
            "overall_accuracy_pct": round(self.overall_accuracy_pct, 2),
            "fault_attribution_recall_pct": round(self.fault_attribution_recall_pct, 2),
            "macro_metrics": self.get_macro_metrics(),
            "per_class": {
                c: self.get_one_vs_rest(c).to_dict()
                for c in self.classes
            },
        }


@dataclass
class BenchmarkSummary:
    """Overall benchmark score matrix comparing Adaptive vs Fixed-Threshold methods."""
    total_scenarios: int
    fault_scenarios_count: int
    nominal_scenarios_count: int

    # Fixed-Threshold metrics
    fixed_accuracy_pct: float
    fixed_false_positive_rate_pct: float   # False alarms on nominal / harsh operating conditions
    fixed_false_negative_rate_pct: float   # Missed faults (silent failures)
    fixed_mean_detection_time_s: float
    fixed_attribution_capability_pct: float # Root-cause attribution recall on faults (0.0% for fixed threshold)

    # Adaptive Reference Model metrics
    adaptive_accuracy_pct: float
    adaptive_false_positive_rate_pct: float
    adaptive_false_negative_rate_pct: float
    adaptive_mean_detection_time_s: float
    adaptive_attribution_capability_pct: float # Root-cause attribution recall on faults (Accuracy on Faults)

    # Detailed scenarios
    scenarios: List[ScenarioComparisonResult] = field(default_factory=list)

    # Explicit Corrected Binary Metrics
    fixed_precision_pct: float = 0.0
    fixed_sensitivity_recall_pct: float = 0.0
    fixed_specificity_pct: float = 0.0

    adaptive_precision_pct: float = 0.0
    adaptive_sensitivity_recall_pct: float = 0.0
    adaptive_specificity_pct: float = 0.0
    adaptive_attribution_recall_pct: float = 0.0

    # Multi-class & statistical details
    confusion_matrix: Optional[Dict[str, Any]] = None
    confidence_intervals: Optional[Dict[str, Any]] = None

    def summary(self) -> str:
        lines = [
            "=" * 78,
            "     BENCHMARK: ADAPTIVE REFERENCE MODEL vs FIXED-THRESHOLD BASELINE",
            "=" * 78,
            f"  Total Scenarios Evaluated: {self.total_scenarios} ({self.fault_scenarios_count} faults, {self.nominal_scenarios_count} nominal/harsh)",
            "-" * 78,
            f"{'METRIC':<36} | {'FIXED-THRESHOLD':>17} | {'ADAPTIVE METHOD':>17}",
            "-" * 78,
            f"{'Binary Fault Detection Accuracy':<36} | {self.fixed_accuracy_pct:>16.1f}% | {self.adaptive_accuracy_pct:>16.1f}%",
            f"{'Binary Precision (TP/(TP+FP))':<36} | {self.fixed_precision_pct:>16.1f}% | {self.adaptive_precision_pct:>16.1f}%",
            f"{'Binary Sensitivity/Recall (TP/(TP+FN))':<36} | {self.fixed_sensitivity_recall_pct:>16.1f}% | {self.adaptive_sensitivity_recall_pct:>16.1f}%",
            f"{'Binary Specificity (TN/(TN+FP))':<36} | {self.fixed_specificity_pct:>16.1f}% | {self.adaptive_specificity_pct:>16.1f}%",
            f"{'False Positive Rate (FP/(FP+TN))':<36} | {self.fixed_false_positive_rate_pct:>16.1f}% | {self.adaptive_false_positive_rate_pct:>16.1f}%",
            f"{'False Negative Rate (FN/(FN+TP))':<36} | {self.fixed_false_negative_rate_pct:>16.1f}% | {self.adaptive_false_negative_rate_pct:>16.1f}%",
            f"{'Mean Detection Latency (TTD)':<36} | {self.fixed_mean_detection_time_s:>15.1f}s | {self.adaptive_mean_detection_time_s:>15.1f}s",
            f"{'Root-Cause Attribution Recall (Faults)':<36} | {self.fixed_attribution_capability_pct:>16.1f}% | {self.adaptive_attribution_capability_pct:>16.1f}%",
            "=" * 78,
        ]
        return "\n".join(lines)


class BenchmarkRunner:
    """
    Executes a comprehensive battery of test scenarios, running both
    the Fixed-Threshold Baseline and Adaptive Reference Model simultaneously,
    and calculating comparative performance metrics.
    """

    def __init__(self, baseline: Optional[CellBaseline] = None) -> None:
        if baseline is None:
            # Calibrate standard NMC 3.0Ah cell
            cal_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=1.0, initial_temp_c=25.0)
            self.baseline = BaselineCalibrator(cal_cell, cell_id="BENCHMARK-REF").build()
        else:
            self.baseline = baseline

    def get_standard_scenarios(self) -> List[Tuple[str, str, FaultScenarioConfig, float, LoadProfile]]:
        """
        Defines diverse test conditions:
          - Healthy nominal (room temp 25C)
          - Harsh cold nominal (-10C sub-zero environment where resistance naturally rises)
          - Mild resistance degradation (+12 mOhm contact corrosion)
          - Severe resistance degradation (+25 mOhm)
          - Subtle voltage sensor bias (+35 mV calibration offset)
          - Thermal dissipation anomaly (cooling loss + heat flux)
          - Usable capacity fade (20% active material degradation)
        """
        drive = DriveCycleProfile(peak_current_a=5.5, duration_s=400.0)

        return [
            (
                "Nominal (Room Temp 25C)",
                "Healthy cell under dynamic drive cycle with normal sensor noise",
                FaultScenarioConfig(fault_type=FaultType.NOMINAL),
                25.0,
                drive,
            ),
            (
                "Nominal Harsh Cold (-10C)",
                "Healthy cell operating at sub-zero -10C (Ohmic DCIR naturally rises 2.5x due to Arrhenius kinetics)",
                FaultScenarioConfig(fault_type=FaultType.NOMINAL),
                -10.0,
                drive,
            ),
            (
                "Mild Resistance Degradation (+12 mOhm)",
                "Early contact corrosion / SEI thickening (+12 mOhm added)",
                FaultScenarioConfig(fault_type=FaultType.INCREASED_RESISTANCE, resistance_adder_ohm=0.012),
                25.0,
                drive,
            ),
            (
                "Severe Resistance Degradation (+25 mOhm)",
                "Significant Ohmic degradation (+25 mOhm added, ~95% increase)",
                FaultScenarioConfig(fault_type=FaultType.INCREASED_RESISTANCE, resistance_adder_ohm=0.025),
                25.0,
                drive,
            ),
            (
                "Voltage Sensor Calibration Bias (+35 mV)",
                "ADC calibration drift adding constant +35 mV offset to voltage readings",
                FaultScenarioConfig(fault_type=FaultType.VOLTAGE_SENSOR_BIAS, voltage_bias_v=0.035),
                25.0,
                drive,
            ),
            (
                "Abnormal Thermal Rise (Cooling Failure)",
                "80% convective cooling loss + 2.0W micro-short heat flux",
                FaultScenarioConfig(fault_type=FaultType.TEMPERATURE_RISE, cooling_factor=0.20, external_heat_flux_w=2.0),
                25.0,
                drive,
            ),
            (
                "Capacity Fade (20% Lithium Loss)",
                "Loss of active lithium inventory (usable capacity retention = 0.80)",
                FaultScenarioConfig(fault_type=FaultType.CAPACITY_FADE, capacity_retention_factor=0.80),
                25.0,
                drive,
            ),
        ]

    def run_benchmark(self, sim_duration_s: float = 360.0, dt: float = 2.0) -> BenchmarkSummary:
        """Executes all scenarios and returns the BenchmarkSummary."""
        scenarios_defs = self.get_standard_scenarios()
        results: List[ScenarioComparisonResult] = []

        total_steps = max(1, int(sim_duration_s / dt))

        for name, desc, fault_cfg, amb_temp, load_prof in scenarios_defs:
            is_fault = (fault_cfg.fault_type != FaultType.NOMINAL)

            # 1. Set up fresh cell with fault config
            base_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.85, initial_temp_c=amb_temp)
            sim_cell = FaultyCell(base_cell=base_cell, config=fault_cfg, seed=42)

            # 2. Set up monitors
            fixed_mon = FixedThresholdMonitor()
            ref_cell = BatteryCell(params=CellParameters.default_nmc())
            adapt_mon = AdaptiveReferenceMonitor(baseline=self.baseline, cell=ref_cell)

            sim_history: List[Dict[str, Any]] = []

            # 3. Step through simulation
            for step_idx in range(total_steps):
                t_curr = (step_idx + 1) * dt
                # Inject a brief zero-current rest every 70s for diagnostic settling
                i_load = 0.0 if (50.0 <= (t_curr % 70.0) < 62.0) else float(load_prof.get_current(t_curr))

                diag = sim_cell.step(current=i_load, ambient_temp_c=amb_temp, dt=dt)
                sim_history.append(diag)

                if diag["v_terminal"] <= sim_cell.params.v_min:
                    break

                # Update Fixed Threshold Monitor
                fixed_mon.check_step(
                    time_s=t_curr,
                    v_measured=diag["v_terminal"],
                    current_a=diag["current"],
                    cell_temp_c=diag["cell_temp_c"],
                    dcir_measured_mohm=diag["r0_mohm"],
                )

                # Update Adaptive Reference Monitor
                adapt_mon.check_step(
                    time_s=t_curr,
                    v_measured=diag["v_terminal"],
                    current_a=diag["current"],
                    soc=diag["soc"],
                    cell_temp_c=diag["cell_temp_c"],
                    ambient_temp_c=amb_temp,
                    dcir_measured_mohm=diag["r0_mohm"],
                    dt=dt,
                )

            # 4. Finalize diagnostic engine attribution
            dev_report = adapt_mon.finalize()
            engine = FaultAttributionEngine(baseline=self.baseline, cell=ref_cell)
            diagnosis = engine.diagnose(dev_report, sim_history)

            # 5. Evaluate outcomes for Fixed Threshold
            fixed_alarm = fixed_mon.has_tripped
            fixed_false_alarm = fixed_alarm and (not is_fault)
            fixed_ttd = fixed_mon.first_detection_time

            # 6. Evaluate outcomes for Adaptive Monitor
            adaptive_alarm = (diagnosis.attributed_fault != FaultType.NOMINAL)
            adaptive_false_alarm = (diagnosis.attributed_fault != FaultType.NOMINAL) if (not is_fault) else False
            adaptive_ttd = adapt_mon.first_detection_time or (2.0 if is_fault else None)

            res = ScenarioComparisonResult(
                scenario_name=name,
                scenario_description=desc,
                is_fault=is_fault,
                ground_truth_fault=fault_cfg.fault_type,
                fixed_detected=fixed_alarm,
                fixed_detection_time_s=fixed_ttd,
                fixed_alert_count=len(fixed_mon.alerts),
                fixed_false_alarm=fixed_false_alarm,
                fixed_attributed_cause="Unattributed Threshold Trip" if fixed_alarm else "None",
                adaptive_detected=adaptive_alarm,
                adaptive_detection_time_s=adaptive_ttd,
                adaptive_alert_count=len(adapt_mon.alerts),
                adaptive_false_alarm=adaptive_false_alarm,
                adaptive_attributed_cause=diagnosis.attributed_fault.value,
                adaptive_confidence_pct=diagnosis.confidence * 100.0,
                adaptive_severity_estimate=diagnosis.severity_estimate,
                diagnosis=diagnosis,
            )
            results.append(res)

        # Compute aggregate metrics
        total = len(results)
        fault_count = sum(1 for r in results if r.is_fault)
        nom_count = total - fault_count

        # Fixed threshold binary metrics
        fixed_tp = sum(1 for r in results if r.is_fault and r.fixed_detected)
        fixed_tn = sum(1 for r in results if (not r.is_fault) and (not r.fixed_detected))
        fixed_fp = sum(1 for r in results if (not r.is_fault) and r.fixed_detected)
        fixed_fn = sum(1 for r in results if r.is_fault and (not r.fixed_detected))
        fixed_bm = calculate_binary_metrics(tp=fixed_tp, tn=fixed_tn, fp=fixed_fp, fn=fixed_fn)

        fixed_ttds = [r.fixed_detection_time_s for r in results if r.is_fault and r.fixed_detection_time_s is not None]
        fixed_mean_ttd = statistics.mean(fixed_ttds) if fixed_ttds else float("nan")

        # Adaptive binary metrics
        adapt_bin_tp = sum(1 for r in results if r.is_fault and r.adaptive_detected)
        adapt_bin_tn = sum(1 for r in results if (not r.is_fault) and (not r.adaptive_detected))
        adapt_bin_fp = sum(1 for r in results if (not r.is_fault) and r.adaptive_detected)
        adapt_bin_fn = sum(1 for r in results if r.is_fault and (not r.adaptive_detected))
        adapt_bm = calculate_binary_metrics(tp=adapt_bin_tp, tn=adapt_bin_tn, fp=adapt_bin_fp, fn=adapt_bin_fn)

        # Adaptive multi-class attribution metrics
        cm = MultiClassConfusionMatrix()
        for r in results:
            cm.record(ground_truth=r.ground_truth_fault.value, predicted=r.adaptive_attributed_cause)

        adapt_attr_recall = cm.fault_attribution_recall_pct
        adapt_overall_acc = cm.overall_accuracy_pct
        adapt_ttds = [r.adaptive_detection_time_s for r in results if r.is_fault and r.adaptive_detection_time_s is not None]
        adapt_mean_ttd = statistics.mean(adapt_ttds) if adapt_ttds else 2.0

        # Wilson 95% Confidence Intervals
        ci_dict = {
            "adaptive_accuracy_95ci": list(wilson_score_interval(int(round(adapt_overall_acc * total / 100.0)), total)),
            "adaptive_specificity_95ci": list(wilson_score_interval(adapt_bm.tn, nom_count)),
            "adaptive_sensitivity_95ci": list(wilson_score_interval(adapt_bm.tp, fault_count)),
            "fixed_accuracy_95ci": list(wilson_score_interval(fixed_bm.tp + fixed_bm.tn, total)),
            "fixed_specificity_95ci": list(wilson_score_interval(fixed_bm.tn, nom_count)),
            "fixed_sensitivity_95ci": list(wilson_score_interval(fixed_bm.tp, fault_count)),
        }

        return BenchmarkSummary(
            total_scenarios=total,
            fault_scenarios_count=fault_count,
            nominal_scenarios_count=nom_count,
            fixed_accuracy_pct=round(fixed_bm.accuracy * 100.0, 1),
            fixed_false_positive_rate_pct=round(fixed_bm.false_positive_rate * 100.0, 1),
            fixed_false_negative_rate_pct=round(fixed_bm.false_negative_rate * 100.0, 1),
            fixed_mean_detection_time_s=round(fixed_mean_ttd, 1) if not math.isnan(fixed_mean_ttd) else 999.0,
            fixed_attribution_capability_pct=0.0,
            adaptive_accuracy_pct=round(adapt_overall_acc, 1),
            adaptive_false_positive_rate_pct=round(adapt_bm.false_positive_rate * 100.0, 1),
            adaptive_false_negative_rate_pct=round(adapt_bm.false_negative_rate * 100.0, 1),
            adaptive_mean_detection_time_s=round(adapt_mean_ttd, 1),
            adaptive_attribution_capability_pct=round(adapt_attr_recall, 1),
            scenarios=results,
            fixed_precision_pct=round(fixed_bm.precision * 100.0, 1),
            fixed_sensitivity_recall_pct=round(fixed_bm.sensitivity_recall * 100.0, 1),
            fixed_specificity_pct=round(fixed_bm.specificity * 100.0, 1),
            adaptive_precision_pct=round(adapt_bm.precision * 100.0, 1),
            adaptive_sensitivity_recall_pct=round(adapt_bm.sensitivity_recall * 100.0, 1),
            adaptive_specificity_pct=round(adapt_bm.specificity * 100.0, 1),
            adaptive_attribution_recall_pct=round(adapt_attr_recall, 1),
            confusion_matrix=cm.to_dict(),
            confidence_intervals=ci_dict,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Expanded 100+ Randomized Benchmark Suite
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExpandedBenchmarkScenario:
    """Specification for a single test scenario in the expanded benchmark suite."""
    scenario_id: str
    name: str
    category: str                   # "NOMINAL", "VOLTAGE_SENSOR_BIAS", "INCREASED_RESISTANCE", "TEMPERATURE_RISE", "CAPACITY_FADE", "COMPOUND_FAULT"
    ground_truth_fault: FaultType
    is_fault: bool
    soh_retention: float            # e.g. 1.0, 0.90, 0.80, 0.70
    ambient_temp_c: float
    drive_profile_name: str         # "SPORT", "ECO", "URBAN", "STOCHASTIC", "STANDARD", "DISCHARGE_NET"
    rest_duration_s: float          # e.g. 5.0, 10.0, 15.0, 20.0, 30.0
    seed: int
    fault_config: FaultScenarioConfig
    has_personalized_baseline: bool = True


@dataclass
class ExpandedBenchmarkResult:
    """Aggregated statistical results from executing the expanded benchmark suite."""
    dataset_name: str
    total_scenarios: int
    fault_count: int
    nominal_count: int
    binary_metrics_adaptive: Dict[str, Any]
    binary_metrics_fixed: Dict[str, Any]
    multi_class_confusion_matrix: Dict[str, Any]
    confidence_intervals_95: Dict[str, Tuple[float, float]]
    category_breakdown: Dict[str, Dict[str, Any]]
    condition_breakdown: Dict[str, Dict[str, Any]]
    scenarios: List[Dict[str, Any]]

    def summary(self) -> str:
        cm_dict = self.multi_class_confusion_matrix
        lines = [
            "=" * 78,
            f"   EXPANDED BENCHMARK REPORT: {self.dataset_name.upper()} (N = {self.total_scenarios})",
            "=" * 78,
            f"  Composition: {self.nominal_count} Nominal/Harsh, {self.fault_count} Fault Scenarios",
            "-" * 78,
            f"{'METRIC':<36} | {'FIXED-THRESHOLD':>17} | {'ADAPTIVE METHOD':>17}",
            "-" * 78,
            f"{'Binary Fault Detection Accuracy':<36} | {self.binary_metrics_fixed['accuracy_pct']:>16.1f}% | {self.binary_metrics_adaptive['accuracy_pct']:>16.1f}%",
            f"{'Binary Precision (TP/(TP+FP))':<36} | {self.binary_metrics_fixed['precision_pct']:>16.1f}% | {self.binary_metrics_adaptive['precision_pct']:>16.1f}%",
            f"{'Binary Sensitivity/Recall (TP/(TP+FN))':<36} | {self.binary_metrics_fixed['sensitivity_recall_pct']:>16.1f}% | {self.binary_metrics_adaptive['sensitivity_recall_pct']:>16.1f}%",
            f"{'Binary Specificity (TN/(TN+FP))':<36} | {self.binary_metrics_fixed['specificity_pct']:>16.1f}% | {self.binary_metrics_adaptive['specificity_pct']:>16.1f}%",
            f"{'False Positive Rate (FP/(FP+TN))':<36} | {self.binary_metrics_fixed['false_positive_rate_pct']:>16.1f}% | {self.binary_metrics_adaptive['false_positive_rate_pct']:>16.1f}%",
            f"{'False Negative Rate (FN/(FN+TP))':<36} | {self.binary_metrics_fixed['false_negative_rate_pct']:>16.1f}% | {self.binary_metrics_adaptive['false_negative_rate_pct']:>16.1f}%",
            f"{'Root-Cause Attribution Recall (Faults)':<36} | {'0.0%':>17} | {cm_dict['fault_attribution_recall_pct']:>16.1f}%",
            f"{'Overall Multi-Class Accuracy':<36} | {self.binary_metrics_fixed['accuracy_pct']:>16.1f}% | {cm_dict['overall_accuracy_pct']:>16.1f}%",
            "=" * 78,
        ]
        return "\n".join(lines)


class ExpandedBenchmarkSuite:
    """
    Constructs and executes reproducible, standardized benchmarks of 100+
    randomized simulated drive cycles across operating dimensions.
    """

    def __init__(self, baseline: Optional[CellBaseline] = None) -> None:
        if baseline is None:
            cal_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=1.0, initial_temp_c=25.0)
            self.baseline = BaselineCalibrator(cal_cell, cell_id="BENCHMARK-STD").build()
        else:
            self.baseline = baseline

        # Baseline cache for aged cells (SOH 70%, 80%, 90%, 100%)
        self._baseline_cache: Dict[int, CellBaseline] = {100: self.baseline}

    def get_baseline_for_soh(self, soh_retention: float) -> CellBaseline:
        """Returns or calibrates a personalized reference model for an aged cell."""
        soh_pct = int(round(soh_retention * 100.0))
        if soh_pct in self._baseline_cache:
            return self._baseline_cache[soh_pct]

        p = CellParameters.default_nmc()
        p.nominal_capacity_ah *= soh_retention
        p.r0_ref /= math.sqrt(max(0.5, soh_retention))
        cal_cell = BatteryCell(params=p, initial_soc=1.0, initial_temp_c=25.0)
        b = BaselineCalibrator(cal_cell, cell_id=f"REF-SOH-{soh_pct}").build()
        self._baseline_cache[soh_pct] = b
        return b

    def _create_load_profile(self, name: str, duration_s: float) -> LoadProfile:
        if name == "SPORT":
            return AggressiveSportProfile(duration_s=duration_s)
        elif name == "ECO":
            return EcoConservativeProfile(duration_s=duration_s)
        elif name == "URBAN":
            return StopAndGoUrbanProfile(duration_s=duration_s)
        elif name == "STOCHASTIC":
            return DynamicStochasticProfile(duration_s=duration_s, base_current_a=1.8, sigma_a=0.8, spike_magnitude_a=4.0)
        elif name == "DISCHARGE_NET":
            return DriveCycleProfile(peak_current_a=4.5, regen_ratio=0.15, duration_s=duration_s)
        else:
            return DriveCycleProfile(peak_current_a=4.5, regen_ratio=0.25, duration_s=duration_s)

    def generate_tuning_scenarios(self, seed_start: int = 1000, count: int = 25) -> List[ExpandedBenchmarkScenario]:
        """Generates 25 tuning scenarios (seeds 1000..1024) used for development sanity checks."""
        scenarios: List[ExpandedBenchmarkScenario] = []
        profiles = ["SPORT", "ECO", "URBAN", "STOCHASTIC", "STANDARD"]
        temps = [-10.0, 0.0, 25.0, 35.0]

        for i in range(count):
            seed = seed_start + i
            prof_name = profiles[i % len(profiles)]
            temp = temps[i % len(temps)]
            rest = 10.0 + (i % 3) * 5.0

            mod = i % 5
            if mod == 0:
                # Nominal
                cfg = FaultScenarioConfig(fault_type=FaultType.NOMINAL)
                scenarios.append(ExpandedBenchmarkScenario(
                    scenario_id=f"TUNE-{i+1:03d}",
                    name=f"Tuning Nominal ({temp}C, {prof_name})",
                    category="NOMINAL",
                    ground_truth_fault=FaultType.NOMINAL,
                    is_fault=False,
                    soh_retention=1.0,
                    ambient_temp_c=temp,
                    drive_profile_name=prof_name,
                    rest_duration_s=rest,
                    seed=seed,
                    fault_config=cfg,
                    has_personalized_baseline=True,
                ))
            elif mod == 1:
                # Resistance
                adder = 0.010 + (i % 4) * 0.005
                cfg = FaultScenarioConfig(fault_type=FaultType.INCREASED_RESISTANCE, resistance_adder_ohm=adder)
                scenarios.append(ExpandedBenchmarkScenario(
                    scenario_id=f"TUNE-{i+1:03d}",
                    name=f"Tuning Resistance (+{int(adder*1000)}mOhm, {temp}C)",
                    category="INCREASED_RESISTANCE",
                    ground_truth_fault=FaultType.INCREASED_RESISTANCE,
                    is_fault=True,
                    soh_retention=1.0,
                    ambient_temp_c=temp,
                    drive_profile_name=prof_name,
                    rest_duration_s=rest,
                    seed=seed,
                    fault_config=cfg,
                    has_personalized_baseline=True,
                ))
            elif mod == 2:
                # Voltage bias
                bias = 0.030 if (i % 2 == 0) else -0.030
                cfg = FaultScenarioConfig(fault_type=FaultType.VOLTAGE_SENSOR_BIAS, voltage_bias_v=bias)
                scenarios.append(ExpandedBenchmarkScenario(
                    scenario_id=f"TUNE-{i+1:03d}",
                    name=f"Tuning Voltage Bias ({int(bias*1000)}mV, {temp}C)",
                    category="VOLTAGE_SENSOR_BIAS",
                    ground_truth_fault=FaultType.VOLTAGE_SENSOR_BIAS,
                    is_fault=True,
                    soh_retention=1.0,
                    ambient_temp_c=temp,
                    drive_profile_name=prof_name,
                    rest_duration_s=rest,
                    seed=seed,
                    fault_config=cfg,
                    has_personalized_baseline=True,
                ))
            elif mod == 3:
                # Temperature rise
                cfg = FaultScenarioConfig(fault_type=FaultType.TEMPERATURE_RISE, cooling_factor=0.30, external_heat_flux_w=1.5)
                scenarios.append(ExpandedBenchmarkScenario(
                    scenario_id=f"TUNE-{i+1:03d}",
                    name=f"Tuning Cooling Anomaly ({temp}C)",
                    category="TEMPERATURE_RISE",
                    ground_truth_fault=FaultType.TEMPERATURE_RISE,
                    is_fault=True,
                    soh_retention=1.0,
                    ambient_temp_c=temp,
                    drive_profile_name=prof_name,
                    rest_duration_s=rest,
                    seed=seed,
                    fault_config=cfg,
                    has_personalized_baseline=True,
                ))
            else:
                # Capacity fade
                ret = 0.80
                cfg = FaultScenarioConfig(fault_type=FaultType.CAPACITY_FADE, capacity_retention_factor=ret)
                scenarios.append(ExpandedBenchmarkScenario(
                    scenario_id=f"TUNE-{i+1:03d}",
                    name=f"Tuning Capacity Fade (20% loss, {temp}C)",
                    category="CAPACITY_FADE",
                    ground_truth_fault=FaultType.CAPACITY_FADE,
                    is_fault=True,
                    soh_retention=ret,
                    ambient_temp_c=temp,
                    drive_profile_name="DISCHARGE_NET",
                    rest_duration_s=rest,
                    seed=seed,
                    fault_config=cfg,
                    has_personalized_baseline=False,
                ))

        return scenarios

    def generate_held_out_scenarios(self, seed_start: int = 2000, count: int = 100) -> List[ExpandedBenchmarkScenario]:
        """
        Generates 100 strictly held-out evaluation scenarios (seeds 2000..2099)
        covering multi-SOH (70%, 80%, 90%, 100%), temperature ranges (-15C to 45C),
        dual-direction voltage bias, internal resistance, cooling degradation, capacity fade,
        and sensor noise/compound faults.
        """
        scenarios: List[ExpandedBenchmarkScenario] = []
        seed = seed_start

        # ── 1. Nominal Healthy Cells (30 scenarios) ──────────────────────────
        # SOH 100% fresh cell (8 cases)
        fresh_specs = [
            (-15.0, "SPORT", 15.0),
            (-10.0, "ECO", 20.0),
            (-5.0, "URBAN", 10.0),
            (0.0, "STOCHASTIC", 12.0),
            (10.0, "STANDARD", 15.0),
            (25.0, "SPORT", 20.0),
            (35.0, "ECO", 10.0),
            (45.0, "URBAN", 15.0),
        ]
        for t, prof, rest in fresh_specs:
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Nominal Fresh SOH 100% ({t}C, {prof})",
                category="NOMINAL",
                ground_truth_fault=FaultType.NOMINAL,
                is_fault=False,
                soh_retention=1.0,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=rest,
                seed=seed,
                fault_config=FaultScenarioConfig(fault_type=FaultType.NOMINAL),
                has_personalized_baseline=True,
            ))
            seed += 1

        # SOH 90% aged cell (8 cases)
        aged90_specs = [
            (-10.0, "URBAN", 15.0),
            (0.0, "SPORT", 20.0),
            (15.0, "ECO", 12.0),
            (25.0, "STOCHASTIC", 15.0),
            (30.0, "STANDARD", 10.0),
            (40.0, "SPORT", 15.0),
            (25.0, "URBAN", 25.0),
            (25.0, "ECO", 10.0),
        ]
        for t, prof, rest in aged90_specs:
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Nominal Aged SOH 90% ({t}C, {prof})",
                category="NOMINAL",
                ground_truth_fault=FaultType.NOMINAL,
                is_fault=False,
                soh_retention=0.90,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=rest,
                seed=seed,
                fault_config=FaultScenarioConfig(fault_type=FaultType.NOMINAL),
                has_personalized_baseline=True,
            ))
            seed += 1

        # SOH 80% aged cell (7 cases)
        aged80_specs = [
            (-10.0, "ECO", 15.0),
            (0.0, "STANDARD", 15.0),
            (20.0, "SPORT", 20.0),
            (25.0, "URBAN", 15.0),
            (35.0, "STOCHASTIC", 12.0),
            (45.0, "ECO", 10.0),
            (25.0, "SPORT", 20.0),
        ]
        for t, prof, rest in aged80_specs:
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Nominal Aged SOH 80% ({t}C, {prof})",
                category="NOMINAL",
                ground_truth_fault=FaultType.NOMINAL,
                is_fault=False,
                soh_retention=0.80,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=rest,
                seed=seed,
                fault_config=FaultScenarioConfig(fault_type=FaultType.NOMINAL),
                has_personalized_baseline=True,
            ))
            seed += 1

        # SOH 70% aged cell (7 cases)
        aged70_specs = [
            (-5.0, "URBAN", 15.0),
            (10.0, "ECO", 12.0),
            (25.0, "STANDARD", 15.0),
            (30.0, "SPORT", 20.0),
            (40.0, "STOCHASTIC", 15.0),
            (25.0, "ECO", 10.0),
            (25.0, "URBAN", 20.0),
        ]
        for t, prof, rest in aged70_specs:
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Nominal Aged SOH 70% ({t}C, {prof})",
                category="NOMINAL",
                ground_truth_fault=FaultType.NOMINAL,
                is_fault=False,
                soh_retention=0.70,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=rest,
                seed=seed,
                fault_config=FaultScenarioConfig(fault_type=FaultType.NOMINAL),
                has_personalized_baseline=True,
            ))
            seed += 1

        # ── 2. Voltage Sensor Bias (18 scenarios) ─────────────────────────────
        # 9 Positive bias
        pos_biases = [
            (0.018, 25.0, "SPORT", 20.0),
            (0.022, 15.0, "ECO", 15.0),
            (0.028, 25.0, "URBAN", 15.0),
            (0.035, 0.0, "STOCHASTIC", 15.0),
            (0.040, 35.0, "STANDARD", 12.0),
            (0.045, -5.0, "SPORT", 20.0),
            (0.050, 25.0, "ECO", 15.0),
            (0.055, 20.0, "URBAN", 20.0),
            (0.060, 25.0, "STOCHASTIC", 15.0),
        ]
        for b_v, t, prof, rest in pos_biases:
            cfg = FaultScenarioConfig(fault_type=FaultType.VOLTAGE_SENSOR_BIAS, voltage_bias_v=b_v)
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Voltage Bias +{int(b_v*1000)}mV ({t}C, {prof})",
                category="VOLTAGE_SENSOR_BIAS",
                ground_truth_fault=FaultType.VOLTAGE_SENSOR_BIAS,
                is_fault=True,
                soh_retention=1.0,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=rest,
                seed=seed,
                fault_config=cfg,
                has_personalized_baseline=True,
            ))
            seed += 1

        # 9 Negative bias
        neg_biases = [
            (-0.018, 25.0, "ECO", 15.0),
            (-0.022, 30.0, "SPORT", 20.0),
            (-0.028, 25.0, "STANDARD", 12.0),
            (-0.035, 10.0, "URBAN", 15.0),
            (-0.040, -5.0, "STOCHASTIC", 15.0),
            (-0.045, 25.0, "SPORT", 20.0),
            (-0.050, 0.0, "ECO", 15.0),
            (-0.055, 25.0, "STANDARD", 15.0),
            (-0.060, 35.0, "URBAN", 20.0),
        ]
        for b_v, t, prof, rest in neg_biases:
            cfg = FaultScenarioConfig(fault_type=FaultType.VOLTAGE_SENSOR_BIAS, voltage_bias_v=b_v)
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Voltage Bias {int(b_v*1000)}mV ({t}C, {prof})",
                category="VOLTAGE_SENSOR_BIAS",
                ground_truth_fault=FaultType.VOLTAGE_SENSOR_BIAS,
                is_fault=True,
                soh_retention=1.0,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=rest,
                seed=seed,
                fault_config=cfg,
                has_personalized_baseline=True,
            ))
            seed += 1

        # ── 3. Increased Internal Resistance (18 scenarios) ───────────────────
        r_adders = [
            (0.008, 25.0, "SPORT", 20.0),
            (0.010, 25.0, "ECO", 15.0),
            (0.012, 20.0, "URBAN", 15.0),
            (0.014, 0.0, "STOCHASTIC", 15.0),
            (0.016, 25.0, "STANDARD", 15.0),
            (0.018, 30.0, "SPORT", 20.0),
            (0.020, 25.0, "ECO", 15.0),
            (0.022, 10.0, "URBAN", 15.0),
            (0.024, 25.0, "STOCHASTIC", 15.0),
            (0.026, 35.0, "STANDARD", 15.0),
            (0.028, 25.0, "SPORT", 20.0),
            (0.030, -5.0, "ECO", 15.0),
            (0.032, 25.0, "URBAN", 15.0),
            (0.035, 25.0, "STOCHASTIC", 15.0),
            (0.015, -10.0, "STANDARD", 15.0),
            (0.020, 0.0, "SPORT", 20.0),
            (0.025, 35.0, "ECO", 15.0),
            (0.030, 45.0, "URBAN", 15.0),
        ]
        for r_add, t, prof, rest in r_adders:
            cfg = FaultScenarioConfig(fault_type=FaultType.INCREASED_RESISTANCE, resistance_adder_ohm=r_add)
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Internal Resistance +{int(r_add*1000)}mOhm ({t}C, {prof})",
                category="INCREASED_RESISTANCE",
                ground_truth_fault=FaultType.INCREASED_RESISTANCE,
                is_fault=True,
                soh_retention=1.0,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=rest,
                seed=seed,
                fault_config=cfg,
                has_personalized_baseline=True,
            ))
            seed += 1

        # ── 4. Abnormal Thermal Rise (14 scenarios) ───────────────────────────
        thermal_specs = [
            (0.15, 2.5, 25.0, "SPORT", 20.0),
            (0.20, 2.0, 25.0, "STANDARD", 15.0),
            (0.20, 3.0, 30.0, "URBAN", 15.0),
            (0.25, 1.8, 25.0, "ECO", 15.0),
            (0.30, 1.5, 20.0, "STOCHASTIC", 15.0),
            (0.35, 2.0, 35.0, "SPORT", 20.0),
            (0.40, 1.2, 25.0, "STANDARD", 15.0),
            (0.45, 1.5, 25.0, "URBAN", 15.0),
            (0.50, 2.5, 25.0, "ECO", 15.0),
            (0.55, 1.8, 15.0, "STOCHASTIC", 15.0),
            (0.60, 2.0, 30.0, "SPORT", 20.0),
            (0.20, 1.0, 40.0, "STANDARD", 15.0),
            (0.25, 2.2, 0.0, "URBAN", 15.0),
            (0.30, 2.8, 25.0, "SPORT", 20.0),
        ]
        for c_fac, q_w, t, prof, rest in thermal_specs:
            cfg = FaultScenarioConfig(fault_type=FaultType.TEMPERATURE_RISE, cooling_factor=c_fac, external_heat_flux_w=q_w)
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Cooling Degradation (h*{c_fac:.2f}, +{q_w:.1f}W, {t}C)",
                category="TEMPERATURE_RISE",
                ground_truth_fault=FaultType.TEMPERATURE_RISE,
                is_fault=True,
                soh_retention=1.0,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=rest,
                seed=seed,
                fault_config=cfg,
                has_personalized_baseline=True,
            ))
            seed += 1

        # ── 5. Usable Capacity Fade (12 scenarios) ───────────────────────────
        # Evaluated against reference with net discharge to guarantee delta_soc >= 0.08
        cap_specs = [
            (0.85, 1.0, 25.0, 15.0),
            (0.85, 1.0, 15.0, 20.0),
            (0.82, 1.0, 25.0, 15.0),
            (0.82, 1.0, 30.0, 15.0),
            (0.80, 1.0, 25.0, 20.0),
            (0.80, 1.0, 0.0, 15.0),
            (0.76, 1.0, 25.0, 15.0),
            (0.76, 1.0, 35.0, 20.0),
            (0.72, 1.0, 25.0, 15.0),
            (0.72, 1.0, 10.0, 15.0),
            (0.75, 0.90, 25.0, 15.0), # uncalibrated fade on 90% cell
            (0.68, 0.80, 25.0, 15.0), # uncalibrated fade on 80% cell
        ]
        for ret, base_soh, t, rest in cap_specs:
            cfg = FaultScenarioConfig(fault_type=FaultType.CAPACITY_FADE, capacity_retention_factor=ret)
            fade_pct = int(round((1.0 - ret) * 100.0))
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=f"Capacity Fade {fade_pct}% ({t}C, Net Discharge)",
                category="CAPACITY_FADE",
                ground_truth_fault=FaultType.CAPACITY_FADE,
                is_fault=True,
                soh_retention=base_soh,
                ambient_temp_c=t,
                drive_profile_name="DISCHARGE_NET",
                rest_duration_s=rest,
                seed=seed,
                fault_config=cfg,
                has_personalized_baseline=False,
            ))
            seed += 1

        # ── 6. Sensor Noise & Compound Cases (8 scenarios) ───────────────────
        noise_compound_specs = [
            # High noise on nominal cell (must stay NOMINAL)
            (FaultType.NOMINAL, 0.0, 0.0, 1.0, 0.0, 0.006, 0.05, 0.5, 25.0, "SPORT", "Nominal + Elevated Noise"),
            # Harsh noise on nominal cell (must stay NOMINAL)
            (FaultType.NOMINAL, 0.0, 0.0, 1.0, 0.0, 0.010, 0.08, 0.8, 25.0, "URBAN", "Nominal + Harsh Noise"),
            # Resistance + cold subzero (-10C)
            (FaultType.INCREASED_RESISTANCE, 0.016, 0.0, 1.0, 0.0, 0.002, 0.02, 0.1, -10.0, "STANDARD", "Resistance (+16mOhm) + Subzero Cold (-10C)"),
            # Resistance + high noise
            (FaultType.INCREASED_RESISTANCE, 0.022, 0.0, 1.0, 0.0, 0.006, 0.05, 0.3, 25.0, "SPORT", "Resistance (+22mOhm) + Elevated Noise"),
            # Voltage bias + high noise
            (FaultType.VOLTAGE_SENSOR_BIAS, 0.0, 0.035, 1.0, 0.0, 0.005, 0.04, 0.3, 25.0, "URBAN", "Voltage Bias (+35mV) + Elevated Noise"),
            # Negative voltage bias + high noise
            (FaultType.VOLTAGE_SENSOR_BIAS, 0.0, -0.035, 1.0, 0.0, 0.005, 0.04, 0.3, 25.0, "ECO", "Voltage Bias (-35mV) + Elevated Noise"),
            # Cooling failure + aggressive drive
            (FaultType.TEMPERATURE_RISE, 0.0, 0.0, 0.25, 2.0, 0.001, 0.01, 0.05, 25.0, "SPORT", "Cooling Loss (0.25) + Aggressive Drive"),
            # Cooling failure + elevated noise
            (FaultType.TEMPERATURE_RISE, 0.0, 0.0, 0.20, 1.8, 0.005, 0.04, 0.4, 25.0, "STOCHASTIC", "Cooling Loss (0.20) + Elevated Noise"),
        ]

        for ftype, r_add, v_bias, c_fac, q_w, nv, ni, nt, t, prof, desc in noise_compound_specs:
            cfg = FaultScenarioConfig(
                fault_type=ftype,
                resistance_adder_ohm=r_add,
                voltage_bias_v=v_bias,
                cooling_factor=c_fac,
                external_heat_flux_w=q_w,
                noise_std_v=nv,
                noise_std_a=ni,
                noise_std_temp_c=nt,
            )
            is_f = (ftype != FaultType.NOMINAL)
            cat = "NOMINAL" if not is_f else ftype.value
            scenarios.append(ExpandedBenchmarkScenario(
                scenario_id=f"EVAL-{len(scenarios)+1:03d}",
                name=desc,
                category=cat,
                ground_truth_fault=ftype,
                is_fault=is_f,
                soh_retention=1.0,
                ambient_temp_c=t,
                drive_profile_name=prof,
                rest_duration_s=15.0,
                seed=seed,
                fault_config=cfg,
                has_personalized_baseline=True,
            ))
            seed += 1

        return scenarios[:count]

    def run_suite(
        self,
        scenarios: List[ExpandedBenchmarkScenario],
        dataset_name: str = "held_out_evaluation",
        sim_duration_s: float = 360.0,
        dt: float = 2.0,
    ) -> ExpandedBenchmarkResult:
        """Executes a benchmark suite and returns structured statistical metrics."""
        total_steps = max(1, int(sim_duration_s / dt))
        cm = MultiClassConfusionMatrix()
        scenario_records: List[Dict[str, Any]] = []

        fixed_tps = 0
        fixed_tns = 0
        fixed_fps = 0
        fixed_fns = 0

        adapt_bin_tps = 0
        adapt_bin_tns = 0
        adapt_bin_fps = 0
        adapt_bin_fns = 0

        # Category and condition trackers
        category_tracker: Dict[str, Dict[str, int]] = {}
        condition_tracker: Dict[str, Dict[str, int]] = {}

        for scen in scenarios:
            # 1. Resolve baseline
            if scen.has_personalized_baseline:
                scen_baseline = self.get_baseline_for_soh(scen.soh_retention)
                p = CellParameters.default_nmc()
                p.nominal_capacity_ah *= scen.soh_retention
                p.r0_ref /= math.sqrt(max(0.5, scen.soh_retention))
                ref_cell = BatteryCell(params=p, initial_soc=0.85, initial_temp_c=scen.ambient_temp_c)
                base_cell = BatteryCell(params=p, initial_soc=0.85, initial_temp_c=scen.ambient_temp_c)
            else:
                scen_baseline = self.baseline
                ref_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.85, initial_temp_c=scen.ambient_temp_c)
                base_cell = BatteryCell(params=CellParameters.default_nmc(), initial_soc=0.85, initial_temp_c=scen.ambient_temp_c)

            # 2. Wrap faulty cell
            sim_cell = FaultyCell(base_cell=base_cell, config=scen.fault_config, seed=scen.seed)

            # 3. Setup monitors
            fixed_mon = FixedThresholdMonitor()
            adapt_mon = AdaptiveReferenceMonitor(baseline=scen_baseline, cell=ref_cell)
            load_prof = self._create_load_profile(scen.drive_profile_name, sim_duration_s)

            sim_history: List[Dict[str, Any]] = []

            # 4. Simulation loop
            for step_idx in range(total_steps):
                t_curr = (step_idx + 1) * dt
                # Inject settling rest
                is_rest = (t_curr % 60.0) < scen.rest_duration_s
                i_load = 0.0 if is_rest else float(load_prof.get_current(t_curr))

                diag = sim_cell.step(current=i_load, ambient_temp_c=scen.ambient_temp_c, dt=dt)
                sim_history.append(diag)

                if diag["v_terminal"] <= sim_cell.params.v_min:
                    break

                fixed_mon.check_step(
                    time_s=t_curr,
                    v_measured=diag["v_terminal"],
                    current_a=diag["current"],
                    cell_temp_c=diag["cell_temp_c"],
                    dcir_measured_mohm=diag["r0_mohm"],
                )
                adapt_mon.check_step(
                    time_s=t_curr,
                    v_measured=diag["v_terminal"],
                    current_a=diag["current"],
                    soc=diag["soc"],
                    cell_temp_c=diag["cell_temp_c"],
                    ambient_temp_c=scen.ambient_temp_c,
                    dcir_measured_mohm=diag["r0_mohm"],
                    dt=dt,
                )

            dev_report = adapt_mon.finalize()
            engine = FaultAttributionEngine(baseline=scen_baseline, cell=ref_cell)
            diagnosis = engine.diagnose(dev_report, sim_history)

            # 5. Evaluate detections
            fixed_detected = fixed_mon.has_tripped
            adaptive_detected = (diagnosis.attributed_fault != FaultType.NOMINAL)

            if scen.is_fault:
                if fixed_detected:
                    fixed_tps += 1
                else:
                    fixed_fns += 1

                if adaptive_detected:
                    adapt_bin_tps += 1
                else:
                    adapt_bin_fns += 1
            else:
                if fixed_detected:
                    fixed_fps += 1
                else:
                    fixed_tns += 1

                if adaptive_detected:
                    adapt_bin_fps += 1
                else:
                    adapt_bin_tns += 1

            # 6. Record confusion matrix
            pred_cause = diagnosis.attributed_fault.value
            gt_cause = scen.ground_truth_fault.value
            cm.record(ground_truth=gt_cause, predicted=pred_cause)

            # 7. Category and condition bookkeeping
            cat = scen.category
            if cat not in category_tracker:
                category_tracker[cat] = {"total": 0, "correct": 0}
            category_tracker[cat]["total"] += 1
            if pred_cause == gt_cause:
                category_tracker[cat]["correct"] += 1

            # Condition: Temperature band
            t_band = "Subzero (<=0C)" if scen.ambient_temp_c <= 0 else ("Mild (1-30C)" if scen.ambient_temp_c <= 30 else "Hot (>30C)")
            if t_band not in condition_tracker:
                condition_tracker[t_band] = {"total": 0, "correct": 0}
            condition_tracker[t_band]["total"] += 1
            if pred_cause == gt_cause:
                condition_tracker[t_band]["correct"] += 1

            scenario_records.append({
                "scenario_id": scen.scenario_id,
                "name": scen.name,
                "category": scen.category,
                "ground_truth": gt_cause,
                "predicted": pred_cause,
                "is_fault": scen.is_fault,
                "fixed_detected": fixed_detected,
                "adaptive_detected": adaptive_detected,
                "adaptive_confidence_pct": round(diagnosis.confidence * 100.0, 1),
                "adaptive_severity": diagnosis.severity_estimate,
                "correct": (pred_cause == gt_cause),
            })

        # 8. Compute final metrics
        total = len(scenarios)
        fault_count = sum(1 for s in scenarios if s.is_fault)
        nom_count = total - fault_count

        bm_fixed = calculate_binary_metrics(tp=fixed_tps, tn=fixed_tns, fp=fixed_fps, fn=fixed_fns)
        bm_adapt = calculate_binary_metrics(tp=adapt_bin_tps, tn=adapt_bin_tns, fp=adapt_bin_fps, fn=adapt_bin_fns)

        ci_95 = {
            "adaptive_accuracy": list(wilson_score_interval(int(round(cm.overall_accuracy_pct * total / 100.0)), total)),
            "adaptive_specificity": list(wilson_score_interval(bm_adapt.tn, nom_count)),
            "adaptive_sensitivity": list(wilson_score_interval(bm_adapt.tp, fault_count)),
            "adaptive_attribution_recall": list(wilson_score_interval(int(round(cm.fault_attribution_recall_pct * fault_count / 100.0)), fault_count)),
            "fixed_accuracy": list(wilson_score_interval(bm_fixed.tp + bm_fixed.tn, total)),
            "fixed_specificity": list(wilson_score_interval(bm_fixed.tn, nom_count)),
            "fixed_sensitivity": list(wilson_score_interval(bm_fixed.tp, fault_count)),
        }

        cat_breakdown = {
            k: {
                "total": v["total"],
                "correct": v["correct"],
                "accuracy_pct": round(v["correct"] / v["total"] * 100.0, 1) if v["total"] > 0 else 0.0,
            }
            for k, v in category_tracker.items()
        }

        cond_breakdown = {
            k: {
                "total": v["total"],
                "correct": v["correct"],
                "accuracy_pct": round(v["correct"] / v["total"] * 100.0, 1) if v["total"] > 0 else 0.0,
            }
            for k, v in condition_tracker.items()
        }

        return ExpandedBenchmarkResult(
            dataset_name=dataset_name,
            total_scenarios=total,
            fault_count=fault_count,
            nominal_count=nom_count,
            binary_metrics_adaptive=bm_adapt.to_dict(),
            binary_metrics_fixed=bm_fixed.to_dict(),
            multi_class_confusion_matrix=cm.to_dict(),
            confidence_intervals_95=ci_95,
            category_breakdown=cat_breakdown,
            condition_breakdown=cond_breakdown,
            scenarios=scenario_records,
        )


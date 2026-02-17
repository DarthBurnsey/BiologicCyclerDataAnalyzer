"""
Automated Cell Anomaly Detection and Flagging System.

This module provides comprehensive automated detection of battery cell anomalies
using statistical, pattern-based, and physics-based algorithms.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class FlagSeverity(Enum):
    """Flag severity levels."""
    INFO = "ℹ️"
    WARNING = "⚠️"
    CRITICAL = "🚨"


class FlagCategory(Enum):
    """Flag categories for organization."""
    PERFORMANCE = "Performance"
    QUALITY = "Quality Assurance"
    DATA_INTEGRITY = "Data Integrity"
    ELECTROCHEMISTRY = "Electrochemistry"


@dataclass
class CellFlag:
    """Represents a single cell flag/anomaly."""
    flag_id: str
    flag_type: str
    severity: FlagSeverity
    category: FlagCategory
    description: str
    confidence: float  # 0.0 to 1.0
    algorithm: str
    cycle: Optional[int] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    recommendation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert flag to dictionary for storage/display."""
        return {
            'flag_id': self.flag_id,
            'flag_type': self.flag_type,
            'severity': self.severity.name,
            'severity_icon': self.severity.value,
            'category': self.category.value,
            'description': self.description,
            'confidence': self.confidence,
            'algorithm': self.algorithm,
            'cycle': self.cycle,
            'metric_value': self.metric_value,
            'threshold_value': self.threshold_value,
            'recommendation': self.recommendation
        }


def analyze_cell_for_flags(df: pd.DataFrame, cell_data: Dict[str, Any], 
                           experiment_context: Optional[Dict[str, Any]] = None) -> List[CellFlag]:
    """
    Comprehensive automated analysis of a single cell for anomalies and issues.
    
    Args:
        df: Cell cycling data DataFrame
        cell_data: Cell metadata (loading, active_material, etc.)
        experiment_context: Optional context about experiment (avg values, etc.)
        
    Returns:
        List of detected flags sorted by severity and confidence
    """
    flags = []
    
    # Performance-based detection
    flags.extend(detect_performance_anomalies(df, cell_data))
    
    # Data integrity checks
    flags.extend(detect_data_integrity_issues(df, cell_data))
    
    # Electrochemical violations
    flags.extend(detect_electrochemical_violations(df, cell_data))
    
    # Statistical anomalies (if we have experiment context)
    if experiment_context:
        flags.extend(detect_statistical_anomalies(cell_data, experiment_context))
    
    # Sort by severity (Critical > Warning > Info) and then by confidence
    severity_order = {FlagSeverity.CRITICAL: 0, FlagSeverity.WARNING: 1, FlagSeverity.INFO: 2}
    flags.sort(key=lambda f: (severity_order[f.severity], -f.confidence))
    
    return flags


def detect_performance_anomalies(df: pd.DataFrame, cell_data: Dict[str, Any]) -> List[CellFlag]:
    """Detect performance-related anomalies (capacity fade, efficiency issues, etc.)."""
    flags = []
    
    # 1. Rapid Capacity Fade Detection
    rapid_fade_flag = detect_rapid_capacity_fade(df)
    if rapid_fade_flag:
        flags.append(rapid_fade_flag)
    
    # 2. Cell Failure Detection
    failure_flag = detect_cell_failure(df)
    if failure_flag:
        flags.append(failure_flag)
    
    # 3. High CE Variation Detection
    ce_variation_flag = detect_high_ce_variation(df)
    if ce_variation_flag:
        flags.append(ce_variation_flag)
    
    # 4. Low Coulombic Efficiency Detection
    low_ce_flag = detect_low_coulombic_efficiency(df)
    if low_ce_flag:
        flags.append(low_ce_flag)
    
    # 5. Accelerating Degradation Detection
    accel_deg_flag = detect_accelerating_degradation(df)
    if accel_deg_flag:
        flags.append(accel_deg_flag)
    
    # 6. First Cycle Issues
    first_cycle_flag = detect_first_cycle_issues(df, cell_data)
    if first_cycle_flag:
        flags.append(first_cycle_flag)
    
    return flags


def detect_data_integrity_issues(df: pd.DataFrame, cell_data: Dict[str, Any]) -> List[CellFlag]:
    """Detect data quality and integrity issues."""
    flags = []
    
    # 1. Incomplete Dataset Detection
    incomplete_flag = detect_incomplete_dataset(df, cell_data)
    if incomplete_flag:
        flags.append(incomplete_flag)
    
    # 2. Missing Data Detection
    missing_data_flag = detect_missing_data(df)
    if missing_data_flag:
        flags.append(missing_data_flag)
    
    # 3. Data Consistency Issues
    consistency_flag = detect_data_inconsistency(df)
    if consistency_flag:
        flags.append(consistency_flag)
    
    return flags


def detect_electrochemical_violations(df: pd.DataFrame, cell_data: Dict[str, Any]) -> List[CellFlag]:
    """Detect violations of electrochemical principles (physics-based detection)."""
    flags = []
    
    # 1. Impossible Efficiency (>100%)
    impossible_eff_flag = detect_impossible_efficiency(df)
    if impossible_eff_flag:
        flags.append(impossible_eff_flag)
    
    # 2. Theoretical Capacity Violation
    capacity_violation_flag = detect_theoretical_capacity_violation(df, cell_data)
    if capacity_violation_flag:
        flags.append(capacity_violation_flag)
    
    return flags


def detect_statistical_anomalies(cell_data: Dict[str, Any], 
                                 experiment_context: Dict[str, Any]) -> List[CellFlag]:
    """Detect statistical outliers compared to experiment cohort."""
    flags = []
    
    # Anomalous First Discharge Capacity
    anomalous_discharge_flag = detect_anomalous_first_discharge(cell_data, experiment_context)
    if anomalous_discharge_flag:
        flags.append(anomalous_discharge_flag)
    
    return flags


# ===========================
# Individual Detection Functions
# ===========================

def detect_rapid_capacity_fade(df: pd.DataFrame) -> Optional[CellFlag]:
    """Detect rapid capacity fade in early cycles."""
    if 'Q Dis (mAh/g)' not in df.columns or len(df) < 10:
        return None
    
    try:
        capacity = df['Q Dis (mAh/g)'].dropna()
        if len(capacity) < 10:
            return None
        
        # Calculate initial capacity (max of first 3 cycles)
        initial_cap = capacity.head(3).max()
        if initial_cap <= 0:
            return None
        
        # Check capacity at cycle 10
        cap_at_10 = capacity.iloc[9] if len(capacity) > 9 else capacity.iloc[-1]
        retention_pct = (cap_at_10 / initial_cap) * 100
        
        if retention_pct < 80:
            severity = FlagSeverity.CRITICAL if retention_pct < 70 else FlagSeverity.WARNING
            confidence = 0.95 if retention_pct < 70 else 0.85
            
            return CellFlag(
                flag_id='rapid_capacity_fade',
                flag_type='Rapid Capacity Fade',
                severity=severity,
                category=FlagCategory.PERFORMANCE,
                description=f"Cell shows rapid capacity loss: {retention_pct:.1f}% retention after 10 cycles",
                confidence=confidence,
                algorithm='pattern_rapid_fade',
                cycle=10,
                metric_value=retention_pct,
                threshold_value=80.0,
                recommendation="Check electrode processing quality, electrolyte compatibility, and cycling conditions. Consider cell manufacturing defects."
            )
    except Exception:
        pass
    
    return None


def detect_cell_failure(df: pd.DataFrame) -> Optional[CellFlag]:
    """Detect complete or near-complete cell failure."""
    if 'Q Dis (mAh/g)' not in df.columns or len(df) < 5:
        return None
    
    try:
        capacity = df['Q Dis (mAh/g)'].dropna()
        if len(capacity) < 5:
            return None
        
        # Get initial capacity
        initial_cap = capacity.head(3).max()
        if initial_cap <= 0:
            return None
        
        # Check if any recent capacity drops below 50% of initial
        recent_capacity = capacity.tail(min(5, len(capacity)))
        min_recent_cap = recent_capacity.min()
        retention_pct = (min_recent_cap / initial_cap) * 100
        
        if retention_pct < 50 and len(capacity) < 50:  # Early failure
            return CellFlag(
                flag_id='cell_failure',
                flag_type='Cell Failure',
                severity=FlagSeverity.CRITICAL,
                category=FlagCategory.PERFORMANCE,
                description=f"Cell failure detected: capacity dropped to {retention_pct:.1f}% of initial value",
                confidence=0.98,
                algorithm='pattern_cell_failure',
                metric_value=retention_pct,
                threshold_value=50.0,
                recommendation="Cell has failed. Check for internal short, dendrite formation, or severe degradation. Data may not be reliable."
            )
    except Exception:
        pass
    
    return None


def detect_high_ce_variation(df: pd.DataFrame) -> Optional[CellFlag]:
    """Detect high variation in coulombic efficiency during stable cycling."""
    if 'Efficiency (-)' not in df.columns or len(df) < 10:
        return None
    
    try:
        # Use efficiency data from after formation cycles (cycles 5+)
        efficiency = df['Efficiency (-)'].iloc[4:] * 100  # Convert to percentage
        
        if len(efficiency) < 5:
            return None
        
        ce_mean = efficiency.mean()
        ce_std = efficiency.std()
        
        # Only flag if mean CE is reasonable (>90%) but variation is high
        if ce_mean > 90 and ce_std > 5.0:
            severity = FlagSeverity.CRITICAL if ce_std > 10 else FlagSeverity.WARNING
            confidence = 0.90 if ce_std > 10 else 0.80
            
            return CellFlag(
                flag_id='high_ce_variation',
                flag_type='High CE Variation',
                severity=severity,
                category=FlagCategory.PERFORMANCE,
                description=f"High coulombic efficiency variation: {ce_std:.1f}% std dev (mean: {ce_mean:.1f}%)",
                confidence=confidence,
                algorithm='statistical_ce_variation',
                metric_value=ce_std,
                threshold_value=5.0,
                recommendation="Check for inconsistent cycling conditions, temperature fluctuations, or electrode stability issues."
            )
    except Exception:
        pass
    
    return None


def detect_low_coulombic_efficiency(df: pd.DataFrame) -> Optional[CellFlag]:
    """Detect consistently low coulombic efficiency."""
    if 'Efficiency (-)' not in df.columns or len(df) < 10:
        return None
    
    try:
        # Use efficiency data from after formation cycles (cycles 5+)
        efficiency = df['Efficiency (-)'].iloc[4:] * 100  # Convert to percentage
        
        if len(efficiency) < 5:
            return None
        
        ce_mean = efficiency.mean()
        
        if ce_mean < 95:
            severity = FlagSeverity.CRITICAL if ce_mean < 90 else FlagSeverity.WARNING
            confidence = 0.95
            
            return CellFlag(
                flag_id='low_coulombic_efficiency',
                flag_type='Low Coulombic Efficiency',
                severity=severity,
                category=FlagCategory.PERFORMANCE,
                description=f"Consistently low coulombic efficiency: {ce_mean:.2f}% average",
                confidence=confidence,
                algorithm='statistical_low_ce',
                metric_value=ce_mean,
                threshold_value=95.0,
                recommendation="Low CE indicates side reactions or active material loss. Check electrolyte stability and electrode-electrolyte interface."
            )
    except Exception:
        pass
    
    return None


def detect_accelerating_degradation(df: pd.DataFrame) -> Optional[CellFlag]:
    """Detect if degradation rate is increasing over time."""
    if 'Q Dis (mAh/g)' not in df.columns or len(df) < 20:
        return None
    
    try:
        capacity = df['Q Dis (mAh/g)'].dropna()
        if len(capacity) < 20:
            return None
        
        # Split into early and late periods
        mid_point = len(capacity) // 2
        early_capacity = capacity.iloc[:mid_point]
        late_capacity = capacity.iloc[mid_point:]
        
        # Calculate fade rates for each period (% per cycle)
        early_fade_rate = calculate_fade_rate(early_capacity)
        late_fade_rate = calculate_fade_rate(late_capacity)
        
        # Check if late fade rate is significantly higher than early
        if early_fade_rate is not None and late_fade_rate is not None:
            if late_fade_rate > early_fade_rate * 2 and late_fade_rate > 0.2:
                return CellFlag(
                    flag_id='accelerating_degradation',
                    flag_type='Accelerating Degradation',
                    severity=FlagSeverity.WARNING,
                    category=FlagCategory.PERFORMANCE,
                    description=f"Degradation rate increasing: early {early_fade_rate:.2f}%/cycle → late {late_fade_rate:.2f}%/cycle",
                    confidence=0.85,
                    algorithm='pattern_accelerating_fade',
                    metric_value=late_fade_rate,
                    threshold_value=early_fade_rate * 2,
                    recommendation="Accelerating degradation suggests progressive failure mechanism. Check for dendrite growth or SEI instability."
                )
    except Exception:
        pass
    
    return None


def calculate_fade_rate(capacity_series: pd.Series) -> Optional[float]:
    """Calculate capacity fade rate as percentage per cycle."""
    try:
        if len(capacity_series) < 2:
            return None
        
        # Linear regression to get slope
        cycles = np.arange(len(capacity_series))
        coeffs = np.polyfit(cycles, capacity_series, 1)
        slope = coeffs[0]
        
        # Convert to percentage per cycle
        initial_cap = capacity_series.iloc[0]
        if initial_cap > 0:
            fade_rate_pct = abs(slope / initial_cap) * 100
            return fade_rate_pct
    except Exception:
        pass
    
    return None


def detect_first_cycle_issues(df: pd.DataFrame, cell_data: Dict[str, Any]) -> Optional[CellFlag]:
    """Detect issues with first cycle performance."""
    if 'Efficiency (-)' not in df.columns or len(df) < 1:
        return None
    
    try:
        first_efficiency = df['Efficiency (-)'].iloc[0] * 100
        
        # Flag extremely low first cycle efficiency
        if first_efficiency < 60:
            severity = FlagSeverity.CRITICAL if first_efficiency < 40 else FlagSeverity.WARNING
            
            return CellFlag(
                flag_id='poor_first_cycle_efficiency',
                flag_type='Poor First Cycle Efficiency',
                severity=severity,
                category=FlagCategory.PERFORMANCE,
                description=f"Very low first cycle efficiency: {first_efficiency:.1f}%",
                confidence=0.90,
                algorithm='threshold_first_efficiency',
                cycle=1,
                metric_value=first_efficiency,
                threshold_value=60.0,
                recommendation="Low first cycle efficiency indicates excessive SEI formation or irreversible capacity loss. Check electrode surface area and electrolyte composition."
            )
    except Exception:
        pass
    
    return None


def detect_incomplete_dataset(df: pd.DataFrame, cell_data: Dict[str, Any]) -> Optional[CellFlag]:
    """Detect if dataset appears incomplete or terminated early."""
    if len(df) < 5:
        return None
    
    try:
        # Check if cell stopped cycling unexpectedly (rapid termination)
        capacity = df['Q Dis (mAh/g)'].dropna() if 'Q Dis (mAh/g)' in df.columns else None
        
        if capacity is not None and len(capacity) >= 5:
            # Get initial capacity
            initial_cap = capacity.head(3).max()
            final_cap = capacity.iloc[-1]
            retention = (final_cap / initial_cap) * 100 if initial_cap > 0 else 100
            
            # If cell still has good capacity but few cycles, likely stopped early
            if retention > 80 and len(capacity) < 30:
                return CellFlag(
                    flag_id='incomplete_dataset',
                    flag_type='Incomplete Dataset',
                    severity=FlagSeverity.INFO,
                    category=FlagCategory.DATA_INTEGRITY,
                    description=f"Dataset appears incomplete: only {len(capacity)} cycles with {retention:.1f}% capacity retention",
                    confidence=0.75,
                    algorithm='heuristic_incomplete_data',
                    metric_value=len(capacity),
                    recommendation="Cell stopped early - data may not reflect full cycle life. Consider continuing test or marking as preliminary data."
                )
            
            # Check for abrupt termination (sudden stop in cycling)
            if len(capacity) > 10:
                # Check if capacity is stable at end (not degrading) - suggests manual stop
                final_5_capacity = capacity.tail(5)
                capacity_trend = final_5_capacity.std() / final_5_capacity.mean() if final_5_capacity.mean() > 0 else 0
                
                if capacity_trend < 0.05 and retention > 70:  # Very stable capacity at end
                    return CellFlag(
                        flag_id='premature_termination',
                        flag_type='Premature Termination',
                        severity=FlagSeverity.INFO,
                        category=FlagCategory.DATA_INTEGRITY,
                        description=f"Test terminated prematurely: {len(capacity)} cycles completed with stable capacity",
                        confidence=0.80,
                        algorithm='pattern_premature_stop',
                        metric_value=retention,
                        recommendation="Cell was stopped while still performing well. Cycle life data incomplete."
                    )
    except Exception:
        pass
    
    return None


def detect_missing_data(df: pd.DataFrame) -> Optional[CellFlag]:
    """Detect missing or sparse data in critical columns."""
    try:
        critical_columns = ['Q Dis (mAh/g)', 'Q Chg (mAh/g)', 'Efficiency (-)']
        missing_info = []
        
        for col in critical_columns:
            if col in df.columns:
                missing_pct = (df[col].isna().sum() / len(df)) * 100
                if missing_pct > 20:
                    missing_info.append(f"{col}: {missing_pct:.0f}% missing")
        
        if missing_info:
            return CellFlag(
                flag_id='missing_data',
                flag_type='Missing Data',
                severity=FlagSeverity.WARNING,
                category=FlagCategory.DATA_INTEGRITY,
                description=f"Significant missing data: {', '.join(missing_info)}",
                confidence=1.0,
                algorithm='data_completeness_check',
                recommendation="Missing data may affect analysis accuracy. Check data acquisition system."
            )
    except Exception:
        pass
    
    return None


def detect_data_inconsistency(df: pd.DataFrame) -> Optional[CellFlag]:
    """Detect inconsistencies in data (e.g., negative capacities, zero values)."""
    try:
        issues = []
        
        # Check for negative capacities
        if 'Q Dis (mAh/g)' in df.columns:
            negative_count = (df['Q Dis (mAh/g)'] < 0).sum()
            if negative_count > 0:
                issues.append(f"{negative_count} negative discharge capacity values")
        
        # Check for zero capacities (unusual)
        if 'Q Dis (mAh/g)' in df.columns:
            zero_count = (df['Q Dis (mAh/g)'] == 0).sum()
            if zero_count > len(df) * 0.1:  # More than 10% zeros
                issues.append(f"{zero_count} zero capacity values")
        
        if issues:
            return CellFlag(
                flag_id='data_inconsistency',
                flag_type='Data Inconsistency',
                severity=FlagSeverity.WARNING,
                category=FlagCategory.DATA_INTEGRITY,
                description=f"Data inconsistencies detected: {', '.join(issues)}",
                confidence=1.0,
                algorithm='data_validation',
                recommendation="Check raw data files for corruption or processing errors."
            )
    except Exception:
        pass
    
    return None


def detect_impossible_efficiency(df: pd.DataFrame) -> Optional[CellFlag]:
    """Detect physically impossible efficiency values (>100%)."""
    if 'Efficiency (-)' not in df.columns:
        return None
    
    try:
        efficiency_pct = df['Efficiency (-)'] * 100
        impossible_count = (efficiency_pct > 105).sum()  # Allow 5% measurement tolerance
        
        if impossible_count > 0:
            max_efficiency = efficiency_pct.max()
            max_cycle_idx = efficiency_pct.idxmax()
            cycle_num = df.iloc[max_cycle_idx, 0] if len(df.columns) > 0 else None
            
            return CellFlag(
                flag_id='impossible_efficiency',
                flag_type='Impossible Efficiency',
                severity=FlagSeverity.CRITICAL,
                category=FlagCategory.ELECTROCHEMISTRY,
                description=f"Physically impossible efficiency detected: {max_efficiency:.1f}% at cycle {cycle_num}",
                confidence=0.99,
                algorithm='physics_conservation_laws',
                cycle=cycle_num,
                metric_value=max_efficiency,
                threshold_value=100.0,
                recommendation="Efficiency >100% violates conservation of energy. Check data processing, loading values, and active material percentage."
            )
    except Exception:
        pass
    
    return None


def detect_theoretical_capacity_violation(df: pd.DataFrame, cell_data: Dict[str, Any]) -> Optional[CellFlag]:
    """Detect if capacity exceeds reasonable theoretical limits."""
    if 'Q Dis (mAh/g)' not in df.columns:
        return None
    
    try:
        # Theoretical capacity limits for common materials (mAh/g)
        # Graphite: ~372, NMC: ~275, LFP: ~170, Si: ~4200
        # Use conservative upper limit of 450 mAh/g for most cathode materials
        theoretical_limit = 450  # mAh/g - conservative upper bound
        
        max_capacity = df['Q Dis (mAh/g)'].max()
        
        if max_capacity > theoretical_limit:
            max_cycle_idx = df['Q Dis (mAh/g)'].idxmax()
            cycle_num = df.iloc[max_cycle_idx, 0] if len(df.columns) > 0 else None
            
            return CellFlag(
                flag_id='theoretical_capacity_violation',
                flag_type='Exceeds Theoretical Capacity',
                severity=FlagSeverity.WARNING,
                category=FlagCategory.ELECTROCHEMISTRY,
                description=f"Capacity exceeds typical limits: {max_capacity:.1f} mAh/g at cycle {cycle_num}",
                confidence=0.80,
                algorithm='physics_theoretical_limit',
                cycle=cycle_num,
                metric_value=max_capacity,
                threshold_value=theoretical_limit,
                recommendation="Verify loading measurement and active material percentage. For specialized materials (e.g., Si), this may be normal."
            )
    except Exception:
        pass
    
    return None


def detect_anomalous_first_discharge(cell_data: Dict[str, Any], 
                                     experiment_context: Dict[str, Any]) -> Optional[CellFlag]:
    """Detect if first discharge capacity is statistically anomalous compared to experiment."""
    try:
        first_discharge = cell_data.get('first_discharge')
        if first_discharge is None:
            return None
        
        # Get experiment statistics
        exp_first_discharge_values = experiment_context.get('first_discharge_values', [])
        if len(exp_first_discharge_values) < 3:  # Need at least 3 cells for comparison
            return None
        
        exp_mean = np.mean(exp_first_discharge_values)
        exp_std = np.std(exp_first_discharge_values)
        
        if exp_std == 0:
            return None
        
        z_score = abs((first_discharge - exp_mean) / exp_std)
        
        if z_score > 3.0:
            direction = "high" if first_discharge > exp_mean else "low"
            severity = FlagSeverity.WARNING if z_score < 4 else FlagSeverity.CRITICAL
            
            return CellFlag(
                flag_id='anomalous_first_discharge',
                flag_type='Anomalous First Discharge',
                severity=severity,
                category=FlagCategory.QUALITY,
                description=f"First discharge capacity is anomalous: {first_discharge:.1f} mAh/g ({direction}, {z_score:.1f}σ from experiment mean {exp_mean:.1f})",
                confidence=0.90,
                algorithm='statistical_z_score',
                cycle=1,
                metric_value=first_discharge,
                threshold_value=exp_mean,
                recommendation="Verify loading and active material measurements. May indicate cell preparation variability."
            )
    except Exception:
        pass
    
    return None


def get_experiment_context(individual_cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build statistical context about an experiment for comparison.
    
    Args:
        individual_cells: List of all cells in experiment
        
    Returns:
        Dictionary with statistical metrics for comparison
    """
    context = {}
    
    # Collect first discharge values
    first_discharge_values = [
        cell['first_discharge'] 
        for cell in individual_cells 
        if cell.get('first_discharge') is not None
    ]
    context['first_discharge_values'] = first_discharge_values
    
    return context


def format_flags_for_display(flags: List[CellFlag]) -> str:
    """
    Format flags for compact display in table cell.
    
    Args:
        flags: List of CellFlag objects
        
    Returns:
        Formatted string for display
    """
    if not flags:
        return ""
    
    # Group by severity
    critical = [f for f in flags if f.severity == FlagSeverity.CRITICAL]
    warning = [f for f in flags if f.severity == FlagSeverity.WARNING]
    info = [f for f in flags if f.severity == FlagSeverity.INFO]
    
    parts = []
    if critical:
        parts.append(f"🚨 {len(critical)}")
    if warning:
        parts.append(f"⚠️ {len(warning)}")
    if info:
        parts.append(f"ℹ️ {len(info)}")
    
    return " ".join(parts)


def get_flag_summary_stats(all_flags: Dict[str, List[CellFlag]]) -> Dict[str, Any]:
    """
    Calculate summary statistics for all flags.
    
    Args:
        all_flags: Dictionary mapping cell_name to list of flags
        
    Returns:
        Dictionary with summary statistics
    """
    total_flags = sum(len(flags) for flags in all_flags.values())
    
    critical_count = 0
    warning_count = 0
    info_count = 0
    
    flag_type_counts = {}
    category_counts = {}
    
    for flags in all_flags.values():
        for flag in flags:
            # Count by severity
            if flag.severity == FlagSeverity.CRITICAL:
                critical_count += 1
            elif flag.severity == FlagSeverity.WARNING:
                warning_count += 1
            else:
                info_count += 1
            
            # Count by type
            flag_type_counts[flag.flag_type] = flag_type_counts.get(flag.flag_type, 0) + 1
            
            # Count by category
            category_counts[flag.category.value] = category_counts.get(flag.category.value, 0) + 1
    
    return {
        'total_flags': total_flags,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'info_count': info_count,
        'flag_type_counts': flag_type_counts,
        'category_counts': category_counts,
        'cells_with_flags': len([f for f in all_flags.values() if f])
    }



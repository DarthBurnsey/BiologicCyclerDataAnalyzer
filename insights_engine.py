"""
Insights Engine for CellScope Dashboard

Rules-based system for generating actionable recommendations
based on battery testing performance data.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class InsightType(Enum):
    """Types of insights the engine can generate."""
    PROMISING_CELL = "promising"
    RAPID_FADE = "warning"
    STALLED_PROJECT = "stalled"
    RECOMMENDATION = "recommendation"
    TREND = "trend"


class InsightSeverity(Enum):
    """Severity levels for insights."""
    SUCCESS = "success"  # Green - good news
    INFO = "info"        # Blue - informational
    WARNING = "warning"  # Yellow - needs attention
    ERROR = "error"      # Red - critical issue


@dataclass
class Insight:
    """Data structure for a single insight."""
    type: InsightType
    severity: InsightSeverity
    title: str
    message: str
    cell_ids: List[str] = None
    project_ids: List[int] = None
    action_items: List[str] = None


def generate_insights(user_id: str, dashboard_data: Dict[str, Any]) -> List[Insight]:
    """
    Main orchestrator for insight generation.
    
    Args:
        user_id: User identifier
        dashboard_data: Dictionary containing:
            - projects: List of project summaries
            - top_cells: DataFrame of top performers
            - stats: Global statistics
    
    Returns:
        List of Insight objects
    """
    insights = []
    
    # Extract data
    projects = dashboard_data.get('projects', [])
    top_cells_df = dashboard_data.get('top_cells')
    stats = dashboard_data.get('stats', {})
    
    # Convert DataFrame to list of dicts if needed
    top_cells = []
    if top_cells_df is not None and not top_cells_df.empty:
        top_cells = top_cells_df.to_dict('records')
    
    # Generate different types of insights
    insights.extend(identify_promising_cells(top_cells))
    insights.extend(flag_rapid_fade(projects))
    insights.extend(detect_stalled_projects(projects))
    insights.extend(suggest_next_experiments(top_cells, projects))
    insights.extend(compare_formulation_trends(projects))
    
    # Sort by severity (errors first, then warnings, then success)
    severity_order = {
        InsightSeverity.ERROR: 0,
        InsightSeverity.WARNING: 1,
        InsightSeverity.INFO: 2,
        InsightSeverity.SUCCESS: 3
    }
    insights.sort(key=lambda x: severity_order[x.severity])
    
    return insights


def identify_promising_cells(top_cells: List[Dict], retention_threshold: float = 90.0) -> List[Insight]:
    """
    Flag cells with exceptional performance for further investigation.
    """
    insights = []
    
    if not top_cells:
        return insights
    
    # Check top performers
    for cell in top_cells:
        retention_pct = cell.get('retention_pct', 0)
        cycles_tested = cell.get('cycles_tested', 0)
        cell_id = cell.get('cell_id', 'Unknown')
        project_name = cell.get('project_name', 'Unknown')
        project_id = cell.get('project_id')
        
        if retention_pct >= retention_threshold:
            if cycles_tested >= 200:
                insights.append(Insight(
                    type=InsightType.PROMISING_CELL,
                    severity=InsightSeverity.SUCCESS,
                    title=f"🌟 Exceptional Cell: {cell_id}",
                    message=(
                        f"Cell **{cell_id}** in project **{project_name}** "
                        f"shows outstanding performance with **{retention_pct:.1f}% retention** "
                        f"at {cycles_tested} cycles. This exceeds the target threshold "
                        f"significantly."
                    ),
                    cell_ids=[cell_id],
                    project_ids=[project_id] if project_id else None,
                    action_items=[
                        "Consider replicating this formulation for validation",
                        "Scale up to larger cell format for commercial evaluation",
                        "Document exact synthesis conditions for reproducibility"
                    ]
                ))
            elif cycles_tested >= 100:
                insights.append(Insight(
                    type=InsightType.PROMISING_CELL,
                    severity=InsightSeverity.SUCCESS,
                    title=f"✨ Promising Cell: {cell_id}",
                    message=(
                        f"Cell **{cell_id}** ({project_name}) maintains "
                        f"**{retention_pct:.1f}% retention** after {cycles_tested} cycles. "
                        f"Continue monitoring for long-term stability."
                    ),
                    cell_ids=[cell_id],
                    project_ids=[project_id] if project_id else None,
                    action_items=[
                        "Extend cycling to 500+ cycles to verify durability",
                        "Test at higher C-rates to assess rate capability"
                    ]
                ))
    
    return insights


def flag_rapid_fade(projects: List[Dict], fade_threshold: float = 2.5) -> List[Insight]:
    """
    Detect projects or cells with concerning degradation rates.
    """
    insights = []
    
    for project in projects:
        avg_fade_rate = project.get('avg_fade_rate', 0)
        project_name = project.get('project_name', 'Unknown')
        project_id = project.get('project_id')
        cell_count = project.get('cell_count', 0)
        
        if avg_fade_rate > fade_threshold and cell_count > 0:
            insights.append(Insight(
                type=InsightType.RAPID_FADE,
                severity=InsightSeverity.ERROR,
                title=f"⚠️ Rapid Fade Detected: {project_name}",
                message=(
                    f"Project **{project_name}** shows high average fade rate of "
                    f"**{avg_fade_rate:.2f}% per 100 cycles**. This indicates "
                    f"accelerated degradation that requires investigation."
                ),
                project_ids=[project_id] if project_id else None,
                action_items=[
                    "Review electrolyte stability - check for gas evolution",
                    "Inspect electrode interfaces for delamination",
                    "Consider reducing upper cutoff voltage to mitigate stress",
                    "Analyze post-mortem cells to identify failure modes"
                ]
            ))
    
    return insights


def detect_stalled_projects(projects: List[Dict], days_threshold: int = 30) -> List[Insight]:
    """
    Identify projects with no recent activity.
    """
    insights = []
    
    for project in projects:
        cell_count = project.get('cell_count', 0)
        project_name = project.get('project_name', 'Unknown')
        project_id = project.get('project_id')
        latest_cycle = project.get('latest_cycle', 0)
        
        if cell_count == 0:
            insights.append(Insight(
                type=InsightType.STALLED_PROJECT,
                severity=InsightSeverity.WARNING,
                title=f"📭 Empty Project: {project_name}",
                message=(
                    f"Project **{project_name}** has no cell data uploaded. "
                    f"Upload experiment data to start tracking performance."
                ),
                project_ids=[project_id] if project_id else None,
                action_items=[
                    "Upload cycling data from completed experiments",
                    "Archive project if no longer active"
                ]
            ))
        elif cell_count < 3 and latest_cycle == 0:
            insights.append(Insight(
                type=InsightType.STALLED_PROJECT,
                severity=InsightSeverity.WARNING,
                title=f"⏸️ Limited Activity: {project_name}",
                message=(
                    f"Project **{project_name}** has only {cell_count} "
                    f"cell(s) with no cycling data. Consider uploading test results."
                ),
                project_ids=[project_id] if project_id else None,
                action_items=[
                    "Upload cycling data from cycler",
                    "Ensure cells have completed formation cycles"
                ]
            ))
    
    return insights


def suggest_next_experiments(top_cells: List[Dict], projects: List[Dict]) -> List[Insight]:
    """
    Generate recommendations for next experiments based on current results.
    """
    insights = []
    
    if not top_cells:
        return insights
    
    # Get the best performing cell
    best_cell = top_cells[0]
    retention_pct = best_cell.get('retention_pct', 0)
    cycles_tested = best_cell.get('cycles_tested', 0)
    cell_id = best_cell.get('cell_id', 'Unknown')
    project_id = best_cell.get('project_id')
    
    # Suggest scaling up if retention is excellent
    if retention_pct >= 92 and cycles_tested >= 200:
        insights.append(Insight(
            type=InsightType.RECOMMENDATION,
            severity=InsightSeverity.INFO,
            title="🚀 Scale-Up Recommendation",
            message=(
                f"Based on exceptional performance of **{cell_id}** "
                f"({retention_pct:.1f}% retention at {cycles_tested} cycles), "
                f"consider advancing to scale-up testing."
            ),
            cell_ids=[cell_id],
            project_ids=[project_id] if project_id else None,
            action_items=[
                "Build pouch cells with same formulation",
                "Test at higher temperatures (45°C+) to evaluate thermal stability",
                "Perform rate capability study (0.5C to 3C)",
                "Initiate safety testing (nail penetration, overcharge)"
            ]
        ))
    
    # Suggest comparison experiments
    if len(top_cells) >= 3:
        top_3_projects = set(c.get('project_name', 'Unknown') for c in top_cells[:3])
        if len(top_3_projects) > 1:
            insights.append(Insight(
                type=InsightType.RECOMMENDATION,
                severity=InsightSeverity.INFO,
                title="🔬 Cross-Project Comparison Opportunity",
                message=(
                    f"Top performers come from {len(top_3_projects)} different projects: "
                    f"{', '.join(top_3_projects)}. Consider a direct comparison study to "
                    f"identify common success factors."
                ),
                action_items=[
                    "Prepare cells with identical test conditions",
                    "Standardize electrolyte and separator across formulations",
                    "Run parallel cycling with same protocol"
                ]
            ))
    
    return insights


def compare_formulation_trends(projects: List[Dict]) -> List[Insight]:
    """
    Analyze formulation patterns across projects (placeholder for future enhancement).
    """
    insights = []
    
    # Placeholder: This would parse formulation data to find correlations
    # Example: "Projects using Graphite 92-95% show 15% better retention than 88-90%"
    
    # For now, provide a generic insight about data collection
    total_projects = len(projects)
    projects_with_cells = sum(1 for p in projects if p.get('cell_count', 0) > 0)
    
    if total_projects > 0 and projects_with_cells / total_projects < 0.5:
        insights.append(Insight(
            type=InsightType.TREND,
            severity=InsightSeverity.INFO,
            title="📊 Data Collection Recommendation",
            message=(
                f"Only {projects_with_cells} of {total_projects} projects have cell data. "
                f"Increasing test coverage will enable more powerful trend analysis and "
                f"formulation optimization insights."
            ),
            action_items=[
                "Prioritize completing tests for active projects",
                "Upload historical data if available"
            ]
        ))
    
    return insights

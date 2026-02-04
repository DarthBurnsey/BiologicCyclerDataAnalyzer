"""
Dashboard Analytics Module for CellScope

Provides data aggregation and analysis functions for the dashboard.
Extracts cycling performance metrics across projects and cells.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from database import get_db_connection, TEST_USER_ID


def get_global_statistics(user_id: str, filter_params: Optional[Dict] = None) -> Dict:
    """
    Aggregate statistics across all projects for a user.
    
    Args:
        user_id: User identifier
        filter_params: Optional filters (project_ids, date_range, min_cycles, etc.)
    
    Returns:
        Dictionary with global stats:
        - total_projects: int
        - total_cells: int
        - most_recent_test: datetime
        - best_retention_pct: float
        - avg_degradation_rate: float (% per 100 cycles)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Build WHERE clause from filters
        where_conditions = ["p.user_id = ?"]
        params = [user_id]
        
        if filter_params:
            if filter_params.get('project_ids'):
                placeholders = ','.join('?' * len(filter_params['project_ids']))
                where_conditions.append(f"p.id IN ({placeholders})")
                params.extend(filter_params['project_ids'])
            
            if filter_params.get('date_range'):
                start_date, end_date = filter_params['date_range']
                where_conditions.append("ce.created_date BETWEEN ? AND ?")
                params.extend([start_date.isoformat(), end_date.isoformat()])
        
        where_clause = " AND ".join(where_conditions)
        
        # Total projects
        cursor.execute(f"""
            SELECT COUNT(DISTINCT p.id)
            FROM projects p
            WHERE p.user_id = ?
        """, (user_id,))
        total_projects = cursor.fetchone()[0]
        
        # Total cells and most recent test
        cursor.execute(f"""
            SELECT COUNT(*), MAX(ce.created_date)
            FROM cell_experiments ce
            JOIN projects p ON ce.project_id = p.id
            WHERE {where_clause}
        """, params)
        result = cursor.fetchone()
        total_cells = result[0] if result[0] else 0
        most_recent = result[1] if result[1] else None
        
        # Get all cells with cycling data to calculate best retention and avg fade
        cursor.execute(f"""
            SELECT ce.data_json
            FROM cell_experiments ce
            JOIN projects p ON ce.project_id = p.id
            WHERE {where_clause} AND ce.data_json IS NOT NULL
        """, params)
        
        all_retentions = []
        all_fade_rates = []
        
        for (data_json_str,) in cursor.fetchall():
            try:
                data = json.loads(data_json_str)
                cells = data.get('cells', [])
                
                for cell in cells:
                    if cell.get('excluded', False):
                        continue
                    
                    # Parse cycling data
                    cell_data_json = cell.get('data_json')
                    if cell_data_json:
                        df = pd.read_json(cell_data_json)
                        
                        # Calculate retention
                        retention = calculate_retention_percent(df)
                        if retention is not None:
                            all_retentions.append(retention)
                        
                        # Calculate fade rate
                        fade_rate = calculate_fade_rate(df)
                        if fade_rate is not None:
                            all_fade_rates.append(fade_rate)
            except (json.JSONDecodeError, Exception):
                continue
        
        best_retention = max(all_retentions) if all_retentions else 0.0
        avg_fade_rate = np.mean(all_fade_rates) if all_fade_rates else 0.0
        
        return {
            'total_projects': total_projects,
            'total_cells': total_cells,
            'most_recent_test': most_recent,
            'best_retention_pct': round(best_retention, 2),
            'avg_degradation_rate': round(avg_fade_rate, 3)
        }


def get_project_summaries(user_id: str, filter_params: Optional[Dict] = None) -> List[Dict]:
    """
    Get summary statistics for each project.
    
    Returns:
        List of project summary dicts:
        - project_id: int
        - project_name: str
        - project_type: str
        - cell_count: int
        - latest_cycle: int
        - best_cell_id: str
        - best_retention_pct: float
        - status: str ('good', 'medium', 'bad')
        - avg_fade_rate: float
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get all projects
        cursor.execute("""
            SELECT id, name, project_type
            FROM projects
            WHERE user_id = ?
            ORDER BY last_modified DESC
        """, (user_id,))
        
        projects = cursor.fetchall()
        summaries = []
        
        for project_id, project_name, project_type in projects:
            # Apply project filter if specified
            if filter_params and filter_params.get('project_ids'):
                if project_id not in filter_params['project_ids']:
                    continue
            
            # Get all experiments for this project
            cursor.execute("""
                SELECT data_json, created_date
                FROM cell_experiments
                WHERE project_id = ?
            """, (project_id,))
            
            experiments = cursor.fetchall()
            
            cell_count = 0
            max_cycles = 0
            best_cell_id = None
            best_retention = 0.0
            all_fade_rates = []
            
            for data_json_str, created_date in experiments:
                # Apply date filter
                if filter_params and filter_params.get('date_range'):
                    start_date, end_date = filter_params['date_range']
                    exp_date = datetime.fromisoformat(created_date) if created_date else None
                    if exp_date:
                        if exp_date < start_date or exp_date > end_date:
                            continue
                
                try:
                    data = json.loads(data_json_str)
                    cells = data.get('cells', [])
                    
                    for cell in cells:
                        if cell.get('excluded', False):
                            continue
                        
                        cell_count += 1
                        cell_data_json = cell.get('data_json')
                        
                        if cell_data_json:
                            df = pd.read_json(cell_data_json)
                            
                            # Get max cycle
                            cycle_col = 'Cycle' if 'Cycle' in df.columns else 'Cycle number'
                            if cycle_col in df.columns:
                                cell_max_cycle = df[cycle_col].max()
                                max_cycles = max(max_cycles, cell_max_cycle)
                            
                            # Check retention
                            retention = calculate_retention_percent(df)
                            if retention and retention > best_retention:
                                best_retention = retention
                                best_cell_id = cell.get('test_number', cell.get('cell_name', 'Unknown'))
                            
                            # Collect fade rates
                            fade_rate = calculate_fade_rate(df)
                            if fade_rate is not None:
                                all_fade_rates.append(fade_rate)
                
                except (json.JSONDecodeError, Exception):
                    continue
            
            # Determine status based on average fade rate
            avg_fade = np.mean(all_fade_rates) if all_fade_rates else 0.0
            if avg_fade < 1.0:
                status = 'good'
            elif avg_fade < 2.0:
                status = 'medium'
            else:
                status = 'bad'
            
            summaries.append({
                'project_id': project_id,
                'project_name': project_name,
                'project_type': project_type,
                'cell_count': cell_count,
                'latest_cycle': max_cycles,
                'best_cell_id': best_cell_id or 'N/A',
                'best_retention_pct': round(best_retention, 2),
                'status': status,
                'avg_fade_rate': round(avg_fade, 3)
            })
        
        return summaries


def get_top_performers(
    user_id: str,
    metric: str = 'retention',
    top_n: int = 5,
    min_cycles: int = 100,
    filter_params: Optional[Dict] = None
) -> pd.DataFrame:
    """
    Get top performing cells across all projects.
    
    Args:
        user_id: User identifier
        metric: 'retention', 'fade_rate', or 'efficiency'
        top_n: Number of top cells to return
        min_cycles: Minimum cycle count to be considered
        filter_params: Optional filters
    
    Returns:
        DataFrame with columns:
        - cell_id: str
        - project_name: str
        - project_id: int
        - initial_capacity: float
        - current_capacity: float
        - retention_pct: float
        - fade_rate: float
        - cycles_tested: int
        - avg_efficiency: float (optional)
    """
    all_cells = []
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Build WHERE clause
        where_conditions = ["p.user_id = ?"]
        params = [user_id]
        
        if filter_params and filter_params.get('project_ids'):
            placeholders = ','.join('?' * len(filter_params['project_ids']))
            where_conditions.append(f"p.id IN ({placeholders})")
            params.extend(filter_params['project_ids'])
        
        where_clause = " AND ".join(where_conditions)
        
        cursor.execute(f"""
            SELECT p.id, p.name, ce.data_json
            FROM cell_experiments ce
            JOIN projects p ON ce.project_id = p.id
            WHERE {where_clause} AND ce.data_json IS NOT NULL
        """, params)
        
        for project_id, project_name, data_json_str in cursor.fetchall():
            try:
                data = json.loads(data_json_str)
                cells = data.get('cells', [])
                
                for cell in cells:
                    if cell.get('excluded', False):
                        continue
                    
                    cell_data_json = cell.get('data_json')
                    if not cell_data_json:
                        continue
                    
                    df = pd.read_json(cell_data_json)
                    
                    # Check minimum cycles
                    cycle_col = 'Cycle' if 'Cycle' in df.columns else 'Cycle number'
                    if cycle_col not in df.columns:
                        continue
                    
                    cycles_tested = df[cycle_col].max()
                    if cycles_tested < min_cycles:
                        continue
                    
                    # Calculate metrics
                    retention = calculate_retention_percent(df)
                    fade_rate = calculate_fade_rate(df)
                    initial_cap, current_cap = get_capacity_values(df)
                    avg_eff = calculate_avg_efficiency(df)
                    
                    cell_id = cell.get('test_number', cell.get('cell_name', 'Unknown'))
                    
                    all_cells.append({
                        'cell_id': cell_id,
                        'project_name': project_name,
                        'project_id': project_id,
                        'initial_capacity': initial_cap,
                        'current_capacity': current_cap,
                        'retention_pct': retention if retention else 0.0,
                        'fade_rate': fade_rate if fade_rate else 0.0,
                        'cycles_tested': cycles_tested,
                        'avg_efficiency': avg_eff if avg_eff else 0.0
                    })
            
            except (json.JSONDecodeError, Exception):
                continue
    
    if not all_cells:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_cells)
    
    # Sort by specified metric
    if metric == 'retention':
        df = df.sort_values('retention_pct', ascending=False)
    elif metric == 'fade_rate':
        df = df.sort_values('fade_rate', ascending=True)
    elif metric == 'efficiency':
        df = df.sort_values('avg_efficiency', ascending=False)
    
    return df.head(top_n)


def calculate_retention_percent(df: pd.DataFrame) -> Optional[float]:
    """Calculate capacity retention percentage."""
    # Handle multiple column naming conventions
    cap_col = None
    if 'Qdis' in df.columns:
        cap_col = 'Qdis'
    elif 'Q discharge (mA.h)' in df.columns:
        cap_col = 'Q discharge (mA.h)'
    elif 'Q Dis (mAh/g)' in df.columns:
        cap_col = 'Q Dis (mAh/g)'
    elif 'discharge_capacity' in df.columns:
        cap_col = 'discharge_capacity'
    
    if cap_col is None:
        return None
    
    # Handle cycle column naming
    cycle_col = None
    if 'Cycle' in df.columns:
        cycle_col = 'Cycle'
    elif 'Cycle number' in df.columns:
        cycle_col = 'Cycle number'
    
    # Get initial capacity (first non-zero value, skip formation cycles if possible)
    valid_caps = df[df[cap_col] > 0][cap_col]
    if len(valid_caps) < 2:
        return None
    
    # Use capacity at cycle 5-10 as "initial" to skip formation variability
    if cycle_col is not None:
        initial_df = df[(df[cycle_col] >= 5) & (df[cycle_col] <= 10) & (df[cap_col] > 0)]
        if not initial_df.empty:
            initial_capacity = initial_df[cap_col].mean()
        else:
            initial_capacity = valid_caps.iloc[0]
    else:
        initial_capacity = valid_caps.iloc[0]
    
    # Get latest capacity
    current_capacity = valid_caps.iloc[-1]
    
    retention = (current_capacity / initial_capacity) * 100
    return round(retention, 2)


def calculate_fade_rate(df: pd.DataFrame) -> Optional[float]:
    """
    Calculate capacity fade rate in % per 100 cycles using linear regression.
    """
    # Handle multiple column naming conventions
    cap_col = None
    if 'Qdis' in df.columns:
        cap_col = 'Qdis'
    elif 'Q discharge (mA.h)' in df.columns:
        cap_col = 'Q discharge (mA.h)'
    elif 'Q Dis (mAh/g)' in df.columns:
        cap_col = 'Q Dis (mAh/g)'
    elif 'discharge_capacity' in df.columns:
        cap_col = 'discharge_capacity'
    
    if cap_col is None:
        return None
    
    # Handle cycle column naming
    cycle_col = None
    if 'Cycle' in df.columns:
        cycle_col = 'Cycle'
    elif 'Cycle number' in df.columns:
        cycle_col = 'Cycle number'
    
    if cycle_col is None:
        return None
    
    # Filter valid data
    valid_data = df[(df[cap_col] > 0) & (df[cycle_col] > 0)].copy()
    if len(valid_data) < 10:
        return None
    
    # Normalize to initial capacity
    initial_cap = valid_data[cap_col].iloc[0]
    valid_data['retention'] = (valid_data[cap_col] / initial_cap) * 100
    
    # Linear regression
    try:
        from scipy.stats import linregress
        slope, intercept, r_value, p_value, std_err = linregress(
            valid_data[cycle_col], valid_data['retention']
        )
        
        # Convert slope to % fade per 100 cycles (negative of slope)
        fade_per_100_cycles = -slope * 100
        
        return round(fade_per_100_cycles, 3)
    except:
        # Fallback: simple first-last calculation
        first_retention = valid_data['retention'].iloc[0]
        last_retention = valid_data['retention'].iloc[-1]
        cycles = valid_data[cycle_col].iloc[-1] - valid_data[cycle_col].iloc[0]
        
        if cycles > 0:
            fade_per_100_cycles = ((first_retention - last_retention) / cycles) * 100
            return round(fade_per_100_cycles, 3)
    
    return None


def get_capacity_values(df: pd.DataFrame) -> Tuple[float, float]:
    """Get initial and current capacity values."""
    # Handle multiple column naming conventions
    cap_col = None
    if 'Qdis' in df.columns:
        cap_col = 'Qdis'
    elif 'Q discharge (mA.h)' in df.columns:
        cap_col = 'Q discharge (mA.h)'
    elif 'Q Dis (mAh/g)' in df.columns:
        cap_col = 'Q Dis (mAh/g)'
    elif 'discharge_capacity' in df.columns:
        cap_col = 'discharge_capacity'
    
    if cap_col is None:
        return 0.0, 0.0
    
    valid_caps = df[df[cap_col] > 0][cap_col]
    if len(valid_caps) < 2:
        return 0.0, 0.0
    
    initial = valid_caps.iloc[0]
    current = valid_caps.iloc[-1]
    
    return round(initial, 2), round(current, 2)


def calculate_avg_efficiency(df: pd.DataFrame) -> Optional[float]:
    """Calculate average coulombic efficiency."""
    # Handle multiple column naming conventions
    eff_col = None
    if 'Efficiency' in df.columns:
        eff_col = 'Efficiency'
    elif 'Efficiency (-)' in df.columns:
        eff_col = 'Efficiency (-)'
    elif 'coulombic_efficiency' in df.columns:
        eff_col = 'coulombic_efficiency'
    
    if eff_col is None:
        return None
    
    valid_eff = df[(df[eff_col] > 0) & (df[eff_col] <= 100)][eff_col]
    if len(valid_eff) == 0:
        return None
    
    return round(valid_eff.mean(), 3)


def get_recent_activity(user_id: str, days: int = 30) -> List[Dict]:
    """
    Get timeline of recent experiment uploads.
    
    Returns:
        List of activity dicts with date and count
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT DATE(ce.created_date) as date, COUNT(*) as count
            FROM cell_experiments ce
            JOIN projects p ON ce.project_id = p.id
            WHERE p.user_id = ? AND ce.created_date >= ?
            GROUP BY DATE(ce.created_date)
            ORDER BY date DESC
        """, (user_id, cutoff_date))
        
        return [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]


def get_stalled_projects(user_id: str, days_threshold: int = 30) -> List[Dict]:
    """
    Identify projects with no recent activity.
    
    Returns:
        List of project dicts with id, name, and days_since_update
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days_threshold)).isoformat()
        
        cursor.execute("""
            SELECT p.id, p.name, MAX(ce.created_date) as last_activity
            FROM projects p
            LEFT JOIN cell_experiments ce ON p.id = ce.project_id
            WHERE p.user_id = ?
            GROUP BY p.id, p.name
            HAVING last_activity < ? OR last_activity IS NULL
            ORDER BY last_activity ASC
        """, (user_id, cutoff_date))
        
        stalled = []
        for project_id, project_name, last_activity in cursor.fetchall():
            if last_activity:
                days_since = (datetime.now() - datetime.fromisoformat(last_activity)).days
            else:
                days_since = 9999  # Never had data
            
            stalled.append({
                'project_id': project_id,
                'project_name': project_name,
                'days_since_update': days_since
            })
        
        return stalled


def get_cells_with_cycle_data(user_id: str, min_cycles: int = 0, filter_params: Optional[Dict] = None) -> List[Dict]:
    """
    Extract all cells with cycling data for visualization.
    
    Returns:
        List of cell data dicts with parsed DataFrames
    """
    all_cells = []
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Build WHERE clause
        where_conditions = ["p.user_id = ?"]
        params = [user_id]
        
        if filter_params and filter_params.get('project_ids'):
            placeholders = ','.join('?' * len(filter_params['project_ids']))
            where_conditions.append(f"p.id IN ({placeholders})")
            params.extend(filter_params['project_ids'])
        
        where_clause = " AND ".join(where_conditions)
        
        cursor.execute(f"""
            SELECT p.id, p.name, ce.data_json
            FROM cell_experiments ce
            JOIN projects p ON ce.project_id = p.id
            WHERE {where_clause} AND ce.data_json IS NOT NULL
        """, params)
        
        for project_id, project_name, data_json_str in cursor.fetchall():
            try:
                data = json.loads(data_json_str)
                cells = data.get('cells', [])
                
                for cell in cells:
                    if cell.get('excluded', False):
                        continue
                    
                    cell_data_json = cell.get('data_json')
                    if not cell_data_json:
                        continue
                    
                    df = pd.read_json(cell_data_json)
                    
                    # Check minimum cycles
                    cycle_col = 'Cycle' if 'Cycle' in df.columns else 'Cycle number'
                    if cycle_col in df.columns:
                        max_cycle = df[cycle_col].max()
                        if max_cycle < min_cycles:
                            continue
                    
                    cell_id = cell.get('test_number', cell.get('cell_name', 'Unknown'))
                    
                    all_cells.append({
                        'cell_id': cell_id,
                        'project_name': project_name,
                        'project_id': project_id,
                        'data_json': cell_data_json,
                        'formulation': cell.get('formulation', [])
                    })
            
            except (json.JSONDecodeError, Exception):
                continue
    
    return all_cells

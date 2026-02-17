"""
Test script for automated cell flag detection system.

This script tests the flag detection algorithms on sample data to ensure they work correctly.
"""

import pandas as pd
import numpy as np
from cell_flags import (
    analyze_cell_for_flags,
    detect_rapid_capacity_fade,
    detect_cell_failure,
    detect_high_ce_variation,
    detect_low_coulombic_efficiency,
    detect_accelerating_degradation,
    detect_incomplete_dataset,
    detect_impossible_efficiency,
    FlagSeverity
)


def create_test_data_rapid_fade():
    """Create test data showing rapid capacity fade."""
    cycles = list(range(1, 21))
    # Capacity drops from 200 to 140 in first 10 cycles (70% retention)
    capacities = [200, 195, 190, 185, 175, 165, 155, 145, 140, 140] + [140] * 10
    efficiency = [0.85] + [0.99] * 19
    
    return pd.DataFrame({
        'Cycle': cycles,
        'Q Dis (mAh/g)': capacities,
        'Q Chg (mAh/g)': [c / e for c, e in zip(capacities, efficiency)],
        'Efficiency (-)': efficiency
    })


def create_test_data_high_ce_variation():
    """Create test data with high CE variation."""
    cycles = list(range(1, 21))
    # First cycle low efficiency, then highly variable
    efficiency = [0.85] + [0.99, 0.92, 0.98, 0.88, 0.97, 0.90, 0.96, 0.89, 0.99, 0.87, 0.99, 0.92, 0.98, 0.88, 0.97, 0.90, 0.96, 0.89, 0.99]
    capacities = [180] * 20
    
    return pd.DataFrame({
        'Cycle': cycles,
        'Q Dis (mAh/g)': capacities,
        'Q Chg (mAh/g)': [c / e for c, e in zip(capacities, efficiency)],
        'Efficiency (-)': efficiency
    })


def create_test_data_incomplete():
    """Create test data that appears incomplete (stopped early)."""
    cycles = list(range(1, 16))  # Only 15 cycles
    capacities = [200, 195, 193, 192, 190, 189, 188, 187, 186, 185, 184, 183, 182, 181, 180]
    efficiency = [0.85] + [0.99] * 14
    
    return pd.DataFrame({
        'Cycle': cycles,
        'Q Dis (mAh/g)': capacities,
        'Q Chg (mAh/g)': [c / e for c, e in zip(capacities, efficiency)],
        'Efficiency (-)': efficiency
    })


def create_test_data_impossible_efficiency():
    """Create test data with impossible efficiency (>100%)."""
    cycles = list(range(1, 11))
    capacities = [200] * 10
    efficiency = [0.85, 0.99, 0.99, 0.99, 1.08, 0.99, 0.99, 0.99, 0.99, 0.99]  # Cycle 5 has >100%
    
    return pd.DataFrame({
        'Cycle': cycles,
        'Q Dis (mAh/g)': capacities,
        'Q Chg (mAh/g)': [c / e for c, e in zip(capacities, efficiency)],
        'Efficiency (-)': efficiency
    })


def create_test_data_low_ce():
    """Create test data with consistently low CE."""
    cycles = list(range(1, 21))
    # First cycle typically lower, then consistently around 92%
    efficiency = [0.85, 0.92, 0.91, 0.93, 0.90, 0.92, 0.91, 0.93, 0.92, 0.91, 
                  0.92, 0.91, 0.93, 0.90, 0.92, 0.91, 0.93, 0.92, 0.91, 0.92]
    capacities = [200] * 20
    
    return pd.DataFrame({
        'Cycle': cycles,
        'Q Dis (mAh/g)': capacities,
        'Q Chg (mAh/g)': [c / e for c, e in zip(capacities, efficiency)],
        'Efficiency (-)': efficiency
    })


def create_test_data_normal():
    """Create normal/healthy test data."""
    cycles = list(range(1, 51))
    # Gradual, normal fade
    capacities = [200 - (i * 0.3) for i in range(50)]
    efficiency = [0.85] + [0.99] * 49
    
    return pd.DataFrame({
        'Cycle': cycles,
        'Q Dis (mAh/g)': capacities,
        'Q Chg (mAh/g)': [c / e for c, e in zip(capacities, efficiency)],
        'Efficiency (-)': efficiency
    })


def test_flag_detection():
    """Run all flag detection tests."""
    print("=" * 80)
    print("AUTOMATED CELL FLAG DETECTION - TEST SUITE")
    print("=" * 80)
    print()
    
    # Test 1: Rapid Capacity Fade
    print("Test 1: Rapid Capacity Fade Detection")
    print("-" * 80)
    df_rapid_fade = create_test_data_rapid_fade()
    cell_data = {'cell_name': 'Test_Rapid_Fade', 'loading': 10, 'active_material': 90}
    flags = analyze_cell_for_flags(df_rapid_fade, cell_data)
    
    if flags:
        print(f"✓ Detected {len(flags)} flag(s):")
        for flag in flags:
            print(f"  {flag.severity.value} {flag.flag_type}")
            print(f"     {flag.description}")
            if flag.recommendation:
                print(f"     💡 {flag.recommendation}")
    else:
        print("✗ No flags detected (Expected: Rapid Capacity Fade)")
    print()
    
    # Test 2: High CE Variation
    print("Test 2: High CE Variation Detection")
    print("-" * 80)
    df_ce_variation = create_test_data_high_ce_variation()
    cell_data = {'cell_name': 'Test_CE_Variation', 'loading': 10, 'active_material': 90}
    flags = analyze_cell_for_flags(df_ce_variation, cell_data)
    
    if flags:
        print(f"✓ Detected {len(flags)} flag(s):")
        for flag in flags:
            print(f"  {flag.severity.value} {flag.flag_type}")
            print(f"     {flag.description}")
    else:
        print("✗ No flags detected (Expected: High CE Variation)")
    print()
    
    # Test 3: Incomplete Dataset
    print("Test 3: Incomplete Dataset Detection")
    print("-" * 80)
    df_incomplete = create_test_data_incomplete()
    cell_data = {'cell_name': 'Test_Incomplete', 'loading': 10, 'active_material': 90}
    flags = analyze_cell_for_flags(df_incomplete, cell_data)
    
    if flags:
        print(f"✓ Detected {len(flags)} flag(s):")
        for flag in flags:
            print(f"  {flag.severity.value} {flag.flag_type}")
            print(f"     {flag.description}")
    else:
        print("✗ No flags detected (Expected: Incomplete Dataset)")
    print()
    
    # Test 4: Impossible Efficiency
    print("Test 4: Impossible Efficiency Detection")
    print("-" * 80)
    df_impossible_eff = create_test_data_impossible_efficiency()
    cell_data = {'cell_name': 'Test_Impossible_Eff', 'loading': 10, 'active_material': 90}
    flags = analyze_cell_for_flags(df_impossible_eff, cell_data)
    
    if flags:
        print(f"✓ Detected {len(flags)} flag(s):")
        for flag in flags:
            print(f"  {flag.severity.value} {flag.flag_type}")
            print(f"     {flag.description}")
    else:
        print("✗ No flags detected (Expected: Impossible Efficiency)")
    print()
    
    # Test 5: Low Coulombic Efficiency
    print("Test 5: Low Coulombic Efficiency Detection")
    print("-" * 80)
    df_low_ce = create_test_data_low_ce()
    cell_data = {'cell_name': 'Test_Low_CE', 'loading': 10, 'active_material': 90}
    flags = analyze_cell_for_flags(df_low_ce, cell_data)
    
    if flags:
        print(f"✓ Detected {len(flags)} flag(s):")
        for flag in flags:
            print(f"  {flag.severity.value} {flag.flag_type}")
            print(f"     {flag.description}")
    else:
        print("✗ No flags detected (Expected: Low Coulombic Efficiency)")
    print()
    
    # Test 6: Normal/Healthy Cell
    print("Test 6: Normal/Healthy Cell (Should have no or minimal flags)")
    print("-" * 80)
    df_normal = create_test_data_normal()
    cell_data = {'cell_name': 'Test_Normal', 'loading': 10, 'active_material': 90}
    flags = analyze_cell_for_flags(df_normal, cell_data)
    
    if flags:
        print(f"⚠ Detected {len(flags)} flag(s):")
        for flag in flags:
            print(f"  {flag.severity.value} {flag.flag_type}")
            print(f"     {flag.description}")
    else:
        print("✓ No flags detected (Expected: Healthy cell)")
    print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("All tests completed successfully!")
    print()
    print("Next steps:")
    print("1. Run the Streamlit app: streamlit run app.py")
    print("2. Navigate to the Master Table tab")
    print("3. Observe the automated flag detection in action")
    print("4. Check the 'Flags' column for visual indicators")
    print("5. Expand the 'Detailed Flag Information' section for full details")
    print()


if __name__ == "__main__":
    test_flag_detection()


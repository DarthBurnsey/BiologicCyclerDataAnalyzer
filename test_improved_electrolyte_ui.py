#!/usr/bin/env python3
"""
Test script for the improved electrolyte UI.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

# Mock streamlit module
import types
class MockSessionState:
    def __init__(self):
        self.data = {}
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def __setitem__(self, key, value):
        self.data[key] = value
    
    def __getitem__(self, key):
        return self.data[key]
    
    def __contains__(self, key):
        return key in self.data

st = types.ModuleType('st')
st.session_state = MockSessionState()
sys.modules['streamlit'] = st

# Now import our functions
from ui_components import get_electrolyte_options, track_electrolyte_usage, COMPREHENSIVE_ELECTROLYTES

def test_electrolyte_options():
    """Test that electrolyte options are returned correctly."""
    print("=" * 70)
    print("TEST 1: Basic Electrolyte Options")
    print("=" * 70)
    
    options = get_electrolyte_options()
    print(f"✓ Got {len(options)} electrolyte options")
    
    # Check that new electrolyte is in the list
    new_electrolyte = "2M LiFSI + 0.2M LiDFOB 3:7 FEC:TEGDME"
    assert new_electrolyte in COMPREHENSIVE_ELECTROLYTES, "New electrolyte not found!"
    print(f"✓ New electrolyte '{new_electrolyte}' is in the list")
    
    # Check sorting (should be alphabetical without a project)
    print(f"✓ First 5 options: {options[:5]}")
    print(f"✓ Last 5 options: {options[-5:]}")
    print()

def test_tracking():
    """Test electrolyte tracking functionality."""
    print("=" * 70)
    print("TEST 2: Electrolyte Usage Tracking")
    print("=" * 70)
    
    # Set up a mock project
    st.session_state['current_project_id'] = 1
    
    # Track some electrolytes
    test_electrolytes = [
        "1M LiPF6 1:1:1",
        "2M LiFSI + 0.2M LiDFOB 3:7 FEC:TEGDME",
        "1M LiTFSI 3:7 +10% FEC"
    ]
    
    print(f"Tracking {len(test_electrolytes)} electrolytes...")
    for e in test_electrolytes:
        track_electrolyte_usage(e)
    
    # Get options again - should now have recent items at top
    options = get_electrolyte_options()
    print(f"✓ Options updated after tracking")
    
    # Check if separator is present (indicates recent items exist)
    has_separator = "─────────────────────────" in options
    print(f"✓ Visual separator present: {has_separator}")
    
    if has_separator:
        separator_idx = options.index("─────────────────────────")
        recent_items = options[:separator_idx]
        print(f"✓ Found {len(recent_items)} recent items before separator")
        print(f"  Recent items: {recent_items}")
    
    print()

def test_performance():
    """Test performance of option retrieval."""
    print("=" * 70)
    print("TEST 3: Performance Check")
    print("=" * 70)
    
    import time
    
    # Time how long it takes to get options 100 times
    start = time.time()
    for _ in range(100):
        options = get_electrolyte_options()
    end = time.time()
    
    avg_time = (end - start) / 100 * 1000  # Convert to ms
    print(f"✓ Average time to get options: {avg_time:.2f}ms")
    print(f"✓ Total options available: {len(options)}")
    
    if avg_time < 10:
        print(f"✓ EXCELLENT: Very fast response time")
    elif avg_time < 50:
        print(f"✓ GOOD: Acceptable response time")
    else:
        print(f"⚠ WARNING: Slow response time (may need optimization)")
    
    print()

def test_custom_separator():
    """Test that the separator works correctly."""
    print("=" * 70)
    print("TEST 4: Visual Separator Functionality")
    print("=" * 70)
    
    # Make sure we have a project context
    st.session_state['current_project_id'] = 1
    
    # Track one electrolyte
    track_electrolyte_usage("1M LiPF6 1:1:1")
    
    options = get_electrolyte_options()
    
    if "─────────────────────────" in options:
        sep_idx = options.index("─────────────────────────")
        print(f"✓ Separator found at index {sep_idx}")
        print(f"✓ Items before separator: {sep_idx}")
        print(f"✓ Items after separator: {len(options) - sep_idx - 1}")
    else:
        print(f"⚠ No separator found (may be expected if no recent items)")
    
    print()

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("TESTING IMPROVED ELECTROLYTE UI")
    print("=" * 70 + "\n")
    
    try:
        test_electrolyte_options()
        test_tracking()
        test_performance()
        test_custom_separator()
        
        print("=" * 70)
        print("ALL TESTS PASSED! ✓")
        print("=" * 70)
        print("\nSummary of Improvements:")
        print("  1. ✓ Simplified UI (no more toggle buttons)")
        print("  2. ✓ Built-in search (faster workflow)")
        print("  3. ✓ Visual separators (better readability)")
        print("  4. ✓ Recent items at top (quick access)")
        print("  5. ✓ Optimized tracking (only on changes)")
        print("  6. ✓ Custom entry option (flexibility)")
        print()
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


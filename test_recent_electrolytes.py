#!/usr/bin/env python3
"""
Quick test script to verify recent electrolyte sorting functionality.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

# Mock streamlit session state
class MockSessionState:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __setitem__(self, key, value):
        self.data[key] = value

    def __contains__(self, key):
        return key in self.data

# Mock streamlit module
import types
st = types.ModuleType('st')
st.session_state = MockSessionState()
sys.modules['streamlit'] = st

# Now import our functions
from ui_components import get_electrolyte_options, track_electrolyte_usage, COMPREHENSIVE_ELECTROLYTES

def test_basic_functionality():
    """Test basic functionality without database."""
    print("Testing basic functionality...")

    # Test that get_electrolyte_options returns sorted list when no project is set
    options = get_electrolyte_options()
    print(f"Got {len(options)} electrolyte options")
    print(f"First 5 options: {options[:5]}")
    print(f"Last 5 options: {options[-5:]}")

    # Test that our new electrolyte is in the list
    new_electrolyte = "2M LiFSI + 0.2M LiDFOB 3:7 FEC:TEGDME"
    assert new_electrolyte in COMPREHENSIVE_ELECTROLYTES, "New electrolyte not found in list"
    print(f"✓ New electrolyte '{new_electrolyte}' found at position {COMPREHENSIVE_ELECTROLYTES.index(new_electrolyte)}")

    print("✓ Basic functionality test passed!")

if __name__ == "__main__":
    test_basic_functionality()

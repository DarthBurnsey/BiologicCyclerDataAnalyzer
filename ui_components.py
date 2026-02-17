# ui_components.py
import streamlit as st
from typing import List, Dict, Any, Tuple
import pandas as pd
import uuid
import numpy as np
import math

def int_to_roman(num: int) -> str:
    """Convert an integer to lowercase roman numeral."""
    val = [
        1000, 900, 500, 400,
        100, 90, 50, 40,
        10, 9, 5, 4,
        1
    ]
    syms = [
        'm', 'cm', 'd', 'cd',
        'c', 'xc', 'l', 'xl',
        'x', 'ix', 'v', 'iv',
        'i'
    ]
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syms[i]
            num -= val[i]
        i += 1
    return roman_num

# Comprehensive Separator Database
COMPREHENSIVE_SEPARATORS = [
    # Original 4 separators
    "2+12+2 CCS",
    "25um PP", 
    "CellPET",
    "GA - Glass Fiber",
    
    # Additional 10 common lithium-ion battery separators
    "PE (Polyethylene) 20μm",
    "PP (Polypropylene) 25μm", 
    "PP/PE/PP Trilayer",
    "PE/PP Bilayer",
    "Celgard 2325 (PP/PE/PP)",
    "Celgard 2400 (PP)",
    "Celgard 2500 (PP)",
    "Ceramic-coated PE",
    "UHMWPE (Ultra-high Molecular Weight PE)",
    "Aramid-coated PE",
    
    # Additional common separators for completeness
    "PE (Polyethylene) 16μm",
    "PE (Polyethylene) 25μm",
    "PP (Polypropylene) 20μm",
    "PP (Polypropylene) 30μm",
    "PP/PE/PP Trilayer 20μm",
    "PP/PE/PP Trilayer 25μm",
    "PE/PP Bilayer 20μm",
    "PE/PP Bilayer 25μm",
    "Celgard 2320 (PP/PE/PP)",
    "Celgard 2340 (PP/PE/PP)",
    "Celgard 2400 (PP) 25μm",
    "Celgard 2500 (PP) 20μm",
    "Ceramic-coated PE 20μm",
    "Ceramic-coated PE 25μm",
    "Al2O3-coated PE",
    "SiO2-coated PE",
    "TiO2-coated PE",
    "UHMWPE 20μm",
    "UHMWPE 25μm",
    "Aramid-coated PE 20μm",
    "Aramid-coated PE 25μm",
    
    # Specialized separators
    "Glass Fiber Separator",
    "Cellulose Separator",
    "Polyimide Separator",
    "Polyamide Separator",
    "PVDF Separator",
    "PAN Separator",
    "PMMA Separator",
    
    # Custom/Experimental separators
    "Custom Separator",
    "Experimental Separator",
    "Research Separator",
    "Proprietary Separator"
]

# Comprehensive Electrolyte Database
COMPREHENSIVE_ELECTROLYTES = [
    # Standard Electrolytes
    "1M LiPF6 1:1:1",
    "1M LiTFSI 3:7 +10% FEC",
    "1M LiPF6 EC:DMC (1:1)",
    "1M LiPF6 EC:DMC:EMC (1:1:1)",
    "1M LiPF6 EC:DMC:EMC (3:3:4)",
    "1M LiPF6 EC:DMC:EMC (1:1:1) + 2% VC",
    "1M LiPF6 EC:EMC:DMC 1:1:1 + 2% LiDFOB",
    "1M LiPF6 EC:DMC:EMC (1:1:1) + 5% FEC",
    "1M LiPF6 EC:DMC:EMC (1:1:1) + 10% FEC",
    "1M LiPF6 EC:DMC:EMC (1:1:1) + 2% VC + 5% FEC",
    
    # Advanced Electrolytes
    "2M LiFSI + 0.2M LiDFOB 3:7 FEC:TEGDME",
    "1M LiTFSI EC:DMC:EMC (1:1:1)",
    "1M LiTFSI EC:DMC:EMC (3:7) + 10% FEC",
    "1M LiTFSI EC:DMC:EMC (3:7) + 5% FEC",
    "1M LiTFSI EC:DMC:EMC (3:7) + 2% VC",
    "1M LiTFSI EC:DMC:EMC (3:7) + 2% VC + 5% FEC",
    "1M LiTFSI DOL:DME (1:1) + 1% LiNO3",
    "1M LiTFSI DOL:DME (1:1) + 2% LiNO3",
    "1M LiTFSI DOL:DME (1:1) + 1% LiNO3 + 1% LiDFOB",
    
    # Hybrid Dual Salt Electrolytes
    "Hybrid Dual Salt (HDE)",
    "0.5M LiPF6 + 0.5M LiTFSI EC:DMC:EMC (1:1:1)",
    "0.5M LiPF6 + 0.5M LiTFSI EC:DMC:EMC (3:7) + 10% FEC",
    "0.5M LiPF6 + 0.5M LiFSI EC:DMC:EMC (1:1:1)",
    "0.5M LiPF6 + 0.5M LiFSI EC:DMC:EMC (3:7) + 10% FEC",
    "0.5M LiTFSI + 0.5M LiFSI EC:DMC:EMC (1:1:1)",
    "0.5M LiTFSI + 0.5M LiFSI EC:DMC:EMC (3:7) + 10% FEC",
    
    # High Concentration Electrolytes
    "3M LiTFSI EC:DMC:EMC (1:1:1)",
    "3M LiTFSI EC:DMC:EMC (3:7) + 10% FEC",
    "4M LiTFSI EC:DMC:EMC (1:1:1)",
    "4M LiTFSI EC:DMC:EMC (3:7) + 10% FEC",
    "5M LiTFSI EC:DMC:EMC (1:1:1)",
    "5M LiTFSI EC:DMC:EMC (3:7) + 10% FEC",
    
    # Localized High Concentration Electrolytes (LHCE)
    "1M LiTFSI EC:DMC:TFE (1:1:3)",
    "1M LiTFSI EC:DMC:TFE (1:1:4)",
    "1M LiTFSI EC:DMC:TFE (1:1:5)",
    "1M LiTFSI EC:DMC:TTE (1:1:3)",
    "1M LiTFSI EC:DMC:TTE (1:1:4)",
    "1M LiTFSI EC:DMC:TTE (1:1:5)",
    
    # Sulfolane-based Electrolytes
    "1M LiPF6 EC:DMC:TMS (1:1:1)",
    "1M LiPF6 EC:DMC:TMS (3:7) + 10% FEC",
    "1M LiTFSI EC:DMC:TMS (1:1:1)",
    "1M LiTFSI EC:DMC:TMS (3:7) + 10% FEC",
    
    # Ionic Liquid Electrolytes
    "1M LiTFSI [EMIM][TFSI]",
    "1M LiTFSI [BMIM][TFSI]",
    "1M LiTFSI [EMIM][BF4]",
    "1M LiTFSI [BMIM][BF4]",
    
    # Solid State Electrolytes
    "PEO + LiTFSI (EO:Li = 20:1)",
    "PEO + LiTFSI (EO:Li = 16:1)",
    "PEO + LiTFSI (EO:Li = 12:1)",
    "PEO + LiTFSI + LLZTO",
    "PEO + LiTFSI + Al2O3",
    "PEO + LiTFSI + SiO2",
    
    # Custom/Experimental Electrolytes
    "Custom Electrolyte",
    "Experimental Electrolyte",
    "Research Electrolyte",
    "Proprietary Electrolyte"
]

# Battery Materials Database for Autocomplete
BATTERY_MATERIALS = {
    "Active Materials": [
        "Graphite", "Silicon", "Lithium Iron Phosphate (LFP)", "Lithium Cobalt Oxide (LCO)",
        "Lithium Nickel Manganese Cobalt Oxide (NMC)", "Lithium Nickel Cobalt Aluminum Oxide (NCA)",
        "Lithium Manganese Oxide (LMO)", "Lithium Titanate (LTO)", "Lithium Metal",
        "Sulfur", "Oxygen", "Lithium Nickel Oxide", "Lithium Manganese Spinel",
        "Lithium Vanadium Phosphate", "Lithium Iron Sulfate", "Lithium Cobalt Phosphate",
        "NMC811", "NMC811 (MSE)", "NMC811 (BASF)", "NMC811DASF", "NMC811 MSC",
        "NMC622", "NMC532", "NMC111"
    ],
    "Binders": [
        "Polyvinylidene Fluoride (PVDF)", "Carboxymethyl Cellulose (CMC)", "Styrene Butadiene Rubber (SBR)",
        "Polyacrylic Acid (PAA)", "Polyethylene Oxide (PEO)", "Polyvinyl Alcohol (PVA)",
        "Polyethylene Glycol (PEG)", "Polytetrafluoroethylene (PTFE)", "Polyvinyl Chloride (PVC)",
        "Polyurethane", "Polyimide", "Polyamide", "Polyester", "Polypropylene"
    ],
    "Conductive Additives": [
        "Carbon Black", "Super P", "Ketjen Black", "Vulcan XC-72", "Timcal Super C65",
        "Carbon Nanotubes (CNT)", "Graphene", "Graphite Flakes", "Carbon Fiber",
        "Carbon Nanofibers", "Reduced Graphene Oxide (rGO)", "Graphene Oxide",
        "Carbon Nanospheres", "Carbon Nanorods", "Carbon Nanobelts"
    ],
    "Electrolytes": [
        "Lithium Hexafluorophosphate (LiPF6)", "Lithium Bis(trifluoromethanesulfonyl)imide (LiTFSI)",
        "Lithium Bis(fluorosulfonyl)imide (LiFSI)", "Lithium Perchlorate (LiClO4)",
        "Lithium Tetrafluoroborate (LiBF4)", "Lithium Difluoro(oxalato)borate (LiDFOB)",
        "Ethylene Carbonate (EC)", "Propylene Carbonate (PC)", "Dimethyl Carbonate (DMC)",
        "Diethyl Carbonate (DEC)", "Ethyl Methyl Carbonate (EMC)", "Vinylene Carbonate (VC)",
        "Fluoroethylene Carbonate (FEC)", "1,3-Dioxolane (DOL)", "1,2-Dimethoxyethane (DME)"
    ],
    "Separators": [
        "Polyethylene (PE)", "Polypropylene (PP)", "Polyethylene/Polypropylene (PE/PP)",
        "Cellulose", "Glass Fiber", "Ceramic Coated", "Polyimide", "Polyamide",
        "Polyvinylidene Fluoride (PVDF)", "Polyacrylonitrile (PAN)", "Polymethyl Methacrylate (PMMA)"
    ],
    "Current Collectors": [
        "Copper Foil", "Aluminum Foil", "Nickel Foil", "Titanium Foil", "Stainless Steel",
        "Carbon Paper", "Carbon Cloth", "Carbon Felt", "Graphite Foil", "Copper Mesh",
        "Aluminum Mesh", "Nickel Mesh", "Titanium Mesh"
    ],
    "Additives": [
        "Vinylene Carbonate (VC)", "Fluoroethylene Carbonate (FEC)", "Succinonitrile",
        "1,3-Propane Sultone", "1,4-Butane Sultone", "Methyl Methanesulfonate",
        "Ethyl Methanesulfonate", "Propyl Methanesulfonate", "Butyl Methanesulfonate",
        "Lithium Difluoro(oxalato)borate (LiDFOB)", "Lithium Bis(oxalato)borate (LiBOB)",
        "Lithium Tetrafluorooxalatophosphate (LiTFOP)", "Lithium Difluorophosphate (LiPO2F2)"
    ],
    "Other": [
        "Water", "Ethanol", "Methanol", "Isopropanol", "Acetone", "N-Methyl-2-pyrrolidone (NMP)",
        "Dimethylformamide (DMF)", "Dimethylacetamide (DMAc)", "Tetrahydrofuran (THF)",
        "Toluene", "Xylene", "Chloroform", "Dichloromethane", "Hexane", "Heptane",
        "Cyclohexane", "Benzene", "Styrene", "Acrylic Acid", "Methacrylic Acid"
    ]
}

def get_separator_options():
    """
    Get comprehensive separator options including all predefined separators.
    This function can be easily extended to load options from a database in the future.
    """
    return COMPREHENSIVE_SEPARATORS.copy()

def track_electrolyte_usage(electrolyte):
    """
    Track electrolyte usage by adding it to the recent list for the current project.
    """
    if not electrolyte or electrolyte not in COMPREHENSIVE_ELECTROLYTES:
        return

    try:
        current_project_id = st.session_state.get('current_project_id')
        if not current_project_id:
            return

        from database import get_project_preferences, save_project_preferences
        preferences = get_project_preferences(current_project_id)
        recent_electrolytes = preferences.get('recent_electrolytes', [])

        # Remove the electrolyte if it's already in the list
        if electrolyte in recent_electrolytes:
            recent_electrolytes.remove(electrolyte)

        # Add it to the front of the list
        recent_electrolytes.insert(0, electrolyte)

        # Keep only the most recent 10 electrolytes
        recent_electrolytes = recent_electrolytes[:10]

        # Update preferences
        preferences['recent_electrolytes'] = recent_electrolytes
        save_project_preferences(current_project_id, preferences)

    except Exception as e:
        # Silently fail if tracking fails
        pass

def get_electrolyte_options():
    """
    Get comprehensive electrolyte options sorted by recent usage.
    Recently used electrolytes appear at the top, followed by alphabetical order.
    """
    try:
        # Get current project ID from session state
        current_project_id = st.session_state.get('current_project_id')

        if current_project_id:
            # Get project preferences to find recently used electrolytes
            from database import get_project_preferences
            preferences = get_project_preferences(current_project_id)
            recent_electrolytes = preferences.get('recent_electrolytes', [])

            if recent_electrolytes:
                # Start with recently used electrolytes (in order)
                sorted_options = recent_electrolytes.copy()
                
                # Add a visual separator
                sorted_options.append("─────────────────────────")

                # Add remaining electrolytes in alphabetical order
                remaining_electrolytes = [e for e in COMPREHENSIVE_ELECTROLYTES if e not in recent_electrolytes]
                remaining_electrolytes.sort()  # Alphabetical sort

                sorted_options.extend(remaining_electrolytes)
                return sorted_options
    except Exception as e:
        # If anything fails, fall back to default sorting
        pass

    # Fallback: return all electrolytes in alphabetical order
    return sorted(COMPREHENSIVE_ELECTROLYTES.copy())

def render_hybrid_electrolyte_input(label: str, default_value: str = "", key: str = None) -> str:
    """
    Render an improved electrolyte input with searchable dropdown and quick custom entry.
    
    Args:
        label: Label for the input field
        default_value: Default value to display
        key: Unique key for the Streamlit widget
    
    Returns:
        The selected/entered electrolyte value
    """
    if key is None:
        key = f"electrolyte_{uuid.uuid4().hex[:8]}"
    
    # Get all available electrolyte options (sorted by recent usage)
    electrolyte_options = get_electrolyte_options()
    
    # Add a "Custom..." option at the end for manual entry
    electrolyte_options_with_custom = electrolyte_options + ["➕ Custom..."]
    
    # Initialize session state
    value_key = f"{key}_value"
    custom_key = f"{key}_custom"
    last_tracked_key = f"{key}_last_tracked"
    
    if value_key not in st.session_state:
        st.session_state[value_key] = default_value
    if custom_key not in st.session_state:
        st.session_state[custom_key] = ""
    
    # Determine the index for the selectbox
    current_value = st.session_state[value_key]
    index = 0
    if current_value in electrolyte_options:
        index = electrolyte_options.index(current_value)
    
    # Main selectbox with search functionality (Streamlit's built-in)
    selected = st.selectbox(
        label,
        options=electrolyte_options_with_custom,
        index=index,
        key=f"{key}_dropdown",
        help="💡 Tip: Start typing to search. Recent selections appear at the top.",
        format_func=lambda x: "✨ Recently Used ↑" if x == "─────────────────────────" else x
    )
    
    # Handle separator selection (redirect to first real option)
    if selected == "─────────────────────────":
        if index > 0:
            selected = electrolyte_options_with_custom[index]
        else:
            selected = electrolyte_options_with_custom[0] if electrolyte_options_with_custom else default_value
    
    # Handle custom entry
    if selected == "➕ Custom...":
        custom_value = st.text_input(
            "Enter custom electrolyte:",
            value=st.session_state[custom_key],
            key=f"{key}_custom_input",
            placeholder="e.g., 1.5M LiFSI DOL:DME (1:1)",
            help="Enter your custom electrolyte formulation"
        )
        
        if custom_value and custom_value != st.session_state[custom_key]:
            st.session_state[custom_key] = custom_value
            st.session_state[value_key] = custom_value
            # Track custom entries too
            if custom_value not in COMPREHENSIVE_ELECTROLYTES:
                st.info(f"💡 Custom electrolyte: '{custom_value}' (not in standard list)")
        
        final_value = st.session_state[value_key] if st.session_state[value_key] != "➕ Custom..." else custom_value
    else:
        # Standard selection
        final_value = selected
        st.session_state[value_key] = selected
        
        # Track usage only when value actually changes (not on initialization)
        if selected and selected in COMPREHENSIVE_ELECTROLYTES:
            if last_tracked_key not in st.session_state:
                st.session_state[last_tracked_key] = None
            
            # Only track if the value changed from last tracked value
            if st.session_state[last_tracked_key] != selected:
                track_electrolyte_usage(selected)
                st.session_state[last_tracked_key] = selected
    
    return final_value

def render_hybrid_separator_input(label: str, default_value: str = "", key: str = None) -> str:
    """
    Render a hybrid separator input that allows both dropdown selection and manual entry.
    
    Args:
        label: Label for the input field
        default_value: Default value to display
        key: Unique key for the Streamlit widget
    
    Returns:
        The selected/entered separator value
    """
    if key is None:
        key = f"separator_{uuid.uuid4().hex[:8]}"
    
    # Get all available separator options
    separator_options = get_separator_options()
    
    # Initialize session state for this input
    value_key = f"{key}_value"
    mode_key = f"{key}_mode"
    
    if value_key not in st.session_state:
        st.session_state[value_key] = default_value
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "dropdown"  # "dropdown" or "custom"
    
    # Create two columns for the hybrid input
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Main input field - can be either dropdown or text input
        if st.session_state[mode_key] == "dropdown":
            # Dropdown mode
            current_value = st.session_state[value_key]
            index = 0
            if current_value in separator_options:
                index = separator_options.index(current_value)
            
            selected = st.selectbox(
                label,
                options=separator_options,
                index=index,
                key=f"{key}_dropdown"
            )
            st.session_state[value_key] = selected
        else:
            # Custom entry mode
            custom_value = st.text_input(
                label,
                value=st.session_state[value_key],
                key=f"{key}_text"
            )
            st.session_state[value_key] = custom_value
    
    with col2:
        # Toggle button to switch between dropdown and custom entry
        if st.button(
            "📝" if st.session_state[mode_key] == "dropdown" else "📋",
            help="Switch to custom entry" if st.session_state[mode_key] == "dropdown" else "Switch to dropdown",
            key=f"{key}_toggle"
        ):
            st.session_state[mode_key] = "custom" if st.session_state[mode_key] == "dropdown" else "dropdown"
            st.rerun()
    
    # Add autocomplete suggestions if in custom mode
    if st.session_state[mode_key] == "custom":
        current_input = st.session_state[value_key].lower()
        if current_input:
            # Filter suggestions based on current input
            suggestions = [opt for opt in separator_options if current_input in opt.lower()]
            if suggestions:
                st.markdown("**💡 Suggestions:**")
                suggestion_cols = st.columns(min(3, len(suggestions)))
                for i, suggestion in enumerate(suggestions[:6]):  # Limit to 6 suggestions
                    col_idx = i % 3
                    with suggestion_cols[col_idx]:
                        if st.button(
                            suggestion,
                            key=f"{key}_suggestion_{i}",
                            use_container_width=True
                        ):
                            st.session_state[value_key] = suggestion
                            st.rerun()
    
    return st.session_state[value_key]

def get_all_battery_materials():
    """Get a flat list of all battery materials for autocomplete."""
    all_materials = []
    for category, materials in BATTERY_MATERIALS.items():
        all_materials.extend(materials)
    return sorted(all_materials)

def filter_materials_by_query(query: str, materials: List[str] = None) -> List[str]:
    """Filter materials based on user query for autocomplete."""
    if materials is None:
        materials = get_all_battery_materials()
    
    if not query:
        return materials[:10]  # Return first 10 if no query
    
    query_lower = query.lower()
    filtered = []
    
    # First priority: exact matches
    exact_matches = [m for m in materials if query_lower == m.lower()]
    filtered.extend(exact_matches)
    
    # Second priority: starts with query
    starts_with = [m for m in materials if m.lower().startswith(query_lower) and m not in exact_matches]
    filtered.extend(starts_with)
    
    # Third priority: contains query
    contains = [m for m in materials if query_lower in m.lower() and m not in filtered]
    filtered.extend(contains)
    
    return filtered[:10]  # Limit to 10 suggestions

def render_autocomplete_input(key: str, label: str = "Component", placeholder: str = "Type to search materials...", 
                            value: str = "", materials: List[str] = None, allow_custom: bool = True) -> str:
    """
    Render an autocomplete input field for battery materials.
    
    Args:
        key: Unique key for the Streamlit component
        label: Label for the input field
        placeholder: Placeholder text
        value: Initial value
        materials: List of materials to search from (defaults to all battery materials)
        allow_custom: Whether to allow custom entries not in the list
    
    Returns:
        Selected or entered material name
    """
    if materials is None:
        materials = get_all_battery_materials()
    
    # Initialize session state for this autocomplete
    query_key = f"{key}_query"
    suggestions_key = f"{key}_suggestions"
    selected_key = f"{key}_selected"
    show_suggestions_key = f"{key}_show_suggestions"
    
    if query_key not in st.session_state:
        st.session_state[query_key] = ""
    if suggestions_key not in st.session_state:
        st.session_state[suggestions_key] = []
    if selected_key not in st.session_state:
        st.session_state[selected_key] = value
    elif value and st.session_state[selected_key] == "":  # Update if we have a new value and current is empty
        st.session_state[selected_key] = value
    if show_suggestions_key not in st.session_state:
        st.session_state[show_suggestions_key] = False
    
    # Handle text input
    current_value = st.session_state[selected_key]
    new_value = st.text_input(
        label,
        value=current_value,
        key=f"{key}_input",
        placeholder=placeholder,
        label_visibility="collapsed"
    )
    
    # Update query and filter suggestions
    if new_value != current_value:
        st.session_state[query_key] = new_value
        st.session_state[suggestions_key] = filter_materials_by_query(new_value, materials)
        st.session_state[show_suggestions_key] = len(new_value) > 0 and len(st.session_state[suggestions_key]) > 0
        st.session_state[selected_key] = new_value
    
    # Show suggestions if there are any and we should show them
    if st.session_state[show_suggestions_key]:
        suggestions = st.session_state[suggestions_key]
        
        # Create a container for suggestions
        suggestions_container = st.container()
        
        with suggestions_container:
            st.markdown("**Suggestions:**")
            
            # Create columns for suggestions (3 per row)
            cols = st.columns(3)
            for i, suggestion in enumerate(suggestions):
                col_idx = i % 3
                with cols[col_idx]:
                    if st.button(
                        suggestion,
                        key=f"{key}_suggestion_{i}",
                        use_container_width=True
                    ):
                        st.session_state[selected_key] = suggestion
                        st.session_state[show_suggestions_key] = False
                        st.rerun()
            
            # Add "Clear suggestions" button
            if st.button("Clear suggestions", key=f"{key}_clear"):
                st.session_state[show_suggestions_key] = False
                st.rerun()
    
    return st.session_state[selected_key]

def get_substrate_options():
    """
    Get available substrate options. This function can be easily extended
    to load options from a database or configuration file in the future.
    """
    return [
        'Copper',
        'Aluminum', 
        'Carbon-Coated Aluminum',
        'SS316',
        'Cx-Cu'
    ]

def calculate_cell_metrics(df_cell, formation_cycles, disc_area_cm2):
    """Centralized metric calculation to avoid duplication"""
    metrics = {}
    
    # 1st Cycle Discharge Capacity
    first_three_qdis = df_cell['Q Dis (mAh/g)'].head(3).tolist()
    metrics['max_qdis'] = max(first_three_qdis) if first_three_qdis else None
    
    # First Cycle Efficiency
    if 'Efficiency (-)' in df_cell.columns and not df_cell['Efficiency (-)'].empty:
        first_cycle_eff = df_cell['Efficiency (-)'].iloc[0]
        try:
            metrics['first_cycle_eff'] = float(first_cycle_eff) * 100
        except (ValueError, TypeError):
            metrics['first_cycle_eff'] = None
    else:
        metrics['first_cycle_eff'] = None
    
    # Cycle Life (expensive calculation - do once)
    qdis_series = get_qdis_series(df_cell)
    cycle_index_series = df_cell[df_cell.columns[0]].iloc[qdis_series.index]
    metrics['cycle_life_80'] = calculate_cycle_life_80(qdis_series, cycle_index_series)
    
    # Initial Areal Capacity
    areal_capacity, chosen_cycle, diff_pct, eff_val = get_initial_areal_capacity(df_cell, disc_area_cm2)
    metrics['areal_capacity'] = areal_capacity
    
    # Reversible Capacity
    if len(df_cell) > formation_cycles:
        metrics['reversible_capacity'] = df_cell['Q Dis (mAh/g)'].iloc[formation_cycles]
    else:
        metrics['reversible_capacity'] = None
    
    # Coulombic Efficiency (post-formation)
    eff_col = 'Efficiency (-)'
    qdis_col = 'Q Dis (mAh/g)'
    qch_col = 'Q Ch (mAh/g)'
    n_cycles = len(df_cell)
    ceff_values = []
    
    try:
        start_idx = formation_cycles if n_cycles > formation_cycles else 0
        
        # Prefer calculating from Q Dis / Q Ch per cycle; fall back to provided efficiency column
        if qdis_col in df_cell.columns and qch_col in df_cell.columns:
            qdis_series = pd.to_numeric(df_cell[qdis_col], errors='coerce')
            qch_series = pd.to_numeric(df_cell[qch_col], errors='coerce')
            
            # Use degradation check logic: stop if capacity drops significantly
            if n_cycles > formation_cycles + 1:
                prev_qdis = qdis_series.iloc[formation_cycles]
                for i in range(formation_cycles + 1, n_cycles):
                    qdis = qdis_series.iloc[i]
                    qch = qch_series.iloc[i]
                    try:
                        pq = float(prev_qdis) if pd.notna(prev_qdis) else 0
                        qd = float(qdis) if pd.notna(qdis) else 0
                        qc = float(qch) if pd.notna(qch) else 0
                        
                        # Stop if capacity drops significantly
                        if pq > 0 and qd < 0.95 * pq:
                            break
                        
                        # Calculate efficiency if we have valid data
                        if pd.notna(qdis) and pd.notna(qch) and qc > 0:
                            ceff_values.append((qd / qc) * 100)
                            prev_qdis = qd
                    except (ValueError, TypeError):
                        continue
            else:
                # Simple calculation without degradation check if not enough cycles
                for i in range(start_idx, n_cycles):
                    qdis = qdis_series.iloc[i]
                    qch = qch_series.iloc[i]
                    if pd.notna(qdis) and pd.notna(qch) and qch > 0:
                        ceff_values.append((qdis / qch) * 100)
        
        elif eff_col in df_cell.columns and qdis_col in df_cell.columns and n_cycles > formation_cycles+1:
            # Fallback to efficiency column with degradation check
            prev_qdis = df_cell[qdis_col].iloc[formation_cycles]
            prev_eff = df_cell[eff_col].iloc[formation_cycles]
            for i in range(formation_cycles+1, n_cycles):
                curr_qdis = df_cell[qdis_col].iloc[i]
                curr_eff = df_cell[eff_col].iloc[i]
                try:
                    pq = float(prev_qdis)
                    cq = float(curr_qdis)
                    pe = float(prev_eff)
                    ce = float(curr_eff)
                    if pq > 0 and (cq < 0.95 * pq or ce < 0.95 * pe):
                        break
                    # Convert efficiency from decimal (0-1) to percentage
                    ceff_values.append(ce * 100)
                    prev_qdis = cq
                    prev_eff = ce
                except (ValueError, TypeError):
                    continue
        
        elif eff_col in df_cell.columns:
            # Simple fallback: just use efficiency column without degradation check
            eff_series = pd.to_numeric(df_cell[eff_col], errors='coerce')
            ceff_values = [val * 100 for val in eff_series.iloc[start_idx:n_cycles] if pd.notna(val) and val > 0]
        
        if ceff_values:
            metrics['coulombic_eff'] = sum(ceff_values) / len(ceff_values)
        else:
            metrics['coulombic_eff'] = None
    except Exception as e:
        metrics['coulombic_eff'] = None
    
    return metrics

def render_toggle_section(dfs: List[Dict[str, Any]], enable_grouping: bool = False) -> Tuple[Dict[str, bool], Dict[str, bool], bool, bool, bool, Dict[str, bool], bool, bool, Dict[str, bool], str, Tuple[float, float]]:
    """Render all toggles and return their states: show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, group_plot_toggles, cycle_filter, y_axis_limits."""
    with st.expander("⚙️ Graph Display Options", expanded=True):
        st.markdown("### Graph Display Options")
        dis_col, chg_col, eff_col = st.columns(3)

        # Helper functions for toggling all
        def set_all_discharge(val):
            for label in discharge_labels:
                st.session_state[f'show_{label}'] = val
        def set_all_charge(val):
            for label in charge_labels:
                st.session_state[f'show_{label}'] = val
        def set_all_efficiency(val):
            for label in efficiency_labels:
                st.session_state[f'show_{label}'] = val

        # Discharge toggles
        with dis_col:
            st.markdown("**Discharge Capacity**")
            discharge_labels = []
            for i, d in enumerate(dfs):
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_dis = f"{cell_name} Q Dis"
                discharge_labels.append(label_dis)
            if len(dfs) > 1:
                toggle_all_discharge = st.checkbox('Toggle All Discharge', value=True, key='toggle_all_discharge', on_change=set_all_discharge, args=(not st.session_state.get('toggle_all_discharge', True),))
            else:
                toggle_all_discharge = True

        # Charge toggles
        with chg_col:
            st.markdown("**Charge Capacity**")
            charge_labels = []
            for i, d in enumerate(dfs):
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_chg = f"{cell_name} Q Chg"
                charge_labels.append(label_chg)
            if len(dfs) > 1:
                toggle_all_charge = st.checkbox('Toggle All Charge', value=True, key='toggle_all_charge', on_change=set_all_charge, args=(not st.session_state.get('toggle_all_charge', True),))
            else:
                toggle_all_charge = True

        # Efficiency toggles
        with eff_col:
            st.markdown("**Efficiency**")
            efficiency_labels = []
            for i, d in enumerate(dfs):
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                label_eff = f"{cell_name} Efficiency"
                efficiency_labels.append(label_eff)
            if len(dfs) > 1:
                toggle_all_efficiency = st.checkbox('Toggle All Efficiency', value=False, key='toggle_all_efficiency', on_change=set_all_efficiency, args=(not st.session_state.get('toggle_all_efficiency', False),))
            else:
                toggle_all_efficiency = False

        show_lines = {}
        with dis_col:
            for label in discharge_labels:
                show_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_discharge, key=f'show_{label}')
        with chg_col:
            for label in charge_labels:
                show_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_charge, key=f'show_{label}')
        show_efficiency_lines = {}
        with eff_col:
            for label in efficiency_labels:
                show_efficiency_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_efficiency, key=f'show_{label}')

        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True, "Average Efficiency": True}
        group_plot_toggles = {"Group Q Dis": False, "Group Q Chg": False, "Group Efficiency": False}
        st.markdown("---")
        
        # Cycle filter section
        with st.expander("🔄 Cycle Data Filter", expanded=False):
            st.markdown("### Filter Cycles to Display")
            st.markdown("**Examples:** `1-120` (cycles 1-120), `2;5;10` (cycles 2,5,10), `3-*` (cycles 3 to end)")
            
            cycle_filter = st.text_input(
                "Cycle Range",
                value="1-*",
                key="cycle_filter",
                help="Enter cycle range (e.g., '1-120', '2;5;10', '3-*'). Use '*' for 'to end'."
            )
        
        with st.expander("📊 Plot Display Settings", expanded=False):
            st.markdown("### Plot Styling Options")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Data Processing**")
                remove_last_cycle = st.checkbox(
                    '🔄 Remove last cycle', 
                    value=False,
                    help="Exclude the last cycle from plots"
                )
                
            with col2:
                st.markdown("**Visual Display**")
                remove_markers = st.checkbox(
                    '🔘 Remove markers', 
                    value=False,
                    help="Hide data point markers for cleaner lines"
                )
                show_graph_title = st.checkbox(
                    '📝 Show graph title', 
                    value=True,
                    help="Display the plot title"
                )
                
            with col3:
                st.markdown("**Legend & Performance**")
                hide_legend = st.checkbox(
                    '🏷️ Hide legend', 
                    value=False,
                    help="Remove the plot legend"
                )
                show_average_performance = False
                if len(dfs) > 1:
                    show_average_performance = st.checkbox(
                        '📊 Show averages', 
                        value=False,
                        help="Display average performance lines"
                    )
            
            # Y-Axis Controls Section
            st.markdown("---")
            st.markdown("### 📏 Y-Axis Range Control")
            st.markdown("*Adjust the upper and lower bounds of the y-axis for capacity plots*")
            
            y_axis_col1, y_axis_col2, y_axis_col3 = st.columns([1, 1, 1])
            
            with y_axis_col1:
                use_auto_ylim = st.checkbox(
                    '🔄 Auto Y-Axis', 
                    value=True,
                    key='use_auto_ylim',
                    help="Automatically set y-axis limits based on data"
                )
            
            with y_axis_col2:
                y_min = st.number_input(
                    "Y-Axis Min (mAh/g)",
                    value=0.0,
                    step=10.0,
                    key='y_axis_min',
                    disabled=use_auto_ylim,
                    help="Set the minimum value for the y-axis"
                )
            
            with y_axis_col3:
                y_max = st.number_input(
                    "Y-Axis Max (mAh/g)",
                    value=400.0,
                    step=10.0,
                    key='y_axis_max',
                    disabled=use_auto_ylim,
                    help="Set the maximum value for the y-axis"
                )
            
            # Store y-axis limits as tuple (None, None) if auto, otherwise (y_min, y_max)
            y_axis_limits = (None, None) if use_auto_ylim else (y_min, y_max)
        # Place average toggles in the same columns as the main toggles, if Average Cell Performance is checked
        if show_average_performance:
            with dis_col:
                avg_line_toggles["Average Q Dis"] = st.checkbox('Show Average Q Dis', value=True, key='show_avg_qdis')
            with chg_col:
                avg_line_toggles["Average Q Chg"] = st.checkbox('Show Average Q Chg', value=True, key='show_avg_qchg')
            with eff_col:
                avg_line_toggles["Average Efficiency"] = st.checkbox('Show Average Efficiency', value=True, key='show_avg_eff')
        # Group plotting toggles in expander if grouping is enabled
        if enable_grouping:
            with st.expander('Group Plotting Options', expanded=True):
                group_plot_toggles["Group Q Dis"] = st.checkbox('Plot Group Q Dis', value=True, key='plot_group_qdis')
                group_plot_toggles["Group Q Chg"] = st.checkbox('Plot Group Q Chg (Charge Capacity)', value=False, key='plot_group_qchg')
                group_plot_toggles["Group Efficiency"] = st.checkbox('Plot Group Efficiency', value=False, key='plot_group_eff')
        return show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, group_plot_toggles, cycle_filter, y_axis_limits

# render_retention_display_options function removed - now using unified plot settings

def parse_cycle_filter(cycle_filter: str, max_cycle: int) -> List[int]:
    """
    Parse cycle filter string and return list of cycles to include.
    
    Args:
        cycle_filter: String like "1-120", "2;5;10", "3-*", etc.
        max_cycle: Maximum cycle number in the dataset
        
    Returns:
        List of cycle numbers to include
    """
    if not cycle_filter or cycle_filter.strip() == "":
        return list(range(1, max_cycle + 1))
    
    cycles = set()
    parts = [part.strip() for part in cycle_filter.split(';')]
    
    for part in parts:
        if '-' in part:
            # Handle range like "1-120" or "3-*"
            start, end = part.split('-', 1)
            start = int(start.strip())
            
            if end.strip() == '*':
                # Handle wildcard - include from start to max_cycle
                cycles.update(range(start, max_cycle + 1))
            else:
                # Handle specific end
                end = int(end.strip())
                cycles.update(range(start, end + 1))
        else:
            # Handle individual cycle like "5"
            cycles.add(int(part))
    
    return sorted(list(cycles))

def render_comparison_plot_options(experiments_data: List[Dict[str, Any]]) -> Tuple[Dict[str, bool], Dict[str, bool], bool, bool, bool, Dict[str, bool], bool, bool, str, Tuple[float, float]]:
    """
    Render plotting options for the comparison plot and return their states.
    
    This is now a wrapper around the unified plot controls system.
    
    Args:
        experiments_data: List of experiment data dictionaries
        
    Returns:
        Tuple containing: show_lines, show_efficiency_lines, remove_last_cycle, 
        show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, cycle_filter, y_axis_limits
    """
    with st.expander("⚙️ Comparison Plot Options", expanded=True):
        st.markdown("### Select Data Series to Compare")
        
        # Create columns for different data types
        dis_col, chg_col, eff_col = st.columns(3)
        
        # Collect all available labels from all experiments
        all_discharge_labels = []
        all_charge_labels = []
        all_efficiency_labels = []
        
        for exp_data in experiments_data:
            exp_name = exp_data['experiment_name']
            dfs = exp_data['dfs']
            
            for i, d in enumerate(dfs):
                cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
                all_discharge_labels.append(f"{exp_name} - {cell_name} Q Dis")
                all_charge_labels.append(f"{exp_name} - {cell_name} Q Chg")
                all_efficiency_labels.append(f"{exp_name} - {cell_name} Efficiency")
        
        # Helper functions for toggling all within each category
        def set_all_discharge(val):
            for label in all_discharge_labels:
                st.session_state[f'comp_show_{label}'] = val
        def set_all_charge(val):
            for label in all_charge_labels:
                st.session_state[f'comp_show_{label}'] = val
        def set_all_efficiency(val):
            for label in all_efficiency_labels:
                st.session_state[f'comp_show_{label}'] = val

        # Discharge toggles
        with dis_col:
            st.markdown("**Discharge Capacity**")
            if len(all_discharge_labels) > 1:
                toggle_all_discharge = st.checkbox('Toggle All Discharge', value=True, key='comp_toggle_all_discharge', on_change=set_all_discharge, args=(not st.session_state.get('comp_toggle_all_discharge', True),))
            else:
                toggle_all_discharge = True

            show_lines = {}
            for i, label in enumerate(all_discharge_labels):
                show_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_discharge, key=f'comp_show_{label}')

        # Charge toggles
        with chg_col:
            st.markdown("**Charge Capacity**")
            if len(all_charge_labels) > 1:
                toggle_all_charge = st.checkbox('Toggle All Charge', value=False, key='comp_toggle_all_charge', on_change=set_all_charge, args=(not st.session_state.get('comp_toggle_all_charge', False),))
            else:
                toggle_all_charge = False

            for i, label in enumerate(all_charge_labels):
                show_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_charge, key=f'comp_show_charge_{label}')

        # Efficiency toggles
        with eff_col:
            st.markdown("**Efficiency**")
            if len(all_efficiency_labels) > 1:
                toggle_all_efficiency = st.checkbox('Toggle All Efficiency', value=False, key='comp_toggle_all_efficiency', on_change=set_all_efficiency, args=(not st.session_state.get('comp_toggle_all_efficiency', False),))
            else:
                toggle_all_efficiency = False

            show_efficiency_lines = {}
            for i, label in enumerate(all_efficiency_labels):
                show_efficiency_lines[label] = st.checkbox(f"Show {label}", value=toggle_all_efficiency, key=f'comp_show_eff_{label}')

        # Cycle filter section for comparison plots
        st.markdown("---")
        with st.expander("🔄 Cycle Data Filter", expanded=False):
            st.markdown("### Filter Cycles to Display")
            st.markdown("**Examples:** `1-120` (cycles 1-120), `2;5;10` (cycles 2,5,10), `3-*` (cycles 3 to end)")
            
            cycle_filter = st.text_input(
                "Cycle Range",
                value="1-*",
                key="comp_cycle_filter",
                help="Enter cycle range (e.g., '1-120', '2;5;10', '3-*'). Use '*' for 'to end'."
            )

        # Unified display options for comparison plots
        with st.expander("📊 Comparison Plot Display Settings", expanded=False):
            st.markdown("### Plot Styling Options")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Data Processing**")
                remove_last_cycle = st.checkbox(
                    '🔄 Remove last cycle', 
                    value=False,
                    key='comp_remove_last',
                    help="Exclude the last cycle from comparison plots"
                )
                
            with col2:
                st.markdown("**Visual Display**")
                remove_markers = st.checkbox(
                    '🔘 Remove markers', 
                    value=False,
                    key='comp_remove_markers',
                    help="Hide data point markers for cleaner lines"
                )
                show_graph_title = st.checkbox(
                    '📝 Show graph title', 
                    value=True,
                    key='comp_show_title',
                    help="Display the plot title"
                )
                
            with col3:
                st.markdown("**Legend & Performance**")
                hide_legend = st.checkbox(
                    '🏷️ Hide legend', 
                    value=False,
                    key='comp_hide_legend',
                    help="Remove the plot legend"
                )
                show_average_performance = st.checkbox(
                    '📊 Show averages', 
                    value=False,
                    key='comp_show_averages',
                    help="Display average performance lines (hides individual cell traces when enabled)"
                )
            
            # Y-Axis Controls Section
            st.markdown("---")
            st.markdown("### 📏 Y-Axis Range Control")
            st.markdown("*Adjust the upper and lower bounds of the y-axis for capacity plots*")
            
            y_axis_col1, y_axis_col2, y_axis_col3 = st.columns([1, 1, 1])
            
            with y_axis_col1:
                use_auto_ylim_comp = st.checkbox(
                    '🔄 Auto Y-Axis', 
                    value=True,
                    key='comp_use_auto_ylim',
                    help="Automatically set y-axis limits based on data"
                )
            
            with y_axis_col2:
                y_min_comp = st.number_input(
                    "Y-Axis Min (mAh/g)",
                    value=0.0,
                    step=10.0,
                    key='comp_y_axis_min',
                    disabled=use_auto_ylim_comp,
                    help="Set the minimum value for the y-axis"
                )
            
            with y_axis_col3:
                y_max_comp = st.number_input(
                    "Y-Axis Max (mAh/g)",
                    value=400.0,
                    step=10.0,
                    key='comp_y_axis_max',
                    disabled=use_auto_ylim_comp,
                    help="Set the maximum value for the y-axis"
                )
            
            # Store y-axis limits as tuple (None, None) if auto, otherwise (y_min, y_max)
            y_axis_limits = (None, None) if use_auto_ylim_comp else (y_min_comp, y_max_comp)

        # Average Line Filter Controls
        avg_line_toggles = {"Average Q Dis": True, "Average Q Chg": True, "Average Efficiency": True}
        
        if show_average_performance:
            st.markdown("---")
            st.markdown("### 📈 Average Line Filters")
            st.info("ℹ️ With 'Show Averages' enabled, individual cell traces are hidden. Use the toggles below to filter which average lines to display.")
            
            avg_col1, avg_col2, avg_col3 = st.columns(3)
            
            with avg_col1:
                avg_line_toggles["Average Q Dis"] = st.checkbox(
                    '📊 Average Q Dis',
                    value=True,
                    key='comp_avg_qdis',
                    help="Show/hide average discharge capacity line"
                )
            
            with avg_col2:
                avg_line_toggles["Average Q Chg"] = st.checkbox(
                    '⚡ Average Q Chg',
                    value=True,
                    key='comp_avg_qchg',
                    help="Show/hide average charge capacity line"
                )
            
            with avg_col3:
                avg_line_toggles["Average Efficiency"] = st.checkbox(
                    '🎯 Average Efficiency',
                    value=True,
                    key='comp_avg_eff',
                    help="Show/hide average efficiency line"
                )
    
    return show_lines, show_efficiency_lines, remove_last_cycle, show_graph_title, show_average_performance, avg_line_toggles, remove_markers, hide_legend, cycle_filter, y_axis_limits


def render_full_cell_mass_balance_inputs(context_key=None, cell_format="Coin"):
    """Render Full Cell specific Mass Balance & Geometry inputs.
    
    Args:
        context_key: Unique key for this render context
        cell_format: Cell format ("Coin", "Pouch", "Cylindrical", "Prismatic")
    
    Returns:
        dict: Full cell parameters including anode/cathode specifications and calculated metrics
    """
    if context_key is None:
        context_key = str(uuid.uuid4())
    
    st.markdown("### ⚖️ Mass Balance & Geometry Configuration")
    st.info("📌 Full Cell Project: Configure anode and cathode specifications for N/P ratio and overhang calculations")
    
    # Determine default diameters for coin cells
    if cell_format == "Coin":
        default_anode_diameter = 16.0  # mm
        default_cathode_diameter = 15.0  # mm
    else:
        # For other formats, use defaults that convert to reasonable areas
        default_anode_diameter = 16.0  # mm
        default_cathode_diameter = 15.0  # mm
    
    # Get current values or use defaults
    anode_diameter_key = f'anode_diameter_{context_key}'
    cathode_diameter_key = f'cathode_diameter_{context_key}'
    anode_loading_manual_key = f'anode_loading_manual_{context_key}'
    cathode_loading_manual_key = f'cathode_loading_manual_{context_key}'
    
    # Initialize diameter values
    if anode_diameter_key not in st.session_state:
        st.session_state[anode_diameter_key] = default_anode_diameter
    if cathode_diameter_key not in st.session_state:
        st.session_state[cathode_diameter_key] = default_cathode_diameter
    
    # Create two columns for Anode and Cathode
    col_anode, col_cathode = st.columns(2)
    
    with col_anode:
        st.markdown("#### 🔋 Anode Specifications")
        anode_mass = st.number_input(
            'Active Material Mass (mg)',
            min_value=0.0,
            step=0.1,
            value=st.session_state.get(f'anode_mass_{context_key}', 10.0),
            key=f'anode_mass_{context_key}',
            help="Mass of anode active material"
        )
        
        # Calculate diameter from area if area was previously stored, otherwise use diameter
        anode_diameter = st.number_input(
            'Diameter (mm)',
            min_value=0.1,
            step=0.1,
            value=st.session_state[anode_diameter_key],
            key=anode_diameter_key,
            help="Diameter of anode electrode disc"
        )
        
        # Calculate area from diameter (in cm²)
        anode_area = math.pi * (anode_diameter / 20.0) ** 2  # Convert mm to cm: diameter/2/10 = diameter/20
        
        # Calculate loading from mass and area
        calculated_anode_loading = anode_mass / anode_area if anode_area > 0 else 0.0
        
        # Check if user has manually set loading (track in session state)
        if anode_loading_manual_key not in st.session_state:
            st.session_state[anode_loading_manual_key] = False
        
        # If user changes loading manually, mark it as manual
        # Use calculated value unless user has manually overridden
        if st.session_state[anode_loading_manual_key]:
            default_loading = st.session_state.get(f'anode_loading_{context_key}', calculated_anode_loading)
        else:
            default_loading = calculated_anode_loading
            st.session_state[f'anode_loading_{context_key}'] = calculated_anode_loading
        
        anode_loading = st.number_input(
            'Loading (mg/cm²)',
            min_value=0.0,
            step=0.1,
            value=default_loading,
            key=f'anode_loading_{context_key}',
            help="Anode active material loading per unit area (calculated from mass and area, can be overwritten)"
        )
        
        # Detect if user manually changed loading
        if abs(anode_loading - calculated_anode_loading) > 0.001:  # Small tolerance for floating point
            st.session_state[anode_loading_manual_key] = True
        elif anode_mass == 0 or anode_area == 0:
            # Reset manual flag if mass or area is zero
            st.session_state[anode_loading_manual_key] = False
        
        anode_thickness = st.number_input(
            'Electrode Thickness (μm)',
            min_value=0.0,
            step=1.0,
            value=st.session_state.get(f'anode_thickness_{context_key}', 50.0),
            key=f'anode_thickness_{context_key}',
            help="Total thickness of anode electrode"
        )
    
    with col_cathode:
        st.markdown("#### 🔋 Cathode Specifications")
        cathode_mass = st.number_input(
            'Active Material Mass (mg)',
            min_value=0.0,
            step=0.1,
            value=st.session_state.get(f'cathode_mass_{context_key}', 12.0),
            key=f'cathode_mass_{context_key}',
            help="Mass of cathode active material"
        )
        
        cathode_diameter = st.number_input(
            'Diameter (mm)',
            min_value=0.1,
            step=0.1,
            value=st.session_state[cathode_diameter_key],
            key=cathode_diameter_key,
            help="Diameter of cathode electrode disc"
        )
        
        # Calculate area from diameter (in cm²)
        cathode_area = math.pi * (cathode_diameter / 20.0) ** 2  # Convert mm to cm: diameter/2/10 = diameter/20
        
        # Calculate loading from mass and area
        calculated_cathode_loading = cathode_mass / cathode_area if cathode_area > 0 else 0.0
        
        # Check if user has manually set loading (track in session state)
        if cathode_loading_manual_key not in st.session_state:
            st.session_state[cathode_loading_manual_key] = False
        
        # If user changes loading manually, mark it as manual
        # Use calculated value unless user has manually overridden
        if st.session_state[cathode_loading_manual_key]:
            default_loading = st.session_state.get(f'cathode_loading_{context_key}', calculated_cathode_loading)
        else:
            default_loading = calculated_cathode_loading
            st.session_state[f'cathode_loading_{context_key}'] = calculated_cathode_loading
        
        cathode_loading = st.number_input(
            'Loading (mg/cm²)',
            min_value=0.0,
            step=0.1,
            value=default_loading,
            key=f'cathode_loading_{context_key}',
            help="Cathode active material loading per unit area (calculated from mass and area, can be overwritten)"
        )
        
        # Detect if user manually changed loading
        if abs(cathode_loading - calculated_cathode_loading) > 0.001:  # Small tolerance for floating point
            st.session_state[cathode_loading_manual_key] = True
        elif cathode_mass == 0 or cathode_area == 0:
            # Reset manual flag if mass or area is zero
            st.session_state[cathode_loading_manual_key] = False
        
        cathode_thickness = st.number_input(
            'Electrode Thickness (μm)',
            min_value=0.0,
            step=1.0,
            value=st.session_state.get(f'cathode_thickness_{context_key}', 60.0),
            key=f'cathode_thickness_{context_key}',
            help="Total thickness of cathode electrode"
        )
    
    # Calculate derived metrics
    st.markdown("---")
    st.markdown("#### 📊 Calculated Key Metrics")
    
    # Calculate overhang ratio (Anode-to-Cathode area ratio)
    overhang_ratio = anode_area / cathode_area if cathode_area > 0 else 0
    
    # Display calculated metrics in columns
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    
    with metric_col1:
        st.metric(
            "Overhang Ratio (A/C)",
            f"{overhang_ratio:.3f}",
            help="Ratio of anode to cathode areal dimensions"
        )
        if overhang_ratio < 1.0:
            st.warning("⚠️ Overhang < 1.0: Anode is smaller than cathode")
    
    with metric_col2:
        # N/P ratio will be calculated from formation capacities - show placeholder
        st.metric(
            "N/P Ratio",
            "To be calculated",
            help="Negative/Positive capacity ratio (calculated from formation data)"
        )
        st.caption("📝 N/P ratio calculated after uploading cycling data")
    
    with metric_col3:
        # Show anode/cathode capacity balance estimate
        anode_specific_capacity = 372.0  # Typical graphite capacity (mAh/g)
        cathode_specific_capacity = 180.0  # Typical NMC capacity (mAh/g)
        
        anode_capacity_est = anode_mass * anode_specific_capacity / 1000  # Convert to mAh
        cathode_capacity_est = cathode_mass * cathode_specific_capacity / 1000  # Convert to mAh
        
        np_ratio_est = anode_capacity_est / cathode_capacity_est if cathode_capacity_est > 0 else 0
        
        st.metric(
            "N/P Ratio (Estimate)",
            f"{np_ratio_est:.3f}",
            help=f"Estimated N/P ratio using typical capacities\nAnode: {anode_specific_capacity} mAh/g, Cathode: {cathode_specific_capacity} mAh/g"
        )
        
        if np_ratio_est < 1.0:
            st.error("🚨 N/P < 1.0: High lithium plating risk!")
        elif np_ratio_est < 1.05:
            st.warning("⚠️ N/P < 1.05: Low safety margin")
        else:
            st.success("✅ N/P ratio in safe range")
    
    # Return all the data (including calculated areas from diameters)
    return {
        'anode_mass': anode_mass,
        'cathode_mass': cathode_mass,
        'anode_loading': anode_loading,
        'cathode_loading': cathode_loading,
        'anode_thickness': anode_thickness,
        'cathode_thickness': cathode_thickness,
        'anode_diameter': anode_diameter,
        'cathode_diameter': cathode_diameter,
        'anode_area': anode_area,
        'cathode_area': cathode_area,
        'overhang_ratio': overhang_ratio,
        'np_ratio_estimate': np_ratio_est
    }


def render_cell_inputs(context_key=None, project_id=None, get_components_func=None, experiment_name=None, project_type='Full Cell'):
    """Render multi-file upload and per-file inputs for each cell. Returns datasets list.
    
    Args:
        context_key: Unique key for this render context
        project_id: ID of the project for defaults
        get_components_func: Function to get formulation components
        experiment_name: Name of experiment for auto-generating cell names (e.g., "Test i", "Test ii")
    """
    if context_key is None:
        context_key = str(uuid.uuid4())
    
    # Get project preferences for defaults
    project_defaults = {}
    if project_id:
        try:
            from preference_components import get_default_values_for_experiment
            project_defaults = get_default_values_for_experiment(project_id)
        except ImportError:
            project_defaults = {}
    
    # Render Full Cell specific inputs first if this is a Full Cell project
    full_cell_data = None
    if project_type == 'Full Cell':
        # Get cell format from session state (set in app.py)
        cell_format = st.session_state.get('current_cell_format', 'Coin')
        full_cell_data = render_full_cell_mass_balance_inputs(context_key, cell_format=cell_format)
        st.markdown("---")
    
    with st.expander('🧪 Cell Inputs', expanded=True):
        upload_key = f"multi_file_upload_{context_key}"
        uploaded_files = st.file_uploader('Upload CSV or XLSX file(s) for Cells', type=['csv', 'xlsx'], accept_multiple_files=True, key=upload_key)
        st.caption("💡 Supported formats: Biologic CSV files (semicolon-delimited), Neware XLSX files (with 'cycle' sheet), and MTI XLSX files (with 'Cycle List1' sheet)")
        datasets = []
        if uploaded_files:
            # Handle multiple cells with assign-to-all functionality
            if len(uploaded_files) > 1:
                # First cell with assign-to-all checkbox
                with st.expander(f'Cell 1: {uploaded_files[0].name}', expanded=False):
                    col1, col2 = st.columns(2)
                    # --- Defaults logic with project preferences ---
                    loading_default = st.session_state.get('loading_0', 20.0)
                    active_default = st.session_state.get('active_0', 90.0)
                    # Handle formation cycles from project defaults (could be string or int)
                    formation_cycles_default = project_defaults.get('formation_cycles', 4)
                    if isinstance(formation_cycles_default, str):
                        try:
                            formation_cycles_default = int(formation_cycles_default)
                        except (ValueError, TypeError):
                            formation_cycles_default = 4
                    formation_default = st.session_state.get('formation_cycles_0', formation_cycles_default)
                    # Prioritize project defaults for electrolyte and substrate
                    electrolyte_default = st.session_state.get('electrolyte_0', project_defaults.get('electrolyte', '1M LiPF6 1:1:1'))
                    substrate_default = st.session_state.get('substrate_0', project_defaults.get('substrate', 'Copper'))
                    separator_default = st.session_state.get('separator_0', project_defaults.get('separator', '25um PP'))
                    with col1:
                        disc_loading_0 = st.number_input(f'Disc loading (mg) for Cell 1', min_value=0.0, step=1.0, value=loading_default, key=f'loading_0')
                        formation_cycles_0 = st.number_input(f'Formation Cycles for Cell 1', min_value=0, step=1, value=formation_default, key=f'formation_cycles_0')
                    with col2:
                        active_material_0 = st.number_input(f'% Active material for Cell 1', min_value=0.0, max_value=100.0, step=1.0, value=active_default, key=f'active_0')
                        # Auto-generate cell name using experiment name + roman numeral
                        default_cell_name = f"{experiment_name} {int_to_roman(1)}" if experiment_name else 'Cell 1'
                        test_number_0 = st.text_input(f'Test Number for Cell 1', value=default_cell_name, key=f'testnum_0')
                    
                    # Electrolyte, Substrate, and Separator selection
                    substrate_options = get_substrate_options()
                    
                    col3, col4, col5 = st.columns(3)
                    with col3:
                        electrolyte_0 = render_hybrid_electrolyte_input(
                            f'Electrolyte for Cell 1', 
                            default_value=electrolyte_default,
                            key=f'electrolyte_0'
                        )
                    with col4:
                        substrate_0 = st.selectbox(f'Substrate for Cell 1', substrate_options,
                                                 index=substrate_options.index(substrate_default) if substrate_default in substrate_options else 0,
                                                 key=f'substrate_0')
                    with col5:
                        separator_0 = render_hybrid_separator_input(
                            f'Separator for Cell 1', 
                            default_value=separator_default,
                            key=f'separator_0'
                        )
                    
                    # Cutoff voltages
                    col6, col7 = st.columns(2)
                    with col6:
                        cutoff_lower_0 = st.number_input(
                            'Lower Cutoff Voltage (V)', 
                            min_value=0.0, 
                            max_value=10.0, 
                            value=st.session_state.get('cutoff_lower_0', 2.5),
                            step=0.1,
                            key='cutoff_lower_0',
                            help="Lower voltage cutoff (e.g., 2.5V). Auto-extracted from MTI/Neware files."
                        )
                    with col7:
                        cutoff_upper_0 = st.number_input(
                            'Upper Cutoff Voltage (V)', 
                            min_value=0.0, 
                            max_value=10.0, 
                            value=st.session_state.get('cutoff_upper_0', 4.2),
                            step=0.1,
                            key='cutoff_upper_0',
                            help="Upper voltage cutoff (e.g., 4.2V). Auto-extracted from MTI/Neware files."
                        )
                    
                    # Formulation table
                    st.markdown("**Formulation:**")
                    formulation_0 = render_formulation_table(f'formulation_0_{context_key}', project_id, get_components_func)
                    
                    # Toggle for using same formulation across all cells (default True)
                    use_same_formulation_key = f'use_same_formulation_{context_key}'
                    if use_same_formulation_key not in st.session_state:
                        st.session_state[use_same_formulation_key] = True  # Default to True
                    use_same_formulation = st.checkbox('💾 Use same formulation for all cells', 
                                                      value=st.session_state[use_same_formulation_key],
                                                      key=use_same_formulation_key,
                                                      help="When enabled, all cells will use the same formulation from Cell 1")
                    
                    # Sync formulation to all other cells if toggle is enabled
                    if use_same_formulation and len(uploaded_files) > 1:
                        import copy
                        formulation_key_0 = f'formulation_data_formulation_0_{context_key}'
                        save_flag_key_0 = f'formulation_saved_formulation_0_{context_key}'
                        if formulation_key_0 in st.session_state:
                            for i in range(1, len(uploaded_files)):
                                formulation_key_i = f'formulation_data_formulation_{i}_{context_key}'
                                st.session_state[formulation_key_i] = copy.deepcopy(st.session_state[formulation_key_0])
                                save_flag_key_i = f'formulation_saved_formulation_{i}_{context_key}'
                                if save_flag_key_0 in st.session_state:
                                    st.session_state[save_flag_key_i] = st.session_state[save_flag_key_0]
                    
                    assign_all = st.checkbox('Assign values to all cells', key=f'assign_all_cells_{context_key}')
                
                # Add first cell to datasets
                datasets.append({
                    'file': uploaded_files[0], 
                    'loading': disc_loading_0, 
                    'active': active_material_0, 
                    'testnum': test_number_0, 
                    'formation_cycles': formation_cycles_0,
                    'electrolyte': electrolyte_0,
                    'substrate': substrate_0,
                    'separator': separator_0,
                    'formulation': formulation_0,
                    'cutoff_voltage_lower': cutoff_lower_0,
                    'cutoff_voltage_upper': cutoff_upper_0
                })
                
                # Handle remaining cells
                for i in range(1, len(uploaded_files)):
                    uploaded_file = uploaded_files[i]
                    with st.expander(f'Cell {i+1}: {uploaded_file.name}', expanded=False):
                        col1, col2 = st.columns(2)
                        if assign_all:
                            # Use values from first cell
                            disc_loading = disc_loading_0
                            formation_cycles = formation_cycles_0
                            active_material = active_material_0
                            electrolyte = electrolyte_0
                            substrate = substrate_0
                            separator = separator_0
                            formulation = formulation_0
                            cutoff_lower = cutoff_lower_0
                            cutoff_upper = cutoff_upper_0
                        else:
                            # Individual inputs for this cell
                            loading_default = st.session_state.get(f'loading_{i}', disc_loading_0)
                            active_default = st.session_state.get(f'active_{i}', active_material_0)
                            # Handle formation cycles from project defaults for subsequent cells
                            formation_cycles_default = project_defaults.get('formation_cycles', formation_cycles_0)
                            if isinstance(formation_cycles_default, str):
                                try:
                                    formation_cycles_default = int(formation_cycles_default)
                                except (ValueError, TypeError):
                                    formation_cycles_default = formation_cycles_0
                            formation_default = st.session_state.get(f'formation_cycles_{i}', formation_cycles_default)
                            electrolyte_default = st.session_state.get(f'electrolyte_{i}', electrolyte_0)
                            substrate_default = st.session_state.get(f'substrate_{i}', substrate_0)
                            separator_default = st.session_state.get(f'separator_{i}', separator_0)
                            with col1:
                                disc_loading = st.number_input(f'Disc loading (mg) for Cell {i+1}', min_value=0.0, step=1.0, value=loading_default, key=f'loading_{i}')
                                formation_cycles = st.number_input(f'Formation Cycles for Cell {i+1}', min_value=0, step=1, value=formation_default, key=f'formation_cycles_{i}')
                            with col2:
                                active_material = st.number_input(f'% Active material for Cell {i+1}', min_value=0.0, max_value=100.0, step=1.0, value=active_default, key=f'active_{i}')
                            
                            # Electrolyte, Substrate, and Separator selection
                            electrolyte = render_hybrid_electrolyte_input(
                                f'Electrolyte for Cell {i+1}', 
                                default_value=electrolyte_default,
                                key=f'electrolyte_{i}'
                            )
                            
                            # Substrate selection
                            substrate = st.selectbox(f'Substrate for Cell {i+1}', substrate_options,
                                                   index=substrate_options.index(substrate_default) if substrate_default in substrate_options else 0,
                                                   key=f'substrate_{i}')
                            
                            # Separator selection
                            separator = render_hybrid_separator_input(
                                f'Separator for Cell {i+1}', 
                                default_value=separator_default,
                                key=f'separator_{i}'
                            )
                            
                            # Cutoff voltages
                            cutoff_col1, cutoff_col2 = st.columns(2)
                            with cutoff_col1:
                                cutoff_lower = st.number_input(
                                    f'Lower Cutoff Voltage (V) for Cell {i+1}', 
                                    min_value=0.0, 
                                    max_value=10.0, 
                                    value=st.session_state.get(f'cutoff_lower_{i}', cutoff_lower_0),
                                    step=0.1,
                                    key=f'cutoff_lower_{i}',
                                    help="Lower voltage cutoff (e.g., 2.5V). Auto-extracted from MTI/Neware files."
                                )
                            with cutoff_col2:
                                cutoff_upper = st.number_input(
                                    f'Upper Cutoff Voltage (V) for Cell {i+1}', 
                                    min_value=0.0, 
                                    max_value=10.0, 
                                    value=st.session_state.get(f'cutoff_upper_{i}', cutoff_upper_0),
                                    step=0.1,
                                    key=f'cutoff_upper_{i}',
                                    help="Upper voltage cutoff (e.g., 4.2V). Auto-extracted from MTI/Neware files."
                                )
                            
                            # Formulation table - use same formulation if toggle is enabled
                            use_same_formulation_key = f'use_same_formulation_{context_key}'
                            use_same_formulation = st.session_state.get(use_same_formulation_key, True)
                            
                            if use_same_formulation:
                                # Use formulation from first cell and sync it
                                formulation = formulation_0
                                # Sync the formulation data to this cell's session state
                                # The key format is: formulation_data_{key_suffix} where key_suffix is f'formulation_{i}_{context_key}'
                                formulation_key_i = f'formulation_data_formulation_{i}_{context_key}'
                                formulation_key_0 = f'formulation_data_formulation_0_{context_key}'
                                if formulation_key_0 in st.session_state:
                                    import copy
                                    st.session_state[formulation_key_i] = copy.deepcopy(st.session_state[formulation_key_0])
                                # Also sync the save flag
                                save_flag_key_i = f'formulation_saved_formulation_{i}_{context_key}'
                                save_flag_key_0 = f'formulation_saved_formulation_0_{context_key}'
                                if save_flag_key_0 in st.session_state:
                                    st.session_state[save_flag_key_i] = st.session_state[save_flag_key_0]
                                st.info("💡 Using same formulation as Cell 1. Edit Cell 1's formulation or uncheck 'Use same formulation for all cells' to customize.")
                            else:
                                # Individual formulation for this cell
                                st.markdown("**Formulation:**")
                                formulation = render_formulation_table(f'formulation_{i}_{context_key}', project_id, get_components_func)
                        
                        # Test number is always individual (not assigned to all)
                        with col2:
                            # Auto-generate cell name using experiment name + roman numeral
                            default_test_num = f"{experiment_name} {int_to_roman(i+1)}" if experiment_name else f'Cell {i+1}'
                            test_number = st.text_input(f'Test Number for Cell {i+1}', value=default_test_num, key=f'testnum_{i}')
                        
                        datasets.append({
                            'file': uploaded_file, 
                            'loading': disc_loading, 
                            'active': active_material, 
                            'testnum': test_number, 
                            'formation_cycles': formation_cycles,
                            'electrolyte': electrolyte,
                            'substrate': substrate,
                            'separator': separator,
                            'formulation': formulation,
                            'cutoff_voltage_lower': cutoff_lower,
                            'cutoff_voltage_upper': cutoff_upper
                        })
            else:
                # Single cell - no assign-to-all needed
                uploaded_file = uploaded_files[0]
                with st.expander(f'Cell 1: {uploaded_file.name}', expanded=False):
                    col1, col2 = st.columns(2)
                    # --- Defaults logic ---
                    loading_default = st.session_state.get('loading_0', 20.0)
                    active_default = st.session_state.get('active_0', 90.0)
                    # Handle formation cycles from project defaults for single cell
                    formation_cycles_default = project_defaults.get('formation_cycles', 4)
                    if isinstance(formation_cycles_default, str):
                        try:
                            formation_cycles_default = int(formation_cycles_default)
                        except (ValueError, TypeError):
                            formation_cycles_default = 4
                    formation_default = st.session_state.get('formation_cycles_0', formation_cycles_default)
                    # Prioritize project defaults for electrolyte, substrate, and separator
                    electrolyte_default = st.session_state.get('electrolyte_0', project_defaults.get('electrolyte', '1M LiPF6 1:1:1'))
                    substrate_default = st.session_state.get('substrate_0', project_defaults.get('substrate', 'Copper'))
                    separator_default = st.session_state.get('separator_0', project_defaults.get('separator', '25um PP'))
                    with col1:
                        disc_loading = st.number_input(f'Disc loading (mg) for Cell 1', min_value=0.0, step=1.0, value=loading_default, key=f'loading_0')
                        formation_cycles = st.number_input(f'Formation Cycles for Cell 1', min_value=0, step=1, value=formation_default, key=f'formation_cycles_0')
                    with col2:
                        active_material = st.number_input(f'% Active material for Cell 1', min_value=0.0, max_value=100.0, step=1.0, value=active_default, key=f'active_0')
                        # Auto-generate cell name using experiment name + roman numeral
                        default_cell_name = f"{experiment_name} {int_to_roman(1)}" if experiment_name else 'Cell 1'
                        test_number = st.text_input(f'Test Number for Cell 1', value=default_cell_name, key=f'testnum_0')
                    
                    # Electrolyte, Substrate, and Separator selection
                    substrate_options = get_substrate_options()
                    
                    col3, col4, col5 = st.columns(3)
                    with col3:
                        electrolyte = render_hybrid_electrolyte_input(
                            f'Electrolyte for Cell 1', 
                            default_value=electrolyte_default,
                            key=f'electrolyte_0'
                        )
                    with col4:
                        substrate = st.selectbox(f'Substrate for Cell 1', substrate_options,
                                               index=substrate_options.index(substrate_default) if substrate_default in substrate_options else 0,
                                               key=f'substrate_0')
                    with col5:
                        separator = render_hybrid_separator_input(
                            f'Separator for Cell 1', 
                            default_value=separator_default,
                            key=f'separator_0'
                        )
                    
                    # Cutoff voltages
                    cutoff_col1, cutoff_col2 = st.columns(2)
                    with cutoff_col1:
                        cutoff_lower = st.number_input(
                            'Lower Cutoff Voltage (V)', 
                            min_value=0.0, 
                            max_value=10.0, 
                            value=st.session_state.get('cutoff_lower_0', 2.5),
                            step=0.1,
                            key='cutoff_lower_0_single',
                            help="Lower voltage cutoff (e.g., 2.5V). Auto-extracted from MTI/Neware files."
                        )
                    with cutoff_col2:
                        cutoff_upper = st.number_input(
                            'Upper Cutoff Voltage (V)', 
                            min_value=0.0, 
                            max_value=10.0, 
                            value=st.session_state.get('cutoff_upper_0', 4.2),
                            step=0.1,
                            key='cutoff_upper_0_single',
                            help="Upper voltage cutoff (e.g., 4.2V). Auto-extracted from MTI/Neware files."
                        )
                    
                    # Formulation table
                    st.markdown("**Formulation:**")
                    formulation = render_formulation_table(f'formulation_0_{context_key}', project_id, get_components_func)
                    
                    datasets.append({
                        'file': uploaded_file, 
                        'loading': disc_loading, 
                        'active': active_material, 
                        'testnum': test_number, 
                        'formation_cycles': formation_cycles,
                        'electrolyte': electrolyte,
                        'substrate': substrate,
                        'separator': separator,
                        'formulation': formulation,
                        'cutoff_voltage_lower': cutoff_lower,
                        'cutoff_voltage_upper': cutoff_upper
                    })
    return datasets, full_cell_data

def render_formulation_table(key_suffix, project_id=None, get_components_func=None):
    """Render a formulation table with Component and Dry Mass Fraction columns using autocomplete."""
    # Initialize formulation data in session state if not exists
    formulation_key = f'formulation_data_{key_suffix}'
    save_flag_key = f'formulation_saved_{key_suffix}'
    
    # Get project preferences for default formulation
    default_formulation = []
    if project_id:
        try:
            from preference_components import get_default_values_for_experiment
            project_defaults = get_default_values_for_experiment(project_id)
            default_formulation = project_defaults.get('formulation', [])
        except ImportError:
            default_formulation = []
    
    if formulation_key not in st.session_state:
        if default_formulation:
            st.session_state[formulation_key] = default_formulation
        else:
            st.session_state[formulation_key] = [
                {'Component': '', 'Dry Mass Fraction (%)': 0.0}
            ]
    if save_flag_key not in st.session_state:
        st.session_state[save_flag_key] = True  # Default to True (saved/on by default)
    
    formulation_data = st.session_state[formulation_key]
    
    # Get previously used components from project if project_id and function are provided
    previous_components = []
    if project_id and get_components_func:
        try:
            previous_components = get_components_func(project_id)
        except Exception:
            previous_components = []
    
    # Combine battery materials with previous components for autocomplete
    all_materials = get_all_battery_materials() + previous_components
    # Remove duplicates while preserving order
    seen = set()
    unique_materials = []
    for material in all_materials:
        if material not in seen:
            unique_materials.append(material)
            seen.add(material)
    
    # Create editable table
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        st.markdown("**Component**")
    with col2:
        st.markdown("**Dry Mass Fraction (%)**")
    with col3:
        st.markdown("**Actions**")
    
    # Display all rows (including empty ones)
    updated_formulation = []
    total_fraction = 0.0
    changed = False
    
    for i, row in enumerate(formulation_data):
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            # Use autocomplete input for component selection
            component = render_autocomplete_input(
                key=f'component_{i}_{key_suffix}',
                label="Component",
                placeholder="Type to search materials...",
                value=row['Component'],
                materials=unique_materials,
                allow_custom=True
            )
                
        with col2:
            fraction = st.number_input(f"Fraction", value=row['Dry Mass Fraction (%)'], min_value=0.0, max_value=100.0, step=0.1, key=f'fraction_{i}_{key_suffix}', label_visibility="collapsed")
            total_fraction += fraction
        with col3:
            if st.button("🗑️", key=f'delete_{i}_{key_suffix}', help="Delete row"):
                # Remove this row and update session state
                st.session_state[formulation_key] = [row for j, row in enumerate(formulation_data) if j != i]
                st.session_state[save_flag_key] = False
                st.rerun()
        # Detect changes
        if component != row['Component'] or fraction != row['Dry Mass Fraction (%)']:
            changed = True
        # Always keep all rows, even if empty
        updated_formulation.append({'Component': component, 'Dry Mass Fraction (%)': fraction})
    
    # Add new row button and Copy formulation button
    btn_col1, btn_col2 = st.columns([1, 1])
    
    with btn_col1:
        if st.button(f"➕ Add Component", key=f'add_component_{key_suffix}', use_container_width=True):
            st.session_state[formulation_key].append({'Component': '', 'Dry Mass Fraction (%)': 0.0})
            st.session_state[save_flag_key] = False
            st.rerun()
    
    with btn_col2:
        copy_button_key = f'show_copy_{key_suffix}'
        if copy_button_key not in st.session_state:
            st.session_state[copy_button_key] = False
        
        if st.button(f"📋 Copy from...", key=f'copy_formulation_btn_{key_suffix}', use_container_width=True, help="Copy formulation from another experiment"):
            st.session_state[copy_button_key] = not st.session_state[copy_button_key]
            st.rerun()
    
    # Show copy formulation dropdown if button was clicked
    if st.session_state.get(copy_button_key, False) and project_id:
        try:
            from database import get_all_project_experiments_data
            import json
            
            # Get all experiments from the project
            experiments = get_all_project_experiments_data(project_id)
            
            # Filter experiments that have formulations
            experiments_with_formulations = []
            for exp in experiments:
                exp_id, cell_name, file_name, loading, active_material, formation_cycles, test_number, electrolyte, substrate, separator, formulation_json, data_json, created_date, porosity, experiment_notes = exp
                
                if formulation_json:
                    try:
                        formulation = json.loads(formulation_json)
                        if formulation and any(row.get('Component') for row in formulation):
                            experiments_with_formulations.append({
                                'id': exp_id,
                                'name': cell_name or file_name,
                                'formulation': formulation
                            })
                    except:
                        pass
            
            if experiments_with_formulations:
                # Create a clean dropdown for selecting experiment
                experiment_names = [f"{exp['name']}" for exp in experiments_with_formulations]
                
                st.markdown("---")
                selected_experiment_name = st.selectbox(
                    "Select experiment to copy formulation from:",
                    options=experiment_names,
                    key=f'copy_select_{key_suffix}',
                    help="Choose an experiment and click 'Copy' to import its formulation"
                )
                
                # Find the selected experiment
                selected_exp = next((exp for exp in experiments_with_formulations if exp['name'] == selected_experiment_name), None)
                
                if selected_exp:
                    # Show preview of the formulation
                    with st.expander("Preview formulation", expanded=True):
                        preview_df = pd.DataFrame(selected_exp['formulation'])
                        if not preview_df.empty:
                            st.dataframe(preview_df, use_container_width=True, hide_index=True)
                    
                    # Copy button
                    copy_col1, copy_col2 = st.columns([1, 1])
                    with copy_col1:
                        if st.button("✅ Copy This Formulation", key=f'execute_copy_{key_suffix}', type="primary", use_container_width=True):
                            import copy
                            st.session_state[formulation_key] = copy.deepcopy(selected_exp['formulation'])
                            st.session_state[save_flag_key] = False
                            st.session_state[copy_button_key] = False  # Hide the copy interface
                            st.success(f"✅ Copied formulation from '{selected_experiment_name}'")
                            st.rerun()
                    with copy_col2:
                        if st.button("❌ Cancel", key=f'cancel_copy_{key_suffix}', use_container_width=True):
                            st.session_state[copy_button_key] = False
                            st.rerun()
                st.markdown("---")
            else:
                st.info("💡 No other experiments with formulations found in this project.")
                if st.button("Close", key=f'close_copy_info_{key_suffix}'):
                    st.session_state[copy_button_key] = False
                    st.rerun()
        except Exception as e:
            st.error(f"Error loading experiments: {e}")
            if st.button("Close", key=f'close_copy_error_{key_suffix}'):
                st.session_state[copy_button_key] = False
                st.rerun()
    
    # If any changes, reset the save flag
    if changed:
        st.session_state[save_flag_key] = False
    
    # Save/Done Editing button - only show if not in preferences modal
    if not key_suffix.startswith('pref_formulation_editor'):
        if st.button("💾 Save Formulation", key=f'save_formulation_{key_suffix}'):
            st.session_state[save_flag_key] = True
    
    # Validation (only show if saved)
    if st.session_state[save_flag_key]:
        if total_fraction > 100.0:
            st.error(f"⚠️ Total dry mass fraction ({total_fraction:.1f}%) exceeds 100%!")
        elif total_fraction < 99.9 and any(row['Component'] for row in updated_formulation):
            st.warning(f"⚠️ Total dry mass fraction ({total_fraction:.1f}%) is less than 100%")
        elif total_fraction >= 99.9 and total_fraction <= 100.1:
            st.success(f"✅ Total dry mass fraction: {total_fraction:.1f}%")
    
    # Update session state (keep all rows, even empty)
    st.session_state[formulation_key] = updated_formulation if updated_formulation else [{'Component': '', 'Dry Mass Fraction (%)': 0.0}]
    
    # Only filter out empty rows when returning
    filtered = [row for row in updated_formulation if row['Component'] or row['Dry Mass Fraction (%)'] > 0]
    return filtered

def get_qdis_series(df_cell):
    qdis_raw = df_cell['Q Dis (mAh/g)']
    if pd.api.types.is_scalar(qdis_raw):
        return pd.Series([qdis_raw]).dropna()
    else:
        return pd.Series(qdis_raw).dropna()

def calculate_cycle_life_80(qdis_series, cycle_index_series):
    if len(qdis_series) >= 4:
        initial_qdis = max(qdis_series.iloc[2], qdis_series.iloc[3])
    elif len(qdis_series) > 0:
        initial_qdis = qdis_series.iloc[-1]
    else:
        return None
    threshold = 0.8 * initial_qdis
    below_threshold = qdis_series <= threshold
    if below_threshold.any():
        first_below_idx = below_threshold.idxmin()
        return int(cycle_index_series.iloc[first_below_idx])
    else:
        return int(cycle_index_series.iloc[-1])

# --- Helper for robust areal capacity calculation ---
def get_initial_areal_capacity(df_cell, disc_area_cm2):
    # Use max of cycles 3 and 4 if available, else last available
    qdis_col = 'Q discharge (mA.h)'
    eff_col = 'Efficiency (-)'
    n = len(df_cell)
    if qdis_col not in df_cell.columns or n == 0:
        return None, None, None, None
    # Get values for cycles 1, 3, 4
    val1 = abs(df_cell[qdis_col].iloc[0]) if n >= 1 and not pd.isnull(df_cell[qdis_col].iloc[0]) else None
    val3 = abs(df_cell[qdis_col].iloc[2]) if n >= 3 and not pd.isnull(df_cell[qdis_col].iloc[2]) else None
    val4 = abs(df_cell[qdis_col].iloc[3]) if n >= 4 and not pd.isnull(df_cell[qdis_col].iloc[3]) else None
    # Choose best initial
    if n >= 4 and val3 is not None and val4 is not None:
        chosen_val = max(val3, val4)
        chosen_cycle = 4 if val4 >= val3 else 3
    elif n >= 4 and val3 is not None:
        chosen_val = val3
        chosen_cycle = 3
    elif n >= 4 and val4 is not None:
        chosen_val = val4
        chosen_cycle = 4
    elif n >= 3 and val3 is not None:
        chosen_val = val3
        chosen_cycle = 3
    else:
        last_val = df_cell[qdis_col].iloc[-1]
        chosen_val = abs(last_val) if not pd.isnull(last_val) else None
        chosen_cycle = n
    areal_capacity = chosen_val / disc_area_cm2 if chosen_val is not None else None
    # Compare to cycle 1
    warn = False
    diff_pct = None
    if val1 is not None and chosen_val is not None and chosen_cycle != 1:
        diff_pct = abs(chosen_val - val1) / val1 if val1 != 0 else None
        if diff_pct is not None and diff_pct > 0.2:
            warn = True
    # Check efficiency for chosen cycle
    eff_val = None
    if eff_col in df_cell.columns and n >= chosen_cycle:
        eff_val = df_cell[eff_col].iloc[chosen_cycle-1] if not pd.isnull(df_cell[eff_col].iloc[chosen_cycle-1]) else None
        try:
            if eff_val is not None and float(eff_val) < 0.8:
                warn = True
        except (ValueError, TypeError):
            pass  # Ignore non-numeric efficiency values
    return areal_capacity, chosen_cycle, diff_pct, eff_val

def display_summary_stats(dfs: List[Dict[str, Any]], disc_area_cm2: float, show_average_col: bool = True, group_assignments: List[str] = None, group_names: List[str] = None):
    """Display summary statistics as a table in Streamlit."""
    import pandas as pd
    # Calculate metrics once for all cells
    cell_metrics = []
    for i, d in enumerate(dfs):
        metrics = calculate_cell_metrics(d['df'], d.get('formation_cycles', 4), disc_area_cm2)
        cell_metrics.append(metrics)
    # Prepare summary data - reordered as requested: Reversible capacity, coulombic efficiency, 1st cycle discharge, 1st cycle efficiency, cycle life
    param_names = [
        "Reversible Capacity (mAh/g)",
        "Coulombic Efficiency (post-formation)",
        "1st Cycle Discharge Capacity (mAh/g)",
        "First Cycle Efficiency (%)",
        "Cycle Life (80%)",
        "Initial Areal Capacity (mAh/cm²)"
    ]
    summary_dict = {param: [] for param in param_names}
    cell_names = []
    for i, (d, metrics) in enumerate(zip(dfs, cell_metrics)):
        cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
        cell_names.append(cell_name)
        summary_dict[param_names[0]].append(metrics['reversible_capacity'])
        summary_dict[param_names[1]].append(metrics['coulombic_eff'])
        summary_dict[param_names[2]].append(metrics['max_qdis'])
        summary_dict[param_names[3]].append(metrics['first_cycle_eff'])
        summary_dict[param_names[4]].append(metrics['cycle_life_80'])
        summary_dict[param_names[5]].append(metrics['areal_capacity'])
    # Add group summary rows if grouping is enabled
    group_names_final = []
    if group_assignments is not None and group_names is not None:
        for group_idx, group_name in enumerate(group_names):
            group_indices = [i for i, g in enumerate(group_assignments) if g == group_name]
            if len(group_indices) > 1:
                group_metrics = [cell_metrics[i] for i in group_indices]
                # Calculate group averages
                avg_values = {}
                for param_key in ['max_qdis', 'first_cycle_eff', 'cycle_life_80', 'areal_capacity', 'reversible_capacity', 'coulombic_eff']:
                    values = [m[param_key] for m in group_metrics if m[param_key] is not None]
                    avg_values[param_key] = sum(values) / len(values) if values else None
                # Add to summary
                for i, param in enumerate(param_names):
                    param_keys = ['reversible_capacity', 'coulombic_eff', 'max_qdis', 'first_cycle_eff', 'cycle_life_80', 'areal_capacity']
                    summary_dict[param].append(avg_values[param_keys[i]])
                group_names_final.append(group_name + " (Group Avg)")
    # Compute overall averages
    if show_average_col and len(dfs) > 1:
        for param in param_names:
            vals = [v for v in summary_dict[param] if v is not None]
            avg = sum(vals) / len(vals) if vals else None
            summary_dict[param].append(avg)
        col_labels = cell_names + group_names_final + ["Average"]
    else:
        col_labels = cell_names + group_names_final
    # Ensure unique column labels (cell names, group names, Average)
    def make_unique(labels):
        seen = {}
        result = []
        for label in labels:
            if label not in seen:
                seen[label] = 1
                result.append(label)
            else:
                seen[label] += 1
                result.append(f"{label} ({seen[label]})")
        return result
    col_labels = make_unique(col_labels)
    # Format for display (updated for new column order)
    display_data = {}
    for idx, param in enumerate(param_names):
        row = []
        for v in summary_dict[param]:
            if v is None:
                row.append("N/A")
            elif idx == 0:  # Reversible Capacity (mAh/g) - 1 decimal place
                row.append(f"{v:.1f}")
            elif idx == 1:  # Coulombic Efficiency (post-formation) - 3 decimal places
                row.append(f"{v:.3f}%")
            elif idx == 2:  # 1st Cycle Discharge Capacity (mAh/g) - 1 decimal place
                row.append(f"{v:.1f}")
            elif idx == 3:  # First Cycle Efficiency (%) - 3 decimal places
                row.append(f"{v:.3f}%")
            elif idx == 4:  # Cycle Life (80%) - 1 decimal place
                row.append(f"{v:.1f}")
            elif idx == 5:  # Initial Areal Capacity (mAh/cm²) - 2 decimal places
                row.append(f"{v:.2f}")
            else:
                row.append(f"{v:.1f}")
        display_data[param] = row
    df = pd.DataFrame(display_data, index=col_labels).T
    df = df.T
    # Keep existing styling logic
    def style_table(styler):
        styler.set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#2563eb'), ('color', '#fff'), ('font-weight', 'bold'), ('font-size', '1.1em'), ('border-radius', '8px 8px 0 0'), ('padding', '10px')]},
            {'selector': 'td', 'props': [('background-color', '#fff'), ('color', '#222'), ('font-size', '1em'), ('padding', '10px')]},
            {'selector': 'tr:hover td', 'props': [('background-color', '#e0e7ef')]} ,
            {'selector': 'table', 'props': [('border-collapse', 'separate'), ('border-spacing', '0'), ('border-radius', '12px'), ('overflow', 'hidden'), ('box-shadow', '0 2px 8px rgba(0,0,0,0.07)')]} 
        ])
        styler.apply(lambda x: ['background-color: #f3f6fa' if i%2==0 else '' for i in range(len(x))], axis=1)
        for group_name in group_names_final:
            if group_name in df.index:
                styler.apply(lambda x: ['background-color: #fef3c7' if x.name == group_name else '' for _ in x], axis=1)
        if 'Average' in df.index:
            styler.apply(lambda x: ['background-color: #fbbf24' if x.name == 'Average' else '' for _ in x], axis=1)
        styler.set_properties(**{'border': '1px solid #d1d5db'})
        return styler
    styled = df.style.pipe(style_table)
    st.markdown('<style>table {margin-bottom: 2em;} th, td {text-align: center !important;} </style>', unsafe_allow_html=True)
    st.write(styled.to_html(escape=False), unsafe_allow_html=True)


def display_averages(dfs: List[Dict[str, Any]], show_averages: bool, disc_area_cm2: float):
    """Display averages in Streamlit if requested."""
    if show_averages and len(dfs) > 1:
        st.markdown("---")
        with st.expander("Average Values Across All Cells", expanded=True):
            # Calculate metrics once for all cells
            all_metrics = []
            for d in dfs:
                metrics = calculate_cell_metrics(d['df'], d.get('formation_cycles', 4), disc_area_cm2)
                all_metrics.append(metrics)
            
            # Calculate averages
            def safe_average(values):
                valid_values = [v for v in values if v is not None]
                return sum(valid_values) / len(valid_values) if valid_values else None
            
            avg_qdis = safe_average([m['max_qdis'] for m in all_metrics])
            avg_eff = safe_average([m['first_cycle_eff'] for m in all_metrics])
            avg_cycle_life = safe_average([m['cycle_life_80'] for m in all_metrics])
            avg_areal = safe_average([m['areal_capacity'] for m in all_metrics])
            avg_reversible = safe_average([m['reversible_capacity'] for m in all_metrics])
            avg_ceff = safe_average([m['coulombic_eff'] for m in all_metrics])
            
            # Display results
            if avg_qdis is not None:
                st.info(f"1st Cycle Discharge Capacity (mAh/g): {avg_qdis:.1f}")
            if avg_eff is not None:
                st.info(f"First Cycle Efficiency: {avg_eff:.1f}%")
            else:
                st.warning('No data for average First Cycle Efficiency.')
            if avg_cycle_life is not None:
                st.info(f"Cycle Life (80%): {avg_cycle_life:.0f}")
            if avg_areal is not None:
                st.info(f"Initial Areal Capacity (mAh/cm²): {avg_areal:.3f}")
            if avg_reversible is not None:
                st.info(f"Reversible Capacity (mAh/g): {avg_reversible:.1f}")
            else:
                st.warning('No data for average Reversible Capacity after formation.')
            if avg_ceff is not None:
                st.info(f"Coulombic Efficiency (post-formation): {avg_ceff:.2f}%")
            else:
                st.warning('No data for average Coulombic Efficiency (post-formation).')


def get_default_color_palette():
    """Get the default color palette matching the plotting module."""
    return ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']


def render_comparison_color_customization(experiments_data: List[Dict[str, Any]], show_average_performance: bool = False) -> Dict[str, str]:
    """
    Render color customization UI for comparison plots.
    
    Args:
        experiments_data: List of experiment data dictionaries
        show_average_performance: Whether average performance lines are being shown
        
    Returns:
        Dictionary mapping dataset labels to custom colors
    """
    default_colors = get_default_color_palette()
    
    # Initialize session state for custom colors if not exists
    if 'comp_custom_colors' not in st.session_state:
        st.session_state.comp_custom_colors = {}
    
    # Collect all datasets that will be shown
    all_datasets = []
    
    for exp_idx, exp_data in enumerate(experiments_data):
        exp_name = exp_data['experiment_name']
        dfs = exp_data['dfs']
        default_color = default_colors[exp_idx % len(default_colors)]
        
        # Individual cell datasets (only if not showing averages)
        if not show_average_performance:
            for cell_idx, d in enumerate(dfs):
                cell_name = d['testnum'] if d['testnum'] else f'Cell {cell_idx+1}'
                all_datasets.append({
                    'label': f"{exp_name} - {cell_name}",
                    'exp_name': exp_name,
                    'cell_name': cell_name,
                    'default_color': default_color,
                    'is_average': False
                })
        
        # Average datasets (if showing averages and multiple cells)
        if show_average_performance and len(dfs) > 1:
            all_datasets.append({
                'label': f"{exp_name} - Average",
                'exp_name': exp_name,
                'cell_name': 'Average',
                'default_color': default_color,
                'is_average': True
            })
    
    # Render color customization UI
    with st.expander("🎨 Dataset Color Customization", expanded=False):
        st.markdown("### Customize Dataset Colors")
        st.info("💡 Select custom colors for each dataset. Colors persist during the session and apply to all plot types.")
        
        # Reset button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Reset All Colors", key="comp_reset_colors", use_container_width=True):
                st.session_state.comp_custom_colors = {}
                st.rerun()
        
        # Color pickers for each dataset
        if all_datasets:
            # Group by experiment for better organization
            experiments_groups = {}
            for dataset in all_datasets:
                exp_name = dataset['exp_name']
                if exp_name not in experiments_groups:
                    experiments_groups[exp_name] = []
                experiments_groups[exp_name].append(dataset)
            
            for exp_name, datasets in experiments_groups.items():
                st.markdown(f"#### 📊 {exp_name}")
                
                # Create columns for color pickers
                cols_per_row = 3
                for i in range(0, len(datasets), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for col_idx, dataset in enumerate(datasets[i:i+cols_per_row]):
                        with cols[col_idx]:
                            label = dataset['label']
                            default_color = dataset['default_color']
                            
                            # Get current custom color or use default
                            current_color = st.session_state.comp_custom_colors.get(label, default_color)
                            
                            # Color picker
                            new_color = st.color_picker(
                                f"{dataset['cell_name']}",
                                value=current_color,
                                key=f"comp_color_{label}",
                                help=f"Choose color for {label}"
                            )
                            
                            # Update session state if color changed
                            if new_color != default_color:
                                st.session_state.comp_custom_colors[label] = new_color
                            elif label in st.session_state.comp_custom_colors and new_color == default_color:
                                # User reset to default
                                del st.session_state.comp_custom_colors[label]
                
                st.markdown("---")
        else:
            st.info("No datasets available for color customization.")
    
    return st.session_state.comp_custom_colors


def render_experiment_color_customization(dfs: List[Dict[str, Any]], experiment_name: str, show_average_performance: bool = False, enable_grouping: bool = False, group_names: List[str] = None) -> Dict[str, str]:
    """
    Render color customization UI for individual experiment plots.
    
    Args:
        dfs: List of cell dataframes
        experiment_name: Name of the experiment
        show_average_performance: Whether average performance lines are being shown
        enable_grouping: Whether cell grouping is enabled
        group_names: List of group names if grouping is enabled
        
    Returns:
        Dictionary mapping dataset labels to custom colors
    """
    if group_names is None:
        group_names = ["Group A", "Group B", "Group C"]
    
    # Initialize session state for custom colors if not exists
    session_key = f'exp_custom_colors_{experiment_name}'
    if session_key not in st.session_state:
        st.session_state[session_key] = {}
    
    # Collect all datasets
    all_datasets = []
    
    # Get matplotlib default color cycle
    import matplotlib.pyplot as plt
    default_colors_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    
    # Individual cell datasets
    if not show_average_performance:
        for i, d in enumerate(dfs):
            cell_name = d['testnum'] if d['testnum'] else f'Cell {i+1}'
            default_color = default_colors_cycle[i % len(default_colors_cycle)]
            all_datasets.append({
                'label': cell_name,
                'default_color': default_color,
                'type': 'cell'
            })
    
    # Average datasets
    if show_average_performance and len(dfs) > 1:
        all_datasets.append({
            'label': 'Average',
            'default_color': '#000000',  # Black for average
            'type': 'average'
        })
    
    # Group datasets
    if enable_grouping:
        group_colors = ['#0000FF', '#FF0000', '#00FF00']  # Blue, Red, Green
        for i, group_name in enumerate(group_names[:3]):
            all_datasets.append({
                'label': group_name,
                'default_color': group_colors[i],
                'type': 'group'
            })
    
    # Render color customization UI
    with st.expander("🎨 Dataset Color Customization", expanded=False):
        st.markdown("### Customize Dataset Colors")
        st.info("💡 Select custom colors for each dataset. Colors persist during the session.")
        
        # Reset button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Reset All Colors", key=f"exp_reset_colors_{experiment_name}", use_container_width=True):
                st.session_state[session_key] = {}
                st.rerun()
        
        # Color pickers for each dataset
        if all_datasets:
            # Group by type
            cell_datasets = [d for d in all_datasets if d['type'] == 'cell']
            average_datasets = [d for d in all_datasets if d['type'] == 'average']
            group_datasets = [d for d in all_datasets if d['type'] == 'group']
            
            # Individual cells
            if cell_datasets:
                st.markdown("#### 📱 Individual Cells")
                cols_per_row = 4
                for i in range(0, len(cell_datasets), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for col_idx, dataset in enumerate(cell_datasets[i:i+cols_per_row]):
                        with cols[col_idx]:
                            label = dataset['label']
                            default_color = dataset['default_color']
                            current_color = st.session_state[session_key].get(label, default_color)
                            
                            new_color = st.color_picker(
                                label,
                                value=current_color,
                                key=f"exp_color_{experiment_name}_{label}",
                                help=f"Choose color for {label}"
                            )
                            
                            if new_color != default_color:
                                st.session_state[session_key][label] = new_color
                            elif label in st.session_state[session_key] and new_color == default_color:
                                del st.session_state[session_key][label]
                
                st.markdown("---")
            
            # Averages
            if average_datasets:
                st.markdown("#### 📊 Average Lines")
                cols = st.columns(len(average_datasets))
                for col_idx, dataset in enumerate(average_datasets):
                    with cols[col_idx]:
                        label = dataset['label']
                        default_color = dataset['default_color']
                        current_color = st.session_state[session_key].get(label, default_color)
                        
                        new_color = st.color_picker(
                            label,
                            value=current_color,
                            key=f"exp_color_{experiment_name}_{label}",
                            help=f"Choose color for {label}"
                        )
                        
                        if new_color != default_color:
                            st.session_state[session_key][label] = new_color
                        elif label in st.session_state[session_key] and new_color == default_color:
                            del st.session_state[session_key][label]
                
                st.markdown("---")
            
            # Groups
            if group_datasets:
                st.markdown("#### 👥 Group Averages")
                cols = st.columns(len(group_datasets))
                for col_idx, dataset in enumerate(group_datasets):
                    with cols[col_idx]:
                        label = dataset['label']
                        default_color = dataset['default_color']
                        current_color = st.session_state[session_key].get(label, default_color)
                        
                        new_color = st.color_picker(
                            label,
                            value=current_color,
                            key=f"exp_color_{experiment_name}_{label}",
                            help=f"Choose color for {label}"
                        )
                        
                        if new_color != default_color:
                            st.session_state[session_key][label] = new_color
                        elif label in st.session_state[session_key] and new_color == default_color:
                            del st.session_state[session_key][label]
        else:
            st.info("No datasets available for color customization.")
    
    return st.session_state[session_key] 
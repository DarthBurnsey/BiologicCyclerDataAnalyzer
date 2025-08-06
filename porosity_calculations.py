# porosity_calculations.py
import math
from typing import List, Dict, Any, Optional

# Common theoretical densities for battery materials (g/cm³)
COMMON_THEORETICAL_DENSITIES = {
    'Graphite': 2.26,
    'Lithium Cobalt Oxide (LiCoO2)': 5.1,
    'Lithium Iron Phosphate (LiFePO4)': 3.6,
    'LFP': 3.6,  # Lithium Iron Phosphate
    'Lithium Nickel Manganese Cobalt Oxide (NMC)': 4.7,
    'Lithium Nickel Cobalt Aluminum Oxide (NCA)': 4.8,
    'Lithium Manganese Oxide (LiMn2O4)': 4.2,
    'Carbon Black': 1.8,
    'Super P': 1.8,
    'Ketjen Black': 1.8,
    'Vulcan XC-72': 1.8,
    'Cx(B)': 1.8,  # Carbon black variant
    'Cx(e)': 1.8,  # Carbon black variant
    'Polyvinylidene Fluoride (PVDF)': 1.78,
    'PVDF HSV900': 1.78,  # PVDF variant
    'Carboxymethyl Cellulose (CMC)': 1.6,
    'Styrene Butadiene Rubber (SBR)': 0.95,
    'Polyacrylic Acid (PAA)': 1.4,
    'LiPAA': 1.4,  # Lithium Polyacrylic Acid
    'Lithium Titanate (Li4Ti5O12)': 3.5,
    'Silicon': 2.33,
    'nano SI': 2.33,  # Nano Silicon
    'Tin': 7.31,
    'Aluminum': 2.7,
    'Copper': 8.96,
    'Nickel': 8.91,
    'Carbon Nanotubes (CNT)': 1.3,
    'Graphene': 2.26,
    'Activated Carbon': 1.5,
    'Carbon Fiber': 1.8,
    'Graphite Oxide': 1.8,
    'Reduced Graphene Oxide (rGO)': 2.0,
    'Lithium Metal': 0.534,
    'Sodium Metal': 0.968,
    'Zinc': 7.14,
    'Iron': 7.87,
    'Manganese': 7.21,
    'Cobalt': 8.9,
    'Nickel Oxide': 6.67,
    'Cobalt Oxide': 6.44,
    'Manganese Oxide': 5.43,
    'Aluminum Oxide': 3.95,
    'Silicon Oxide': 2.65,
    'Titanium Oxide': 4.23,
    'Zinc Oxide': 5.61,
    'Iron Oxide': 5.24,
    'Copper Oxide': 6.31,
    'Nickel Hydroxide': 4.1,
    'Cobalt Hydroxide': 3.6,
    'Manganese Hydroxide': 3.3,
    'Aluminum Hydroxide': 2.42,
    'Binder (Generic)': 1.5,
    'Conductive Additive (Generic)': 1.8,
    'Active Material (Generic)': 4.0
}

def get_theoretical_density(component_name: str) -> Optional[float]:
    """Get theoretical density for a component from common materials."""
    return COMMON_THEORETICAL_DENSITIES.get(component_name.strip())

def calculate_electrode_density(disc_mass_mg: float, disc_diameter_mm: float, pressed_thickness_um: float) -> float:
    """
    Calculate electrode density in g/cm³.
    
    Args:
        disc_mass_mg: Mass of the electrode disc in mg
        disc_diameter_mm: Diameter of the disc in mm
        pressed_thickness_um: Pressed thickness in micrometers
    
    Returns:
        Electrode density in g/cm³
    """
    # Validate inputs
    if not all(isinstance(x, (int, float)) and x > 0 for x in [disc_mass_mg, disc_diameter_mm, pressed_thickness_um]):
        return 0.0
    
    # Convert units
    disc_mass_g = disc_mass_mg / 1000.0  # mg to g
    disc_radius_cm = (disc_diameter_mm / 2) / 10.0  # mm to cm
    pressed_thickness_cm = pressed_thickness_um / 10000.0  # um to cm
    
    # Calculate volume: V = π * r² * h
    volume_cm3 = math.pi * (disc_radius_cm ** 2) * pressed_thickness_cm
    
    # Calculate density: ρ = m/V
    if volume_cm3 > 0:
        density_g_cm3 = disc_mass_g / volume_cm3
        return density_g_cm3
    else:
        return 0.0

def calculate_theoretical_density_from_formulation(formulation: List[Dict[str, Any]]) -> float:
    """
    Calculate theoretical density from formulation components.
    
    Args:
        formulation: List of dictionaries with 'Component' and 'Dry Mass Fraction (%)' keys
    
    Returns:
        Theoretical density in g/cm³
    """
    if not isinstance(formulation, list) or not formulation:
        return 0.0
    
    total_mass_fraction = 0.0
    total_volume_fraction = 0.0
    valid_components = 0
    
    for component in formulation:
        if not isinstance(component, dict):
            continue
            
        component_name = component.get('Component', '').strip()
        mass_fraction = component.get('Dry Mass Fraction (%)', 0.0) / 100.0  # Convert % to decimal
        
        if component_name and mass_fraction > 0:
            theoretical_density = get_theoretical_density(component_name)
            
            if theoretical_density and theoretical_density > 0:
                # Volume fraction = mass fraction / density
                volume_fraction = mass_fraction / theoretical_density
                total_volume_fraction += volume_fraction
                total_mass_fraction += mass_fraction
                valid_components += 1
    
    # Theoretical density = total mass / total volume
    if total_volume_fraction > 0 and valid_components > 0:
        theoretical_density = total_mass_fraction / total_volume_fraction
        return theoretical_density
    else:
        return 0.0

def calculate_porosity(electrode_density: float, theoretical_density: float) -> float:
    """
    Calculate porosity using the formula: porosity = 1 - (electrode_density / theoretical_density)
    
    Args:
        electrode_density: Measured electrode density in g/cm³
        theoretical_density: Theoretical density in g/cm³
    
    Returns:
        Porosity as a decimal (0.0 to 1.0)
    """
    if theoretical_density > 0:
        porosity = 1.0 - (electrode_density / theoretical_density)
        # Ensure porosity is between 0 and 1
        return max(0.0, min(1.0, porosity))
    else:
        return 0.0

def calculate_porosity_from_experiment_data(
    disc_mass_mg: float,
    disc_diameter_mm: float,
    pressed_thickness_um: float,
    formulation: List[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Calculate porosity from experiment data.
    
    Args:
        disc_mass_mg: Mass of the electrode disc in mg
        disc_diameter_mm: Diameter of the disc in mm
        pressed_thickness_um: Pressed thickness in micrometers
        formulation: List of formulation components
    
    Returns:
        Dictionary with calculated values:
        - electrode_density: g/cm³
        - theoretical_density: g/cm³
        - porosity: decimal (0.0 to 1.0)
    """
    # Validate inputs
    if not isinstance(formulation, list) or not formulation:
        return {
            'electrode_density': 0.0,
            'theoretical_density': 0.0,
            'porosity': 0.0
        }
    
    # Calculate electrode density
    electrode_density = calculate_electrode_density(disc_mass_mg, disc_diameter_mm, pressed_thickness_um)
    
    # Calculate theoretical density from formulation
    theoretical_density = calculate_theoretical_density_from_formulation(formulation)
    
    # Calculate porosity
    porosity = calculate_porosity(electrode_density, theoretical_density)
    
    # Validate results
    if electrode_density <= 0 or theoretical_density <= 0:
        return {
            'electrode_density': electrode_density,
            'theoretical_density': theoretical_density,
            'porosity': 0.0
        }
    
    return {
        'electrode_density': electrode_density,
        'theoretical_density': theoretical_density,
        'porosity': porosity
    }

def get_missing_density_components(formulation: List[Dict[str, Any]]) -> List[str]:
    """
    Get list of components that don't have theoretical densities.
    
    Args:
        formulation: List of formulation components
    
    Returns:
        List of component names missing theoretical densities
    """
    missing_components = []
    
    for component in formulation:
        component_name = component.get('Component', '').strip()
        mass_fraction = component.get('Dry Mass Fraction (%)', 0.0)
        
        if component_name and mass_fraction > 0:
            if get_theoretical_density(component_name) is None:
                missing_components.append(component_name)
    
    return missing_components

def format_porosity_display(porosity: float) -> str:
    """
    Format porosity for display.
    
    Args:
        porosity: Porosity as decimal (0.0 to 1.0)
    
    Returns:
        Formatted string (e.g., "45.2%")
    """
    if porosity >= 0:
        return f"{porosity * 100:.1f}%"
    else:
        return "N/A"
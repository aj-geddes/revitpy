"""
Performance analysis engine for building elements.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import time
from enum import Enum

from ..core.exceptions import BridgeAnalysisError


class AnalysisType(Enum):
    """Types of performance analysis."""
    
    THERMAL = "thermal"
    ENERGY = "energy" 
    STRUCTURAL = "structural"
    ACOUSTIC = "acoustic"
    DAYLIGHT = "daylight"
    AIRFLOW = "airflow"


@dataclass
class PerformanceMetric:
    """A single performance metric result."""
    
    name: str
    value: float
    unit: str
    benchmark: Optional[float] = None
    rating: Optional[str] = None  # excellent, good, fair, poor
    confidence: Optional[float] = None


@dataclass 
class PerformanceResult:
    """Result of performance analysis."""
    
    analysis_type: AnalysisType
    metrics: List[PerformanceMetric]
    overall_rating: str
    recommendations: List[Dict[str, Any]]
    analysis_time: float
    element_count: int


class ThermalAnalysisEngine:
    """Engine for thermal performance analysis."""
    
    def __init__(self):
        """Initialize thermal analysis engine."""
        self.logger = logging.getLogger('revitpy_bridge.thermal_analysis')
        
        # Thermal properties database
        self.material_properties = {
            'concrete': {'conductivity': 1.7, 'density': 2400, 'specific_heat': 880},
            'steel': {'conductivity': 50.0, 'density': 7850, 'specific_heat': 490},
            'wood': {'conductivity': 0.13, 'density': 500, 'specific_heat': 1600},
            'glass': {'conductivity': 1.0, 'density': 2500, 'specific_heat': 840},
            'insulation': {'conductivity': 0.04, 'density': 50, 'specific_heat': 1000},
            'air': {'conductivity': 0.026, 'density': 1.2, 'specific_heat': 1005}
        }
    
    def analyze_thermal_performance(self, 
                                   elements_data: pd.DataFrame,
                                   parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze thermal performance of building elements.
        
        Args:
            elements_data: DataFrame containing element data
            parameters: Analysis parameters
            
        Returns:
            Thermal analysis results
        """
        try:
            start_time = time.time()
            
            # Extract analysis parameters
            include_thermal_bridging = parameters.get('include_thermal_bridging', True)
            condensation_analysis = parameters.get('condensation_analysis', True)
            precision = parameters.get('precision', 'standard')
            
            thermal_results = []
            recommendations = []
            
            for _, element in elements_data.iterrows():
                element_result = self._analyze_element_thermal(element, parameters)
                thermal_results.append(element_result)
                
                # Generate recommendations based on performance
                element_recommendations = self._generate_thermal_recommendations(
                    element, element_result
                )
                recommendations.extend(element_recommendations)
            
            # Calculate overall thermal performance
            overall_metrics = self._calculate_overall_thermal_metrics(thermal_results)
            
            # Thermal bridging analysis
            thermal_bridging = {}
            if include_thermal_bridging:
                thermal_bridging = self._analyze_thermal_bridging(elements_data)
            
            # Condensation risk analysis
            condensation_risk = {}
            if condensation_analysis:
                condensation_risk = self._analyze_condensation_risk(elements_data, parameters)
            
            analysis_time = time.time() - start_time
            
            return {
                'element_results': thermal_results,
                'overall_metrics': overall_metrics,
                'thermal_bridging': thermal_bridging,
                'condensation_risk': condensation_risk,
                'recommendations': recommendations,
                'analysis_metadata': {
                    'analysis_time': analysis_time,
                    'element_count': len(elements_data),
                    'precision': precision,
                    'parameters_used': parameters
                }
            }
            
        except Exception as e:
            raise BridgeAnalysisError("thermal_analysis", f"Thermal analysis failed: {e}")
    
    def _analyze_element_thermal(self, element: pd.Series, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze thermal performance of a single element."""
        element_id = element.get('id', 'unknown')
        category = element.get('category', 'Unknown')
        
        # Extract geometric properties
        area = self._extract_area(element)
        thickness = self._extract_thickness(element)
        
        # Calculate thermal properties
        u_value = self._calculate_u_value(element)
        thermal_mass = self._calculate_thermal_mass(element)
        thermal_resistance = 1.0 / max(u_value, 0.001)  # R-value
        
        # Calculate heat transfer
        heat_transfer_rate = self._calculate_heat_transfer(area, u_value)
        
        # Performance rating
        rating = self._rate_thermal_performance(category, u_value)
        
        return {
            'element_id': element_id,
            'category': category,
            'area': area,
            'thickness': thickness,
            'u_value': u_value,
            'r_value': thermal_resistance,
            'thermal_mass': thermal_mass,
            'heat_transfer_rate': heat_transfer_rate,
            'performance_rating': rating,
            'metrics': {
                'thermal_transmittance': u_value,
                'thermal_resistance': thermal_resistance,
                'thermal_mass_per_area': thermal_mass / max(area, 0.001)
            }
        }
    
    def _extract_area(self, element: pd.Series) -> float:
        """Extract element area."""
        try:
            parameters = element.get('parameters', {})
            if 'Area' in parameters:
                area_param = parameters['Area']
                return float(area_param.get('value', 1.0))
            
            # Calculate from geometry if available
            geometry = element.get('geometry', {})
            if geometry and 'data' in geometry:
                return self._estimate_area_from_geometry(geometry['data'])
            
            return 1.0  # Default
        except:
            return 1.0
    
    def _extract_thickness(self, element: pd.Series) -> float:
        """Extract element thickness."""
        try:
            parameters = element.get('parameters', {})
            
            # Check various thickness parameter names
            thickness_params = ['Width', 'Thickness', 'Depth']
            for param_name in thickness_params:
                if param_name in parameters:
                    thickness_param = parameters[param_name]
                    return float(thickness_param.get('value', 0.1))
            
            # Default thickness based on category
            category = element.get('category', '').lower()
            if 'wall' in category:
                return 0.2  # 200mm default wall
            elif 'floor' in category or 'roof' in category:
                return 0.25  # 250mm default slab
            elif 'window' in category or 'door' in category:
                return 0.05  # 50mm default opening
            
            return 0.1  # Default thickness
        except:
            return 0.1
    
    def _calculate_u_value(self, element: pd.Series) -> float:
        """Calculate thermal transmittance (U-value)."""
        try:
            parameters = element.get('parameters', {})
            
            # Check if U-value is already specified
            u_value_params = ['U Value', 'Thermal Transmittance', 'U-Factor']
            for param_name in u_value_params:
                if param_name in parameters:
                    u_param = parameters[param_name]
                    return float(u_param.get('value', 2.0))
            
            # Calculate U-value from material properties
            category = element.get('category', '').lower()
            element_type = element.get('type', '').lower()
            thickness = self._extract_thickness(element)
            
            # Determine material and calculate thermal resistance
            thermal_resistance = self._calculate_material_resistance(category, element_type, thickness)
            
            # Add surface resistances (internal and external)
            surface_resistance = 0.17  # Combined internal and external surface resistance
            total_resistance = thermal_resistance + surface_resistance
            
            return 1.0 / max(total_resistance, 0.001)
            
        except:
            # Default values based on category
            category = element.get('category', '').lower()
            if 'wall' in category:
                return 0.5  # Good insulated wall
            elif 'window' in category:
                return 2.5  # Double glazed window
            elif 'door' in category:
                return 3.0  # Insulated door
            elif 'roof' in category:
                return 0.3  # Insulated roof
            elif 'floor' in category:
                return 0.4  # Insulated floor
            else:
                return 1.0  # Default
    
    def _calculate_material_resistance(self, category: str, element_type: str, thickness: float) -> float:
        """Calculate thermal resistance of material layer."""
        # Determine primary material
        if 'concrete' in element_type or 'masonry' in category.lower():
            conductivity = self.material_properties['concrete']['conductivity']
        elif 'steel' in element_type or 'metal' in element_type:
            conductivity = self.material_properties['steel']['conductivity']
        elif 'wood' in element_type or 'timber' in element_type:
            conductivity = self.material_properties['wood']['conductivity']
        elif 'glass' in element_type or 'glazing' in element_type:
            conductivity = self.material_properties['glass']['conductivity']
        elif 'insulation' in element_type:
            conductivity = self.material_properties['insulation']['conductivity']
        else:
            # Default to concrete for unknown materials
            conductivity = self.material_properties['concrete']['conductivity']
        
        # R = thickness / conductivity
        return thickness / conductivity
    
    def _calculate_thermal_mass(self, element: pd.Series) -> float:
        """Calculate thermal mass of element."""
        try:
            area = self._extract_area(element)
            thickness = self._extract_thickness(element)
            volume = area * thickness
            
            # Determine material density and specific heat
            element_type = element.get('type', '').lower()
            
            if 'concrete' in element_type:
                density = self.material_properties['concrete']['density']
                specific_heat = self.material_properties['concrete']['specific_heat']
            elif 'steel' in element_type:
                density = self.material_properties['steel']['density']
                specific_heat = self.material_properties['steel']['specific_heat']
            elif 'wood' in element_type:
                density = self.material_properties['wood']['density']
                specific_heat = self.material_properties['wood']['specific_heat']
            else:
                # Default to concrete
                density = self.material_properties['concrete']['density']
                specific_heat = self.material_properties['concrete']['specific_heat']
            
            # Thermal mass = volume × density × specific heat
            thermal_mass = volume * density * specific_heat
            
            return thermal_mass
            
        except:
            return 1000000.0  # Default thermal mass in J/K
    
    def _calculate_heat_transfer(self, area: float, u_value: float) -> float:
        """Calculate heat transfer rate."""
        # Assume 20°C temperature difference
        temperature_difference = 20.0  # K
        
        # Q = U × A × ΔT (W)
        heat_transfer_rate = u_value * area * temperature_difference
        
        return heat_transfer_rate
    
    def _rate_thermal_performance(self, category: str, u_value: float) -> str:
        """Rate thermal performance based on U-value and category."""
        # Performance benchmarks by category
        benchmarks = {
            'walls': {'excellent': 0.2, 'good': 0.3, 'fair': 0.5, 'poor': 1.0},
            'windows': {'excellent': 1.0, 'good': 1.5, 'fair': 2.5, 'poor': 4.0},
            'doors': {'excellent': 1.5, 'good': 2.0, 'fair': 3.0, 'poor': 5.0},
            'roofs': {'excellent': 0.15, 'good': 0.25, 'fair': 0.4, 'poor': 0.8},
            'floors': {'excellent': 0.2, 'good': 0.3, 'fair': 0.5, 'poor': 1.0}
        }
        
        # Find appropriate benchmark
        category_lower = category.lower()
        benchmark = None
        
        for cat_name, cat_benchmark in benchmarks.items():
            if cat_name in category_lower:
                benchmark = cat_benchmark
                break
        
        if not benchmark:
            benchmark = benchmarks['walls']  # Default to wall benchmarks
        
        # Rate performance
        if u_value <= benchmark['excellent']:
            return 'excellent'
        elif u_value <= benchmark['good']:
            return 'good'
        elif u_value <= benchmark['fair']:
            return 'fair'
        else:
            return 'poor'
    
    def _calculate_overall_thermal_metrics(self, element_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall thermal performance metrics."""
        if not element_results:
            return {}
        
        # Aggregate metrics
        total_area = sum(result['area'] for result in element_results)
        total_heat_transfer = sum(result['heat_transfer_rate'] for result in element_results)
        
        # Area-weighted average U-value
        weighted_u_value = 0.0
        for result in element_results:
            weight = result['area'] / max(total_area, 0.001)
            weighted_u_value += result['u_value'] * weight
        
        # Performance distribution
        ratings = [result['performance_rating'] for result in element_results]
        rating_counts = {rating: ratings.count(rating) for rating in set(ratings)}
        
        return {
            'total_building_area': total_area,
            'total_heat_loss_rate': total_heat_transfer,
            'average_u_value': weighted_u_value,
            'heat_loss_per_area': total_heat_transfer / max(total_area, 0.001),
            'performance_distribution': rating_counts,
            'overall_rating': self._determine_overall_rating(rating_counts)
        }
    
    def _determine_overall_rating(self, rating_counts: Dict[str, int]) -> str:
        """Determine overall building thermal rating."""
        total_elements = sum(rating_counts.values())
        
        if total_elements == 0:
            return 'unknown'
        
        # Calculate weighted score
        weights = {'excellent': 4, 'good': 3, 'fair': 2, 'poor': 1}
        total_score = sum(rating_counts.get(rating, 0) * weight 
                         for rating, weight in weights.items())
        average_score = total_score / total_elements
        
        if average_score >= 3.5:
            return 'excellent'
        elif average_score >= 2.5:
            return 'good'
        elif average_score >= 1.5:
            return 'fair'
        else:
            return 'poor'
    
    def _analyze_thermal_bridging(self, elements_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze thermal bridging effects."""
        # Simplified thermal bridging analysis
        thermal_bridges = []
        
        # Look for potential thermal bridges at junctions
        wall_elements = elements_data[elements_data['category'].str.contains('Wall', na=False)]
        
        for _, wall in wall_elements.iterrows():
            # Check for steel/concrete elements that could cause thermal bridging
            element_type = wall.get('type', '').lower()
            
            if 'steel' in element_type or 'concrete' in element_type:
                thermal_bridges.append({
                    'element_id': wall.get('id'),
                    'type': 'material_bridge',
                    'severity': 'moderate',
                    'description': f'Potential thermal bridge in {element_type} element',
                    'estimated_heat_loss_increase': 15  # % increase
                })
        
        return {
            'bridges_found': len(thermal_bridges),
            'bridge_details': thermal_bridges,
            'total_estimated_impact': sum(bridge['estimated_heat_loss_increase'] 
                                        for bridge in thermal_bridges) / max(len(thermal_bridges), 1)
        }
    
    def _analyze_condensation_risk(self, elements_data: pd.DataFrame, 
                                 parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze condensation risk."""
        # Simplified condensation analysis
        indoor_temp = parameters.get('indoor_temperature', 20.0)  # °C
        indoor_humidity = parameters.get('indoor_humidity', 60.0)  # %
        outdoor_temp = parameters.get('outdoor_temperature', 0.0)  # °C
        
        # Calculate dew point
        dew_point = self._calculate_dew_point(indoor_temp, indoor_humidity)
        
        condensation_risks = []
        
        for _, element in elements_data.iterrows():
            # Check elements that might be at risk
            category = element.get('category', '').lower()
            
            if any(cat in category for cat in ['window', 'door', 'wall']):
                # Estimate surface temperature
                u_value = self._calculate_u_value(element)
                surface_temp = self._estimate_surface_temperature(
                    indoor_temp, outdoor_temp, u_value
                )
                
                # Check condensation risk
                if surface_temp < dew_point:
                    risk_level = 'high' if surface_temp < dew_point - 2 else 'moderate'
                    
                    condensation_risks.append({
                        'element_id': element.get('id'),
                        'category': category,
                        'surface_temperature': surface_temp,
                        'dew_point': dew_point,
                        'risk_level': risk_level,
                        'temperature_margin': surface_temp - dew_point
                    })
        
        return {
            'analysis_conditions': {
                'indoor_temperature': indoor_temp,
                'indoor_humidity': indoor_humidity,
                'outdoor_temperature': outdoor_temp,
                'dew_point': dew_point
            },
            'elements_at_risk': len(condensation_risks),
            'risk_details': condensation_risks
        }
    
    def _calculate_dew_point(self, temperature: float, humidity: float) -> float:
        """Calculate dew point temperature."""
        # Simplified Magnus formula
        a = 17.27
        b = 237.7
        
        alpha = ((a * temperature) / (b + temperature)) + np.log(humidity / 100.0)
        dew_point = (b * alpha) / (a - alpha)
        
        return dew_point
    
    def _estimate_surface_temperature(self, indoor_temp: float, outdoor_temp: float, u_value: float) -> float:
        """Estimate interior surface temperature."""
        # Simplified calculation using thermal resistance
        total_resistance = 1.0 / u_value
        interior_surface_resistance = 0.13  # m²K/W
        
        # Temperature drop across interior surface
        temp_drop = (indoor_temp - outdoor_temp) * (interior_surface_resistance / total_resistance)
        
        return indoor_temp - temp_drop
    
    def _generate_thermal_recommendations(self, element: pd.Series, 
                                        thermal_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate thermal improvement recommendations."""
        recommendations = []
        
        rating = thermal_result['performance_rating']
        u_value = thermal_result['u_value']
        category = thermal_result['category']
        
        if rating in ['poor', 'fair']:
            if 'wall' in category.lower():
                if u_value > 0.5:
                    recommendations.append({
                        'element_id': thermal_result['element_id'],
                        'type': 'insulation_improvement',
                        'priority': 'high' if rating == 'poor' else 'medium',
                        'description': 'Add external or cavity wall insulation',
                        'estimated_improvement': f'Reduce U-value to 0.3 W/m²K',
                        'estimated_cost': 50 * thermal_result['area'],  # €50/m²
                        'energy_savings': 0.3 * thermal_result['heat_transfer_rate']  # 30% reduction
                    })
            
            elif 'window' in category.lower():
                if u_value > 2.0:
                    recommendations.append({
                        'element_id': thermal_result['element_id'],
                        'type': 'glazing_upgrade',
                        'priority': 'medium',
                        'description': 'Upgrade to triple glazed windows',
                        'estimated_improvement': 'Reduce U-value to 1.0 W/m²K',
                        'estimated_cost': 300 * thermal_result['area'],  # €300/m²
                        'energy_savings': 0.4 * thermal_result['heat_transfer_rate']
                    })
            
            elif 'door' in category.lower():
                if u_value > 2.5:
                    recommendations.append({
                        'element_id': thermal_result['element_id'],
                        'type': 'door_upgrade',
                        'priority': 'low',
                        'description': 'Install insulated door',
                        'estimated_improvement': 'Reduce U-value to 1.5 W/m²K',
                        'estimated_cost': 800,  # €800 per door
                        'energy_savings': 0.35 * thermal_result['heat_transfer_rate']
                    })
        
        return recommendations
    
    def _estimate_area_from_geometry(self, geometry_data: Dict[str, Any]) -> float:
        """Estimate area from geometry data."""
        # Simplified area estimation
        return 10.0  # Default area


class PerformanceAnalysisEngine:
    """Main performance analysis engine combining multiple analysis types."""
    
    def __init__(self):
        """Initialize performance analysis engine."""
        self.logger = logging.getLogger('revitpy_bridge.performance_analysis')
        
        # Initialize analysis engines
        self.thermal_engine = ThermalAnalysisEngine()
        
        # Performance benchmarks
        self.benchmarks = {
            'energy_efficiency': {'excellent': 0.9, 'good': 0.7, 'fair': 0.5, 'poor': 0.3},
            'thermal_performance': {'excellent': 0.3, 'good': 0.5, 'fair': 0.8, 'poor': 1.5},
            'acoustic_performance': {'excellent': 60, 'good': 50, 'fair': 40, 'poor': 30}
        }
    
    async def analyze_performance(self, 
                                elements_data: pd.DataFrame,
                                analysis_types: List[str],
                                parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive performance analysis.
        
        Args:
            elements_data: Element data to analyze
            analysis_types: Types of analysis to perform
            parameters: Analysis parameters
            
        Returns:
            Combined performance analysis results
        """
        try:
            start_time = time.time()
            results = {}
            
            # Thermal analysis
            if 'thermal' in analysis_types:
                self.logger.info("Performing thermal analysis...")
                thermal_results = self.thermal_engine.analyze_thermal_performance(
                    elements_data, parameters
                )
                results['thermal'] = thermal_results
            
            # Energy analysis
            if 'energy' in analysis_types:
                self.logger.info("Performing energy analysis...")
                energy_results = await self._analyze_energy_performance(
                    elements_data, parameters
                )
                results['energy'] = energy_results
            
            # Daylight analysis
            if 'daylight' in analysis_types:
                self.logger.info("Performing daylight analysis...")
                daylight_results = await self._analyze_daylight_performance(
                    elements_data, parameters
                )
                results['daylight'] = daylight_results
            
            # Acoustic analysis
            if 'acoustic' in analysis_types:
                self.logger.info("Performing acoustic analysis...")
                acoustic_results = await self._analyze_acoustic_performance(
                    elements_data, parameters
                )
                results['acoustic'] = acoustic_results
            
            # Generate overall assessment
            overall_assessment = self._generate_overall_assessment(results)
            
            total_time = time.time() - start_time
            
            return {
                'analysis_results': results,
                'overall_assessment': overall_assessment,
                'analysis_metadata': {
                    'total_analysis_time': total_time,
                    'element_count': len(elements_data),
                    'analysis_types_performed': analysis_types,
                    'parameters_used': parameters
                }
            }
            
        except Exception as e:
            raise BridgeAnalysisError("performance_analysis", f"Performance analysis failed: {e}")
    
    async def _analyze_energy_performance(self, elements_data: pd.DataFrame, 
                                        parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze energy performance."""
        try:
            # Energy analysis implementation
            energy_results = []
            total_energy_demand = 0.0
            
            for _, element in elements_data.iterrows():
                element_energy = self._calculate_element_energy_demand(element)
                energy_results.append({
                    'element_id': element.get('id'),
                    'category': element.get('category'),
                    'annual_energy_demand': element_energy,
                    'energy_per_area': element_energy / max(self._get_element_area(element), 0.001)
                })
                total_energy_demand += element_energy
            
            # Calculate energy efficiency metrics
            total_area = sum(self._get_element_area(row) for _, row in elements_data.iterrows())
            energy_intensity = total_energy_demand / max(total_area, 0.001)
            
            # Rate energy performance
            efficiency_rating = self._rate_energy_efficiency(energy_intensity)
            
            return {
                'element_results': energy_results,
                'total_energy_demand': total_energy_demand,
                'total_building_area': total_area,
                'energy_intensity': energy_intensity,
                'efficiency_rating': efficiency_rating,
                'benchmarks': {
                    'excellent': 50,  # kWh/m²/year
                    'good': 100,
                    'fair': 150,
                    'poor': 200
                }
            }
            
        except Exception as e:
            raise BridgeAnalysisError("energy_analysis", f"Energy analysis failed: {e}")
    
    async def _analyze_daylight_performance(self, elements_data: pd.DataFrame,
                                          parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze daylight performance."""
        try:
            # Simplified daylight analysis
            daylight_results = []
            
            # Filter for relevant elements
            windows = elements_data[elements_data['category'].str.contains('Window', na=False)]
            spaces = elements_data[elements_data['category'].str.contains('Room|Space', na=False)]
            
            for _, space in spaces.iterrows():
                # Calculate window-to-floor ratio
                space_area = self._get_element_area(space)
                
                # Find associated windows (simplified - in reality would use spatial relationships)
                window_area = sum(self._get_element_area(window) for _, window in windows.iterrows()) / len(spaces)
                
                window_to_floor_ratio = window_area / max(space_area, 0.001)
                
                # Estimate daylight factor
                daylight_factor = min(window_to_floor_ratio * 100, 10.0)  # Simplified calculation
                
                # Rate daylight performance
                daylight_rating = self._rate_daylight_performance(daylight_factor)
                
                daylight_results.append({
                    'space_id': space.get('id'),
                    'space_area': space_area,
                    'window_area': window_area,
                    'window_to_floor_ratio': window_to_floor_ratio,
                    'daylight_factor': daylight_factor,
                    'rating': daylight_rating
                })
            
            # Overall daylight assessment
            average_daylight_factor = np.mean([result['daylight_factor'] for result in daylight_results])
            overall_rating = self._rate_daylight_performance(average_daylight_factor)
            
            return {
                'space_results': daylight_results,
                'average_daylight_factor': average_daylight_factor,
                'overall_rating': overall_rating,
                'recommendations': self._generate_daylight_recommendations(daylight_results)
            }
            
        except Exception as e:
            raise BridgeAnalysisError("daylight_analysis", f"Daylight analysis failed: {e}")
    
    async def _analyze_acoustic_performance(self, elements_data: pd.DataFrame,
                                          parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze acoustic performance."""
        try:
            # Simplified acoustic analysis
            acoustic_results = []
            
            for _, element in elements_data.iterrows():
                category = element.get('category', '').lower()
                
                if any(cat in category for cat in ['wall', 'floor', 'ceiling', 'door']):
                    # Estimate sound reduction index
                    sound_reduction = self._estimate_sound_reduction(element)
                    
                    # Rate acoustic performance
                    acoustic_rating = self._rate_acoustic_performance(sound_reduction)
                    
                    acoustic_results.append({
                        'element_id': element.get('id'),
                        'category': category,
                        'sound_reduction_index': sound_reduction,
                        'rating': acoustic_rating
                    })
            
            # Calculate overall acoustic performance
            if acoustic_results:
                average_sound_reduction = np.mean([result['sound_reduction_index'] 
                                                 for result in acoustic_results])
                overall_rating = self._rate_acoustic_performance(average_sound_reduction)
            else:
                average_sound_reduction = 0
                overall_rating = 'unknown'
            
            return {
                'element_results': acoustic_results,
                'average_sound_reduction': average_sound_reduction,
                'overall_rating': overall_rating,
                'requirements': {
                    'residential': 45,  # dB minimum
                    'office': 40,
                    'educational': 50
                }
            }
            
        except Exception as e:
            raise BridgeAnalysisError("acoustic_analysis", f"Acoustic analysis failed: {e}")
    
    def _calculate_element_energy_demand(self, element: pd.Series) -> float:
        """Calculate energy demand for an element."""
        # Simplified energy calculation based on thermal properties
        area = self._get_element_area(element)
        u_value = self._calculate_u_value_simple(element)
        
        # Annual energy demand (heating)
        degree_days = 2500  # Heating degree days
        energy_demand = area * u_value * degree_days * 24 / 1000  # kWh/year
        
        return energy_demand
    
    def _get_element_area(self, element: pd.Series) -> float:
        """Get element area."""
        try:
            parameters = element.get('parameters', {})
            if 'Area' in parameters:
                return float(parameters['Area'].get('value', 1.0))
            return 1.0
        except:
            return 1.0
    
    def _calculate_u_value_simple(self, element: pd.Series) -> float:
        """Simple U-value calculation."""
        category = element.get('category', '').lower()
        
        # Default U-values by category
        default_u_values = {
            'wall': 0.5,
            'window': 2.5,
            'door': 3.0,
            'roof': 0.3,
            'floor': 0.4
        }
        
        for cat, u_val in default_u_values.items():
            if cat in category:
                return u_val
        
        return 1.0  # Default
    
    def _rate_energy_efficiency(self, energy_intensity: float) -> str:
        """Rate energy efficiency based on intensity."""
        if energy_intensity <= 50:
            return 'excellent'
        elif energy_intensity <= 100:
            return 'good'
        elif energy_intensity <= 150:
            return 'fair'
        else:
            return 'poor'
    
    def _rate_daylight_performance(self, daylight_factor: float) -> str:
        """Rate daylight performance."""
        if daylight_factor >= 5.0:
            return 'excellent'
        elif daylight_factor >= 3.0:
            return 'good'
        elif daylight_factor >= 2.0:
            return 'fair'
        else:
            return 'poor'
    
    def _estimate_sound_reduction(self, element: pd.Series) -> float:
        """Estimate sound reduction index."""
        category = element.get('category', '').lower()
        thickness = self._get_element_thickness(element)
        
        # Simplified sound reduction estimation
        if 'wall' in category:
            # Mass law approximation
            if 'concrete' in element.get('type', '').lower():
                density = 2400  # kg/m³
                mass_per_area = density * thickness
                # Simplified mass law: R = 20*log10(mass) - 48
                sound_reduction = 20 * np.log10(mass_per_area) - 48
            else:
                sound_reduction = 40 + thickness * 50  # Empirical formula
        elif 'door' in category:
            sound_reduction = 25 + thickness * 20
        elif 'window' in category:
            if 'double' in element.get('type', '').lower():
                sound_reduction = 32
            elif 'triple' in element.get('type', '').lower():
                sound_reduction = 38
            else:
                sound_reduction = 25  # Single glazing
        else:
            sound_reduction = 35  # Default
        
        return max(15, min(sound_reduction, 65))  # Clamp to realistic range
    
    def _get_element_thickness(self, element: pd.Series) -> float:
        """Get element thickness."""
        try:
            parameters = element.get('parameters', {})
            thickness_params = ['Width', 'Thickness', 'Depth']
            
            for param_name in thickness_params:
                if param_name in parameters:
                    return float(parameters[param_name].get('value', 0.1))
            
            return 0.1  # Default thickness
        except:
            return 0.1
    
    def _rate_acoustic_performance(self, sound_reduction: float) -> str:
        """Rate acoustic performance."""
        if sound_reduction >= 50:
            return 'excellent'
        elif sound_reduction >= 40:
            return 'good'
        elif sound_reduction >= 30:
            return 'fair'
        else:
            return 'poor'
    
    def _generate_daylight_recommendations(self, daylight_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate daylight improvement recommendations."""
        recommendations = []
        
        for result in daylight_results:
            if result['rating'] in ['poor', 'fair']:
                if result['daylight_factor'] < 2.0:
                    recommendations.append({
                        'space_id': result['space_id'],
                        'type': 'increase_window_area',
                        'priority': 'high' if result['rating'] == 'poor' else 'medium',
                        'description': 'Increase window area to improve natural lighting',
                        'target_window_ratio': 0.2,  # 20% window-to-floor ratio
                        'estimated_improvement': 'Increase daylight factor to 3.0+'
                    })
        
        return recommendations
    
    def _generate_overall_assessment(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall building performance assessment."""
        assessments = {}
        
        # Collect ratings from all analyses
        all_ratings = []
        
        for analysis_type, analysis_results in results.items():
            if 'overall_rating' in analysis_results:
                rating = analysis_results['overall_rating']
                assessments[analysis_type] = rating
                all_ratings.append(rating)
        
        # Calculate overall rating
        if all_ratings:
            rating_scores = {'excellent': 4, 'good': 3, 'fair': 2, 'poor': 1, 'unknown': 0}
            average_score = np.mean([rating_scores.get(rating, 0) for rating in all_ratings])
            
            if average_score >= 3.5:
                overall_rating = 'excellent'
            elif average_score >= 2.5:
                overall_rating = 'good'
            elif average_score >= 1.5:
                overall_rating = 'fair'
            else:
                overall_rating = 'poor'
        else:
            overall_rating = 'unknown'
        
        return {
            'individual_assessments': assessments,
            'overall_building_rating': overall_rating,
            'performance_summary': self._create_performance_summary(results),
            'priority_recommendations': self._extract_priority_recommendations(results)
        }
    
    def _create_performance_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Create performance summary."""
        summary = {}
        
        if 'thermal' in results:
            thermal_data = results['thermal']['overall_metrics']
            summary['thermal'] = {
                'average_u_value': thermal_data.get('average_u_value', 0),
                'total_heat_loss': thermal_data.get('total_heat_loss_rate', 0)
            }
        
        if 'energy' in results:
            energy_data = results['energy']
            summary['energy'] = {
                'energy_intensity': energy_data.get('energy_intensity', 0),
                'total_demand': energy_data.get('total_energy_demand', 0)
            }
        
        if 'daylight' in results:
            daylight_data = results['daylight']
            summary['daylight'] = {
                'average_daylight_factor': daylight_data.get('average_daylight_factor', 0)
            }
        
        if 'acoustic' in results:
            acoustic_data = results['acoustic']
            summary['acoustic'] = {
                'average_sound_reduction': acoustic_data.get('average_sound_reduction', 0)
            }
        
        return summary
    
    def _extract_priority_recommendations(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract high-priority recommendations from all analyses."""
        priority_recommendations = []
        
        for analysis_type, analysis_results in results.items():
            recommendations = analysis_results.get('recommendations', [])
            
            for rec in recommendations:
                if rec.get('priority') == 'high':
                    rec['analysis_source'] = analysis_type
                    priority_recommendations.append(rec)
        
        # Sort by estimated savings/impact
        priority_recommendations.sort(
            key=lambda x: x.get('energy_savings', x.get('estimated_improvement', 0)),
            reverse=True
        )
        
        return priority_recommendations[:10]  # Top 10 recommendations
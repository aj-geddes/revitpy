"""
Real-Time Monitoring Workflow

This workflow demonstrates integration of IoT sensors, weather data,
and building performance monitoring with live updates to the Revit model.
"""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

# PyRevit imports
try:
    from pyrevit import revit, UI, forms
    PYREVIT_AVAILABLE = True
except ImportError:
    PYREVIT_AVAILABLE = False

from ..pyrevit_integration import RevitPyBridge, ElementSelector, BridgeUIHelpers
from ..core.exceptions import BridgeException


@dataclass
class SensorReading:
    """Represents a sensor reading."""
    
    sensor_id: str
    sensor_type: str
    timestamp: datetime
    value: float
    unit: str
    element_id: Optional[str] = None
    location: Optional[Dict[str, float]] = None
    quality: Optional[str] = 'good'


@dataclass
class MonitoringAlert:
    """Represents a monitoring alert."""
    
    alert_id: str
    alert_type: str
    severity: str  # low, medium, high, critical
    element_id: Optional[str]
    description: str
    timestamp: datetime
    current_value: Optional[float]
    threshold_value: Optional[float]
    recommended_action: Optional[str]


class RealTimeMonitoringWorkflow:
    """
    Real-time monitoring workflow that integrates IoT sensors,
    weather data, and building performance analysis.
    
    Features:
    1. Live sensor data integration
    2. Real-time parameter updates in Revit
    3. Automated anomaly detection
    4. Performance trending and analysis
    5. Predictive maintenance alerts
    6. Energy optimization recommendations
    """
    
    def __init__(self):
        """Initialize the real-time monitoring workflow."""
        self.logger = logging.getLogger('real_time_monitoring_workflow')
        self.bridge = RevitPyBridge()
        self.element_selector = ElementSelector()
        
        # Monitoring configuration
        self.monitoring_active = False
        self.update_interval = 30  # seconds
        self.data_retention_days = 30
        
        # Data sources
        self.sensor_types = {
            'temperature': {'unit': '°C', 'typical_range': (18, 26), 'critical_range': (15, 35)},
            'humidity': {'unit': '%', 'typical_range': (40, 60), 'critical_range': (20, 80)},
            'co2': {'unit': 'ppm', 'typical_range': (400, 800), 'critical_range': (300, 1500)},
            'occupancy': {'unit': 'people', 'typical_range': (0, 50), 'critical_range': (0, 100)},
            'energy_consumption': {'unit': 'kW', 'typical_range': (0, 100), 'critical_range': (0, 200)},
            'light_level': {'unit': 'lux', 'typical_range': (300, 500), 'critical_range': (100, 1000)}
        }
        
        # Monitored elements and sensors
        self.monitored_elements = {}
        self.sensor_data_cache = {}
        self.alerts_active = []
        
        # Performance baselines
        self.performance_baselines = {}
    
    def start_monitoring_workflow(self, interactive: bool = True) -> Dict[str, Any]:
        """
        Start the real-time monitoring workflow.
        
        Args:
            interactive: Whether to show UI dialogs
            
        Returns:
            Monitoring workflow status
        """
        workflow_results = {
            'success': True,
            'monitoring_started': False,
            'elements_monitored': 0,
            'sensors_configured': 0,
            'data_sources_connected': [],
            'monitoring_duration': 0.0
        }
        
        try:
            self.logger.info("Starting real-time monitoring workflow")
            
            # Step 1: Element Selection and Sensor Configuration
            if interactive:
                UI.TaskDialog.Show("Real-Time Monitoring",
                                 "Starting real-time building monitoring workflow.\n\n"
                                 "Step 1: Select elements and configure sensors")
            
            elements, sensor_config = self._step_1_configure_monitoring(interactive)
            workflow_results['elements_monitored'] = len(elements)
            workflow_results['sensors_configured'] = len(sensor_config)
            
            if not elements or not sensor_config:
                raise BridgeException("No elements or sensors configured for monitoring")
            
            # Step 2: Data Source Integration
            if interactive:
                UI.TaskDialog.Show("Real-Time Monitoring",
                                 "Step 2: Connecting to data sources...")
            
            data_sources = self._step_2_connect_data_sources(sensor_config, interactive)
            workflow_results['data_sources_connected'] = data_sources
            
            # Step 3: Baseline Establishment
            if interactive:
                UI.TaskDialog.Show("Real-Time Monitoring",
                                 "Step 3: Establishing performance baselines...")
            
            baselines = self._step_3_establish_baselines(elements, sensor_config, interactive)
            self.performance_baselines = baselines
            
            # Step 4: Start Real-Time Monitoring
            if interactive:
                result = UI.TaskDialog.Show("Real-Time Monitoring",
                                          "Step 4: Start real-time monitoring?\n\n"
                                          "This will begin continuous monitoring and "
                                          "updating of building performance data.",
                                          UI.TaskDialogCommonButtons.Yes | UI.TaskDialogCommonButtons.No)
                
                if result != UI.TaskDialogResult.Yes:
                    workflow_results['monitoring_started'] = False
                    return workflow_results
            
            # Start monitoring loop
            monitoring_start_time = time.time()
            
            if interactive:
                # Run monitoring with UI updates
                asyncio.run(self._run_interactive_monitoring(elements, sensor_config))
            else:
                # Run monitoring without UI (for testing/automation)
                asyncio.run(self._run_background_monitoring(elements, sensor_config, duration=300))  # 5 minutes
            
            workflow_results['monitoring_started'] = True
            workflow_results['monitoring_duration'] = time.time() - monitoring_start_time
            
            self.logger.info(f"Monitoring workflow completed after {workflow_results['monitoring_duration']:.1f}s")
            return workflow_results
            
        except Exception as e:
            workflow_results['success'] = False
            workflow_results['error'] = str(e)
            
            self.logger.error(f"Real-time monitoring workflow failed: {e}")
            
            if interactive:
                UI.TaskDialog.Show("Monitoring Error",
                                 f"Real-time monitoring workflow failed:\n\n{str(e)}")
            
            return workflow_results
    
    def _step_1_configure_monitoring(self, interactive: bool) -> tuple:
        """Step 1: Configure elements and sensors for monitoring."""
        try:
            # Select elements to monitor
            if interactive:
                elements = self.element_selector.select_elements_interactively(
                    message="Select building elements to monitor.\n\n"
                           "Include rooms, HVAC equipment, lighting fixtures, "
                           "and other elements with sensors.",
                    allow_multiple=True
                )
                
                if elements:
                    # Show selection summary
                    summary = self.element_selector.create_element_summary(elements)
                    BridgeUIHelpers.show_element_summary(summary)
            else:
                # Non-interactive: select common monitorable elements
                categories = ['Rooms', 'Mechanical Equipment', 'Electrical Equipment', 'Lighting Fixtures']
                elements = []
                for category in categories:
                    category_elements = self.element_selector.select_elements_by_category([category])
                    elements.extend(category_elements[:5])  # Limit to 5 per category
            
            if not elements:
                return [], {}
            
            # Configure sensors for each element
            sensor_config = self._configure_sensors_for_elements(elements, interactive)
            
            return elements, sensor_config
            
        except Exception as e:
            self.logger.error(f"Monitoring configuration failed: {e}")
            return [], {}
    
    def _step_2_connect_data_sources(self, sensor_config: Dict[str, Any], 
                                   interactive: bool) -> List[str]:
        """Step 2: Connect to external data sources."""
        try:
            data_sources_connected = []
            
            # Connect to RevitPy bridge for advanced analytics
            if not self.bridge.is_connected():
                if self.bridge.connect():
                    data_sources_connected.append('revitpy_bridge')
                    self.logger.info("Connected to RevitPy bridge")
            
            # Simulate connection to IoT platform
            if self._connect_to_iot_platform(sensor_config):
                data_sources_connected.append('iot_sensors')
                self.logger.info("Connected to IoT sensor platform")
            
            # Simulate connection to weather API
            if self._connect_to_weather_api():
                data_sources_connected.append('weather_api')
                self.logger.info("Connected to weather data API")
            
            # Simulate connection to energy grid
            if self._connect_to_energy_grid():
                data_sources_connected.append('energy_grid')
                self.logger.info("Connected to energy grid data")
            
            if interactive:
                sources_summary = f"Connected to {len(data_sources_connected)} data sources:\n\n"
                for source in data_sources_connected:
                    sources_summary += f"• {source.replace('_', ' ').title()}\n"
                
                UI.TaskDialog.Show("Data Sources Connected", sources_summary)
            
            return data_sources_connected
            
        except Exception as e:
            self.logger.error(f"Data source connection failed: {e}")
            return []
    
    def _step_3_establish_baselines(self, elements: List[Any], 
                                  sensor_config: Dict[str, Any],
                                  interactive: bool) -> Dict[str, Any]:
        """Step 3: Establish performance baselines."""
        try:
            baselines = {}
            
            # Collect initial readings from all sensors
            if interactive:
                UI.TaskDialog.Show("Establishing Baselines",
                                 "Collecting initial sensor readings to establish "
                                 "performance baselines...\n\n"
                                 "This may take 1-2 minutes.")
            
            # Simulate baseline data collection
            for element_id, sensors in sensor_config.items():
                element_baselines = {}
                
                for sensor_id, sensor_info in sensors.items():
                    sensor_type = sensor_info['type']
                    
                    # Generate baseline readings (in real implementation, would collect actual data)
                    baseline_readings = self._collect_baseline_readings(sensor_id, sensor_type)
                    
                    element_baselines[sensor_id] = {
                        'sensor_type': sensor_type,
                        'baseline_value': baseline_readings['average'],
                        'typical_range': baseline_readings['range'],
                        'variance': baseline_readings['variance'],
                        'readings_count': baseline_readings['count'],
                        'established_at': datetime.now()
                    }
                
                baselines[element_id] = element_baselines
            
            # Store baselines for anomaly detection
            self.performance_baselines = baselines
            
            if interactive:
                baseline_summary = f"Established baselines for {len(baselines)} elements:\n\n"
                total_sensors = sum(len(sensors) for sensors in baselines.values())
                baseline_summary += f"• Total sensors: {total_sensors}\n"
                baseline_summary += f"• Sensor types: {', '.join(set(s['sensor_type'] for element_sensors in baselines.values() for s in element_sensors.values()))}\n"
                
                UI.TaskDialog.Show("Baselines Established", baseline_summary)
            
            return baselines
            
        except Exception as e:
            self.logger.error(f"Baseline establishment failed: {e}")
            return {}
    
    async def _run_interactive_monitoring(self, elements: List[Any], 
                                        sensor_config: Dict[str, Any]):
        """Run monitoring with interactive UI updates."""
        try:
            self.monitoring_active = True
            monitoring_start = datetime.now()
            
            # Show monitoring dashboard
            if PYREVIT_AVAILABLE:
                UI.TaskDialog.Show("Monitoring Started",
                                 f"Real-time monitoring started at {monitoring_start.strftime('%H:%M:%S')}\n\n"
                                 f"Monitoring {len(elements)} elements with {sum(len(sensors) for sensors in sensor_config.values())} sensors.\n\n"
                                 f"Click OK to start monitoring dashboard.")
            
            # Main monitoring loop
            cycle_count = 0
            while self.monitoring_active and cycle_count < 120:  # Run for 1 hour max (120 cycles * 30s)
                cycle_start = time.time()
                
                # Collect current sensor readings
                current_readings = await self._collect_sensor_readings(sensor_config)
                
                # Update Revit parameters
                updates_applied = await self._update_revit_parameters(elements, current_readings)
                
                # Perform anomaly detection
                alerts = await self._detect_anomalies(current_readings)
                
                # Update performance trends
                trend_analysis = await self._analyze_performance_trends(current_readings)
                
                # Show periodic updates
                if cycle_count % 10 == 0:  # Every 5 minutes
                    await self._show_monitoring_update(
                        cycle_count, current_readings, alerts, trend_analysis
                    )
                
                # Check for critical alerts
                critical_alerts = [alert for alert in alerts if alert.severity == 'critical']
                if critical_alerts:
                    await self._handle_critical_alerts(critical_alerts)
                
                cycle_count += 1
                
                # Wait for next cycle
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, self.update_interval - cycle_duration)
                await asyncio.sleep(sleep_time)
            
            self.monitoring_active = False
            
            # Show monitoring summary
            if PYREVIT_AVAILABLE:
                monitoring_end = datetime.now()
                duration = monitoring_end - monitoring_start
                
                summary = f"Monitoring completed:\n\n"
                summary += f"• Duration: {duration.total_seconds() / 60:.1f} minutes\n"
                summary += f"• Monitoring cycles: {cycle_count}\n"
                summary += f"• Total alerts generated: {len(self.alerts_active)}\n"
                
                UI.TaskDialog.Show("Monitoring Complete", summary)
            
        except Exception as e:
            self.logger.error(f"Interactive monitoring failed: {e}")
            self.monitoring_active = False
    
    async def _run_background_monitoring(self, elements: List[Any], 
                                       sensor_config: Dict[str, Any],
                                       duration: int = 300):
        """Run monitoring in background for specified duration."""
        try:
            self.monitoring_active = True
            start_time = time.time()
            
            while self.monitoring_active and (time.time() - start_time) < duration:
                # Collect sensor readings
                current_readings = await self._collect_sensor_readings(sensor_config)
                
                # Update parameters
                await self._update_revit_parameters(elements, current_readings)
                
                # Check for anomalies
                alerts = await self._detect_anomalies(current_readings)
                
                # Log any alerts
                for alert in alerts:
                    if alert.severity in ['high', 'critical']:
                        self.logger.warning(f"Alert: {alert.description}")
                
                # Wait for next cycle
                await asyncio.sleep(self.update_interval)
            
            self.monitoring_active = False
            
        except Exception as e:
            self.logger.error(f"Background monitoring failed: {e}")
            self.monitoring_active = False
    
    def _configure_sensors_for_elements(self, elements: List[Any], 
                                      interactive: bool) -> Dict[str, Dict[str, Any]]:
        """Configure sensors for selected elements."""
        sensor_config = {}
        
        for element in elements:
            element_id = self._get_element_id(element)
            element_category = self._get_element_category(element).lower()
            
            # Determine appropriate sensors based on element category
            element_sensors = {}
            
            if 'room' in element_category or 'space' in element_category:
                # Room sensors
                element_sensors.update({
                    f"{element_id}_temp": {'type': 'temperature', 'location': 'center'},
                    f"{element_id}_humidity": {'type': 'humidity', 'location': 'center'},
                    f"{element_id}_co2": {'type': 'co2', 'location': 'center'},
                    f"{element_id}_occupancy": {'type': 'occupancy', 'location': 'entrance'},
                    f"{element_id}_light": {'type': 'light_level', 'location': 'desk_level'}
                })
            
            elif 'mechanical' in element_category:
                # HVAC equipment sensors
                element_sensors.update({
                    f"{element_id}_temp": {'type': 'temperature', 'location': 'supply'},
                    f"{element_id}_energy": {'type': 'energy_consumption', 'location': 'unit'}
                })
            
            elif 'electrical' in element_category:
                # Electrical equipment sensors
                element_sensors.update({
                    f"{element_id}_energy": {'type': 'energy_consumption', 'location': 'panel'}
                })
            
            elif 'lighting' in element_category:
                # Lighting sensors
                element_sensors.update({
                    f"{element_id}_energy": {'type': 'energy_consumption', 'location': 'fixture'},
                    f"{element_id}_light": {'type': 'light_level', 'location': 'fixture'}
                })
            
            if element_sensors:
                sensor_config[element_id] = element_sensors
        
        return sensor_config
    
    def _connect_to_iot_platform(self, sensor_config: Dict[str, Any]) -> bool:
        """Simulate connection to IoT sensor platform."""
        try:
            # In real implementation, would connect to actual IoT platform
            self.logger.info(f"Connecting to IoT platform for {len(sensor_config)} elements")
            time.sleep(0.5)  # Simulate connection delay
            return True
        except Exception as e:
            self.logger.error(f"IoT platform connection failed: {e}")
            return False
    
    def _connect_to_weather_api(self) -> bool:
        """Simulate connection to weather data API."""
        try:
            # In real implementation, would connect to weather service
            self.logger.info("Connecting to weather data API")
            time.sleep(0.3)  # Simulate connection delay
            return True
        except Exception as e:
            self.logger.error(f"Weather API connection failed: {e}")
            return False
    
    def _connect_to_energy_grid(self) -> bool:
        """Simulate connection to energy grid data."""
        try:
            # In real implementation, would connect to energy provider API
            self.logger.info("Connecting to energy grid data")
            time.sleep(0.3)  # Simulate connection delay
            return True
        except Exception as e:
            self.logger.error(f"Energy grid connection failed: {e}")
            return False
    
    def _collect_baseline_readings(self, sensor_id: str, sensor_type: str) -> Dict[str, Any]:
        """Collect baseline readings for a sensor."""
        # Simulate baseline data collection
        import random
        
        sensor_info = self.sensor_types.get(sensor_type, {})
        typical_range = sensor_info.get('typical_range', (0, 100))
        
        # Generate realistic baseline readings
        readings = []
        base_value = (typical_range[0] + typical_range[1]) / 2
        
        for _ in range(20):  # 20 baseline readings
            variation = random.uniform(-0.1, 0.1) * (typical_range[1] - typical_range[0])
            reading = base_value + variation
            readings.append(reading)
        
        average = sum(readings) / len(readings)
        variance = sum((r - average) ** 2 for r in readings) / len(readings)
        
        return {
            'average': average,
            'range': (min(readings), max(readings)),
            'variance': variance,
            'count': len(readings),
            'readings': readings
        }
    
    async def _collect_sensor_readings(self, sensor_config: Dict[str, Any]) -> List[SensorReading]:
        """Collect current readings from all sensors."""
        readings = []
        current_time = datetime.now()
        
        for element_id, sensors in sensor_config.items():
            for sensor_id, sensor_info in sensors.items():
                sensor_type = sensor_info['type']
                
                # Generate realistic sensor reading
                reading_value = self._generate_realistic_reading(sensor_id, sensor_type)
                
                reading = SensorReading(
                    sensor_id=sensor_id,
                    sensor_type=sensor_type,
                    timestamp=current_time,
                    value=reading_value,
                    unit=self.sensor_types[sensor_type]['unit'],
                    element_id=element_id,
                    location=sensor_info.get('location'),
                    quality='good'
                )
                
                readings.append(reading)
        
        return readings
    
    def _generate_realistic_reading(self, sensor_id: str, sensor_type: str) -> float:
        """Generate realistic sensor reading with trends and noise."""
        import random
        import math
        
        # Get sensor type info
        sensor_info = self.sensor_types.get(sensor_type, {})
        typical_range = sensor_info.get('typical_range', (0, 100))
        
        # Get baseline if available
        baseline_value = None
        for element_baselines in self.performance_baselines.values():
            if sensor_id in element_baselines:
                baseline_value = element_baselines[sensor_id]['baseline_value']
                break
        
        if baseline_value is None:
            baseline_value = (typical_range[0] + typical_range[1]) / 2
        
        # Add time-based trends (simulate daily cycles)
        current_hour = datetime.now().hour
        
        # Daily cycle adjustment
        if sensor_type == 'temperature':
            # Temperature varies throughout day
            daily_variation = 3 * math.sin((current_hour - 6) * math.pi / 12)
            baseline_value += daily_variation
        elif sensor_type == 'occupancy':
            # Higher occupancy during work hours
            if 8 <= current_hour <= 18:
                baseline_value *= 1.5
            else:
                baseline_value *= 0.3
        elif sensor_type == 'energy_consumption':
            # Higher energy use during work hours
            if 8 <= current_hour <= 18:
                baseline_value *= 1.2
            else:
                baseline_value *= 0.8
        
        # Add random noise
        noise = random.uniform(-0.05, 0.05) * (typical_range[1] - typical_range[0])
        reading_value = baseline_value + noise
        
        # Clamp to reasonable bounds
        reading_value = max(typical_range[0] * 0.8, 
                          min(typical_range[1] * 1.2, reading_value))
        
        return round(reading_value, 2)
    
    async def _update_revit_parameters(self, elements: List[Any], 
                                     readings: List[SensorReading]) -> int:
        """Update Revit element parameters with sensor readings."""
        updates_applied = 0
        
        try:
            # Group readings by element
            readings_by_element = {}
            for reading in readings:
                if reading.element_id not in readings_by_element:
                    readings_by_element[reading.element_id] = []
                readings_by_element[reading.element_id].append(reading)
            
            # Update parameters for each element
            for element in elements:
                element_id = self._get_element_id(element)
                
                if element_id in readings_by_element:
                    element_readings = readings_by_element[element_id]
                    
                    for reading in element_readings:
                        # In real implementation, would update actual Revit parameters
                        # For now, just log the update
                        self.logger.debug(f"Updated {element_id} {reading.sensor_type}: {reading.value} {reading.unit}")
                        updates_applied += 1
            
            return updates_applied
            
        except Exception as e:
            self.logger.error(f"Parameter update failed: {e}")
            return 0
    
    async def _detect_anomalies(self, readings: List[SensorReading]) -> List[MonitoringAlert]:
        """Detect anomalies in sensor readings."""
        alerts = []
        
        for reading in readings:
            try:
                # Get sensor type info
                sensor_info = self.sensor_types.get(reading.sensor_type, {})
                typical_range = sensor_info.get('typical_range', (0, 100))
                critical_range = sensor_info.get('critical_range', (0, 200))
                
                # Get baseline for comparison
                baseline_value = None
                baseline_variance = None
                
                for element_baselines in self.performance_baselines.values():
                    if reading.sensor_id in element_baselines:
                        baseline_info = element_baselines[reading.sensor_id]
                        baseline_value = baseline_info['baseline_value']
                        baseline_variance = baseline_info['variance']
                        break
                
                # Anomaly detection
                alert = None
                
                # Critical range check
                if reading.value < critical_range[0] or reading.value > critical_range[1]:
                    alert = MonitoringAlert(
                        alert_id=f"critical_{reading.sensor_id}_{int(time.time())}",
                        alert_type="critical_range_exceeded",
                        severity="critical",
                        element_id=reading.element_id,
                        description=f"{reading.sensor_type.title()} critically out of range: {reading.value} {reading.unit}",
                        timestamp=reading.timestamp,
                        current_value=reading.value,
                        threshold_value=critical_range[1] if reading.value > critical_range[1] else critical_range[0],
                        recommended_action="Immediate attention required"
                    )
                
                # Typical range check
                elif reading.value < typical_range[0] or reading.value > typical_range[1]:
                    alert = MonitoringAlert(
                        alert_id=f"range_{reading.sensor_id}_{int(time.time())}",
                        alert_type="typical_range_exceeded",
                        severity="medium",
                        element_id=reading.element_id,
                        description=f"{reading.sensor_type.title()} outside typical range: {reading.value} {reading.unit}",
                        timestamp=reading.timestamp,
                        current_value=reading.value,
                        threshold_value=typical_range[1] if reading.value > typical_range[1] else typical_range[0],
                        recommended_action="Monitor and investigate if pattern continues"
                    )
                
                # Baseline deviation check
                elif baseline_value is not None and baseline_variance is not None:
                    deviation = abs(reading.value - baseline_value)
                    threshold = 3 * (baseline_variance ** 0.5)  # 3-sigma rule
                    
                    if deviation > threshold:
                        alert = MonitoringAlert(
                            alert_id=f"deviation_{reading.sensor_id}_{int(time.time())}",
                            alert_type="baseline_deviation",
                            severity="low",
                            element_id=reading.element_id,
                            description=f"{reading.sensor_type.title()} deviates from baseline: {reading.value} {reading.unit} (baseline: {baseline_value:.2f})",
                            timestamp=reading.timestamp,
                            current_value=reading.value,
                            threshold_value=baseline_value,
                            recommended_action="Check for environmental changes or equipment issues"
                        )
                
                if alert:
                    alerts.append(alert)
                    self.alerts_active.append(alert)
            
            except Exception as e:
                self.logger.error(f"Anomaly detection failed for {reading.sensor_id}: {e}")
        
        return alerts
    
    async def _analyze_performance_trends(self, readings: List[SensorReading]) -> Dict[str, Any]:
        """Analyze performance trends from readings."""
        try:
            trend_analysis = {
                'energy_trend': 'stable',
                'comfort_trend': 'improving',
                'efficiency_metrics': {},
                'predictions': {}
            }
            
            # Analyze energy consumption trend
            energy_readings = [r for r in readings if r.sensor_type == 'energy_consumption']
            if energy_readings:
                total_energy = sum(r.value for r in energy_readings)
                trend_analysis['efficiency_metrics']['current_energy_usage'] = total_energy
                
                # Simple trend analysis (in real implementation, would use historical data)
                trend_analysis['energy_trend'] = 'stable'
                trend_analysis['predictions']['energy_forecast_1h'] = total_energy * 1.05
            
            # Analyze comfort metrics
            temp_readings = [r for r in readings if r.sensor_type == 'temperature']
            humidity_readings = [r for r in readings if r.sensor_type == 'humidity']
            
            if temp_readings and humidity_readings:
                avg_temp = sum(r.value for r in temp_readings) / len(temp_readings)
                avg_humidity = sum(r.value for r in humidity_readings) / len(humidity_readings)
                
                # Simple comfort index
                temp_comfort = 1.0 - abs(22 - avg_temp) / 10  # Optimal at 22°C
                humidity_comfort = 1.0 - abs(50 - avg_humidity) / 30  # Optimal at 50%
                comfort_index = (temp_comfort + humidity_comfort) / 2
                
                trend_analysis['efficiency_metrics']['comfort_index'] = max(0, min(1, comfort_index))
            
            return trend_analysis
            
        except Exception as e:
            self.logger.error(f"Trend analysis failed: {e}")
            return {}
    
    async def _show_monitoring_update(self, cycle_count: int, 
                                    readings: List[SensorReading],
                                    alerts: List[MonitoringAlert],
                                    trends: Dict[str, Any]):
        """Show periodic monitoring updates."""
        try:
            if not PYREVIT_AVAILABLE:
                return
            
            # Create update summary
            update_time = datetime.now().strftime('%H:%M:%S')
            update_summary = f"Monitoring Update - {update_time}\n\n"
            update_summary += f"Cycle: {cycle_count + 1}\n"
            update_summary += f"Sensors: {len(readings)} readings collected\n"
            update_summary += f"Alerts: {len(alerts)} new alerts\n\n"
            
            # Show key metrics
            if trends.get('efficiency_metrics'):
                metrics = trends['efficiency_metrics']
                update_summary += "Key Metrics:\n"
                
                if 'current_energy_usage' in metrics:
                    update_summary += f"• Energy Usage: {metrics['current_energy_usage']:.1f} kW\n"
                
                if 'comfort_index' in metrics:
                    comfort_pct = metrics['comfort_index'] * 100
                    update_summary += f"• Comfort Index: {comfort_pct:.0f}%\n"
            
            # Show recent alerts
            if alerts:
                update_summary += f"\nRecent Alerts:\n"
                for alert in alerts[:3]:  # Show top 3 alerts
                    update_summary += f"• {alert.severity.upper()}: {alert.description[:50]}...\n"
            
            UI.TaskDialog.Show("Monitoring Update", update_summary)
            
        except Exception as e:
            self.logger.error(f"Monitoring update display failed: {e}")
    
    async def _handle_critical_alerts(self, critical_alerts: List[MonitoringAlert]):
        """Handle critical alerts immediately."""
        try:
            if not PYREVIT_AVAILABLE:
                return
            
            for alert in critical_alerts:
                alert_message = f"CRITICAL ALERT\n\n"
                alert_message += f"Element: {alert.element_id}\n"
                alert_message += f"Issue: {alert.description}\n"
                alert_message += f"Time: {alert.timestamp.strftime('%H:%M:%S')}\n\n"
                alert_message += f"Recommended Action:\n{alert.recommended_action}\n\n"
                alert_message += "Immediate attention required!"
                
                UI.TaskDialog.Show("CRITICAL ALERT", alert_message)
                
                # Log critical alert
                self.logger.error(f"CRITICAL ALERT: {alert.description}")
            
        except Exception as e:
            self.logger.error(f"Critical alert handling failed: {e}")
    
    def stop_monitoring(self):
        """Stop the monitoring workflow."""
        self.monitoring_active = False
        self.logger.info("Monitoring workflow stopped by user")
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get summary of monitoring session."""
        return {
            'monitoring_active': self.monitoring_active,
            'elements_monitored': len(self.monitored_elements),
            'total_alerts': len(self.alerts_active),
            'alert_breakdown': {
                'critical': len([a for a in self.alerts_active if a.severity == 'critical']),
                'high': len([a for a in self.alerts_active if a.severity == 'high']),
                'medium': len([a for a in self.alerts_active if a.severity == 'medium']),
                'low': len([a for a in self.alerts_active if a.severity == 'low'])
            },
            'baselines_established': len(self.performance_baselines),
            'sensor_types_active': list(self.sensor_types.keys())
        }
    
    # Utility methods
    
    def _get_element_id(self, element) -> str:
        """Get element ID."""
        try:
            if hasattr(element, 'Id'):
                if hasattr(element.Id, 'IntegerValue'):
                    return str(element.Id.IntegerValue)
                return str(element.Id)
            return "unknown"
        except:
            return "unknown"
    
    def _get_element_category(self, element) -> str:
        """Get element category."""
        try:
            if hasattr(element, 'Category') and element.Category:
                return element.Category.Name
            return "Unknown"
        except:
            return "Unknown"
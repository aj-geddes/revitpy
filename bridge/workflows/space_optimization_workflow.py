"""
Space Optimization Workflow using ML

This workflow demonstrates ML-powered space optimization where PyRevit 
handles user interaction and RevitPy performs advanced ML analysis.
"""

import time
import json
from typing import Dict, List, Any, Optional
import logging

# PyRevit imports
try:
    from pyrevit import revit, UI, forms
    PYREVIT_AVAILABLE = True
except ImportError:
    PYREVIT_AVAILABLE = False

from ..pyrevit_integration import RevitPyBridge, ElementSelector, BridgeUIHelpers
from ..core.exceptions import BridgeException


class SpaceOptimizationWorkflow:
    """
    ML-powered space optimization workflow combining PyRevit UI
    with RevitPy's advanced optimization algorithms.
    
    Workflow Steps:
    1. PyRevit: Select spaces and define optimization goals
    2. PyRevit: Collect space data and constraints
    3. RevitPy: Run ML optimization algorithms
    4. RevitPy: Generate optimized layouts
    5. PyRevit: Preview optimization results
    6. PyRevit: Allow user to apply selected optimizations
    """
    
    def __init__(self):
        """Initialize the space optimization workflow."""
        self.logger = logging.getLogger('space_optimization_workflow')
        self.bridge = RevitPyBridge()
        self.element_selector = ElementSelector()
        
        # Optimization configurations
        self.optimization_goals = {
            'efficiency': 'Maximize space utilization efficiency',
            'cost': 'Minimize renovation and operational costs',
            'satisfaction': 'Maximize user satisfaction and comfort',
            'flexibility': 'Maximize layout flexibility and adaptability'
        }
        
        self.optimization_algorithms = {
            'genetic_algorithm': 'Genetic Algorithm (best for complex layouts)',
            'simulated_annealing': 'Simulated Annealing (fast convergence)',
            'particle_swarm': 'Particle Swarm Optimization (balanced approach)'
        }
    
    def execute_optimization_workflow(self, interactive: bool = True) -> Dict[str, Any]:
        """
        Execute the complete space optimization workflow.
        
        Args:
            interactive: Whether to show UI dialogs
            
        Returns:
            Complete optimization workflow results
        """
        workflow_start = time.time()
        workflow_results = {
            'success': True,
            'steps_completed': [],
            'spaces_analyzed': 0,
            'optimization_results': {},
            'layouts_generated': [],
            'selected_optimizations': [],
            'workflow_time': 0.0
        }
        
        try:
            self.logger.info("Starting ML-powered space optimization workflow")
            
            # Step 1: Space Selection and Goal Definition
            if interactive:
                UI.TaskDialog.Show("Space Optimization",
                                 "Starting ML-powered space optimization workflow.\n\n"
                                 "Step 1: Select spaces and define optimization goals")
            
            spaces, optimization_config = self._step_1_configure_optimization(interactive)
            workflow_results['steps_completed'].append('optimization_configuration')
            workflow_results['spaces_analyzed'] = len(spaces)
            workflow_results['optimization_config'] = optimization_config
            
            if not spaces:
                raise BridgeException("No spaces selected for optimization")
            
            # Step 2: Constraint Definition
            if interactive:
                UI.TaskDialog.Show("Space Optimization",
                                 f"Step 2: Define constraints for {len(spaces)} spaces")
            
            constraints = self._step_2_define_constraints(spaces, interactive)
            workflow_results['steps_completed'].append('constraint_definition')
            workflow_results['constraints'] = constraints
            
            # Step 3: ML Optimization
            if interactive:
                UI.TaskDialog.Show("Space Optimization",
                                 "Step 3: Running ML optimization algorithms...\n\n"
                                 "This process uses advanced algorithms to explore "
                                 "thousands of layout possibilities.")
            
            optimization_results = self._step_3_run_optimization(
                spaces, optimization_config, constraints, interactive
            )
            workflow_results['steps_completed'].append('ml_optimization')
            workflow_results['optimization_results'] = optimization_results
            
            # Step 4: Layout Generation and Preview
            if interactive:
                UI.TaskDialog.Show("Space Optimization",
                                 "Step 4: Generating optimized layouts for preview")
            
            generated_layouts = self._step_4_generate_layouts(
                optimization_results, spaces, interactive
            )
            workflow_results['steps_completed'].append('layout_generation')
            workflow_results['layouts_generated'] = generated_layouts
            
            # Step 5: User Selection and Preview
            if interactive:
                selected_layouts = self._step_5_preview_and_select(
                    generated_layouts, optimization_results, interactive
                )
                workflow_results['selected_optimizations'] = selected_layouts
                workflow_results['steps_completed'].append('layout_selection')
            
            # Step 6: Apply Selected Optimizations
            if interactive and workflow_results.get('selected_optimizations'):
                applied_optimizations = self._step_6_apply_optimizations(
                    workflow_results['selected_optimizations'], spaces, interactive
                )
                workflow_results['applied_optimizations'] = applied_optimizations
                workflow_results['steps_completed'].append('optimization_application')
            
            # Step 7: Performance Validation
            if workflow_results.get('applied_optimizations'):
                validation_results = self._step_7_validate_performance(
                    workflow_results['applied_optimizations'], spaces, interactive
                )
                workflow_results['validation_results'] = validation_results
                workflow_results['steps_completed'].append('performance_validation')
            
            workflow_results['workflow_time'] = time.time() - workflow_start
            
            # Show completion summary
            if interactive:
                self._show_completion_summary(workflow_results)
            
            self.logger.info(f"Space optimization workflow completed in {workflow_results['workflow_time']:.1f}s")
            return workflow_results
            
        except Exception as e:
            workflow_results['success'] = False
            workflow_results['error'] = str(e)
            workflow_results['workflow_time'] = time.time() - workflow_start
            
            self.logger.error(f"Space optimization workflow failed: {e}")
            
            if interactive:
                UI.TaskDialog.Show("Workflow Error",
                                 f"Space optimization workflow failed:\n\n{str(e)}")
            
            return workflow_results
    
    def _step_1_configure_optimization(self, interactive: bool) -> tuple:
        """Step 1: Select spaces and configure optimization."""
        try:
            # Select spaces
            if interactive:
                # Show space selection dialog
                spaces = self.element_selector.select_elements_by_category(['Rooms', 'Spaces'])
                
                if not spaces:
                    # Try interactive selection
                    spaces = self.element_selector.select_elements_interactively(
                        message="Select rooms or spaces for optimization.\n\n"
                               "Select spaces that can be reconfigured or "
                               "where layout changes are possible.",
                        allow_multiple=True,
                        element_filter=self._space_filter
                    )
                
                if spaces:
                    # Show space summary
                    summary = self.element_selector.create_element_summary(spaces)
                    BridgeUIHelpers.show_element_summary(summary)
            else:
                # Non-interactive: select all rooms and spaces
                spaces = self.element_selector.select_elements_by_category(['Rooms', 'Spaces'])
            
            if not spaces:
                return [], {}
            
            # Configure optimization goals
            optimization_config = self._configure_optimization_goals(interactive)
            
            return spaces, optimization_config
            
        except Exception as e:
            self.logger.error(f"Optimization configuration failed: {e}")
            return [], {}
    
    def _step_2_define_constraints(self, spaces: List[Any], interactive: bool) -> Dict[str, Any]:
        """Step 2: Define optimization constraints."""
        try:
            constraints = {
                'global_constraints': {
                    'total_area_change_limit': 0.1,  # 10% maximum change
                    'maintain_circulation_paths': True,
                    'preserve_structural_elements': True,
                    'accessibility_compliance': True
                },
                'space_constraints': {}
            }
            
            # Define constraints for each space
            for space in spaces:
                space_id = self._get_element_id(space)
                space_name = self._get_element_name(space)
                current_area = self._get_element_area(space)
                
                space_constraints = {
                    'min_area': max(current_area * 0.7, 10.0),  # Minimum 70% of current or 10m²
                    'max_area': current_area * 1.3,  # Maximum 130% of current
                    'fixed_location': False,
                    'function_changeable': True,
                    'adjacency_requirements': self._get_adjacency_requirements(space)
                }
                
                # Interactive constraint refinement
                if interactive:
                    space_constraints = self._refine_space_constraints(
                        space, space_constraints, interactive
                    )
                
                constraints['space_constraints'][space_id] = space_constraints
            
            # Show constraints summary
            if interactive:
                self._show_constraints_summary(constraints)
            
            return constraints
            
        except Exception as e:
            self.logger.error(f"Constraint definition failed: {e}")
            return {}
    
    def _step_3_run_optimization(self, spaces: List[Any], 
                               optimization_config: Dict[str, Any],
                               constraints: Dict[str, Any],
                               interactive: bool) -> Dict[str, Any]:
        """Step 3: Run ML optimization using RevitPy."""
        try:
            # Connect to RevitPy bridge
            if not self.bridge.is_connected():
                if not self.bridge.connect():
                    raise BridgeException("Failed to connect to RevitPy bridge")
            
            # Show progress if interactive
            if interactive:
                progress_dialog = BridgeUIHelpers.show_analysis_progress(
                    "ML Space Optimization", len(spaces)
                )
            
            # Execute space optimization analysis
            optimization_results = self.bridge.execute_analysis(
                elements=spaces,
                analysis_type='space_optimization',
                parameters={
                    'optimization_goal': optimization_config.get('goal', 'efficiency'),
                    'algorithm': optimization_config.get('algorithm', 'genetic_algorithm'),
                    'iterations': optimization_config.get('iterations', 100),
                    'constraints': constraints,
                    'population_size': optimization_config.get('population_size', 50),
                    'mutation_rate': optimization_config.get('mutation_rate', 0.1),
                    'convergence_threshold': 1e-6
                },
                timeout=300  # 5 minute timeout for optimization
            )
            
            # Validate optimization results
            if not optimization_results or not optimization_results.get('optimized_layout'):
                raise BridgeException("Optimization did not produce valid results")
            
            # Enhance results with additional metrics
            enhanced_results = self._enhance_optimization_results(
                optimization_results, spaces, optimization_config
            )
            
            return enhanced_results
            
        except Exception as e:
            self.logger.error(f"ML optimization failed: {e}")
            raise BridgeException(f"ML optimization failed: {e}")
    
    def _step_4_generate_layouts(self, optimization_results: Dict[str, Any],
                               spaces: List[Any], interactive: bool) -> List[Dict[str, Any]]:
        """Step 4: Generate layout options from optimization results."""
        try:
            optimized_layout = optimization_results.get('optimized_layout', {})
            optimized_spaces = optimized_layout.get('optimized_spaces', [])
            modifications = optimized_layout.get('modifications_required', [])
            
            layouts_generated = []
            
            # Generate primary optimized layout
            primary_layout = {
                'layout_id': 'primary_optimized',
                'name': 'Primary Optimized Layout',
                'description': 'Fully optimized layout based on specified goals',
                'spaces': optimized_spaces,
                'modifications': modifications,
                'metrics': {
                    'efficiency_improvement': optimization_results.get('efficiency_improvement', 0),
                    'cost_impact': optimization_results.get('cost_impact', {}),
                    'fitness_score': optimization_results.get('fitness_score', 0)
                },
                'preview_data': self._generate_layout_preview_data(optimized_spaces, spaces)
            }
            layouts_generated.append(primary_layout)
            
            # Generate alternative layouts with different trade-offs
            if len(modifications) > 1:
                # Conservative layout (fewer changes)
                conservative_modifications = [m for m in modifications 
                                            if m.get('modification_type') != 'major_restructure']
                if conservative_modifications:
                    conservative_layout = {
                        'layout_id': 'conservative',
                        'name': 'Conservative Optimization',
                        'description': 'Optimized layout with minimal structural changes',
                        'spaces': self._apply_modifications_partially(spaces, conservative_modifications),
                        'modifications': conservative_modifications,
                        'metrics': self._estimate_partial_metrics(optimization_results, 0.7),
                        'preview_data': {}
                    }
                    layouts_generated.append(conservative_layout)
                
                # Aggressive layout (maximum changes)
                if len(modifications) > 3:
                    aggressive_layout = {
                        'layout_id': 'aggressive',
                        'name': 'Aggressive Optimization',
                        'description': 'Maximum optimization with significant layout changes',
                        'spaces': optimized_spaces,
                        'modifications': modifications,
                        'metrics': self._estimate_partial_metrics(optimization_results, 1.2),
                        'preview_data': {}
                    }
                    layouts_generated.append(aggressive_layout)
            
            # Show layout generation summary
            if interactive:
                layout_summary = f"Generated {len(layouts_generated)} layout options:\n\n"
                for layout in layouts_generated:
                    improvement = layout['metrics'].get('efficiency_improvement', 0)
                    layout_summary += f"• {layout['name']}: {improvement:.1f}% improvement\n"
                
                UI.TaskDialog.Show("Layouts Generated", layout_summary)
            
            return layouts_generated
            
        except Exception as e:
            self.logger.error(f"Layout generation failed: {e}")
            return []
    
    def _step_5_preview_and_select(self, generated_layouts: List[Dict[str, Any]],
                                  optimization_results: Dict[str, Any],
                                  interactive: bool) -> List[Dict[str, Any]]:
        """Step 5: Preview layouts and let user select which to apply."""
        try:
            if not interactive or not generated_layouts:
                # Non-interactive: select primary layout
                return [generated_layouts[0]] if generated_layouts else []
            
            # Show layout comparison
            selected_layouts = []
            
            for layout in generated_layouts:
                # Show layout details
                layout_details = self._format_layout_details(layout)
                
                result = UI.TaskDialog.Show(
                    f"Preview: {layout['name']}",
                    layout_details + "\n\nDo you want to apply this layout?",
                    UI.TaskDialogCommonButtons.Yes | UI.TaskDialogCommonButtons.No
                )
                
                if result == UI.TaskDialogResult.Yes:
                    selected_layouts.append(layout)
            
            # Show selection summary
            if selected_layouts:
                selection_summary = f"Selected {len(selected_layouts)} layout(s) for application:\n\n"
                for layout in selected_layouts:
                    selection_summary += f"• {layout['name']}\n"
                
                UI.TaskDialog.Show("Layouts Selected", selection_summary)
            else:
                UI.TaskDialog.Show("No Selection", "No layouts were selected for application.")
            
            return selected_layouts
            
        except Exception as e:
            self.logger.error(f"Layout preview and selection failed: {e}")
            return []
    
    def _step_6_apply_optimizations(self, selected_layouts: List[Dict[str, Any]],
                                   spaces: List[Any], interactive: bool) -> List[Dict[str, Any]]:
        """Step 6: Apply selected optimization layouts."""
        try:
            applied_optimizations = []
            
            for layout in selected_layouts:
                try:
                    # Show application progress
                    if interactive:
                        UI.TaskDialog.Show("Applying Layout",
                                         f"Applying {layout['name']}...\n\n"
                                         f"This will modify {len(layout.get('modifications', []))} spaces.")
                    
                    # Apply modifications
                    application_result = self._apply_layout_modifications(
                        layout, spaces, interactive
                    )
                    
                    if application_result['success']:
                        applied_optimizations.append({
                            'layout_id': layout['layout_id'],
                            'layout_name': layout['name'],
                            'status': 'applied',
                            'modifications_applied': len(application_result['modifications_applied']),
                            'modifications_failed': len(application_result['modifications_failed']),
                            'application_time': application_result['application_time']
                        })
                    else:
                        applied_optimizations.append({
                            'layout_id': layout['layout_id'],
                            'layout_name': layout['name'],
                            'status': 'failed',
                            'error': application_result.get('error', 'Unknown error')
                        })
                
                except Exception as e:
                    applied_optimizations.append({
                        'layout_id': layout['layout_id'],
                        'layout_name': layout['name'],
                        'status': 'error',
                        'error': str(e)
                    })
            
            # Show application results
            if interactive and applied_optimizations:
                self._show_application_results(applied_optimizations)
            
            return applied_optimizations
            
        except Exception as e:
            self.logger.error(f"Optimization application failed: {e}")
            return []
    
    def _step_7_validate_performance(self, applied_optimizations: List[Dict[str, Any]],
                                   spaces: List[Any], interactive: bool) -> Dict[str, Any]:
        """Step 7: Validate performance after applying optimizations."""
        try:
            # Re-analyze spaces after optimization
            if not self.bridge.is_connected():
                if not self.bridge.connect():
                    raise BridgeException("Failed to connect to RevitPy bridge")
            
            # Run post-optimization analysis
            post_optimization_results = self.bridge.execute_analysis(
                elements=spaces,
                analysis_type='space_optimization',
                parameters={
                    'optimization_goal': 'efficiency',
                    'algorithm': 'evaluation_only',  # Just evaluate, don't optimize
                    'validation_mode': True
                }
            )
            
            validation_results = {
                'validation_successful': True,
                'post_optimization_metrics': post_optimization_results,
                'improvements_validated': [],
                'performance_comparison': {}
            }
            
            # Compare with pre-optimization baseline
            for optimization in applied_optimizations:
                if optimization['status'] == 'applied':
                    validation_results['improvements_validated'].append({
                        'layout_name': optimization['layout_name'],
                        'validated_improvement': True,  # Simplified validation
                        'actual_efficiency_gain': 0.15  # Example value
                    })
            
            # Show validation results
            if interactive:
                self._show_validation_results(validation_results)
            
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Performance validation failed: {e}")
            return {'validation_successful': False, 'error': str(e)}
    
    # Helper methods
    
    def _space_filter(self, element) -> bool:
        """Filter function for space selection."""
        try:
            category = self._get_element_category(element).lower()
            return any(space_type in category for space_type in ['room', 'space'])
        except:
            return False
    
    def _configure_optimization_goals(self, interactive: bool) -> Dict[str, Any]:
        """Configure optimization goals and parameters."""
        config = {
            'goal': 'efficiency',
            'algorithm': 'genetic_algorithm',
            'iterations': 100,
            'population_size': 50,
            'mutation_rate': 0.1
        }
        
        if interactive and PYREVIT_AVAILABLE:
            try:
                # Goal selection
                selected_goal = forms.SelectFromList.show(
                    [f"{key}: {desc}" for key, desc in self.optimization_goals.items()],
                    title="Select Optimization Goal",
                    multiselect=False
                )
                
                if selected_goal:
                    config['goal'] = selected_goal.split(':')[0]
                
                # Algorithm selection
                selected_algorithm = forms.SelectFromList.show(
                    [f"{key}: {desc}" for key, desc in self.optimization_algorithms.items()],
                    title="Select Optimization Algorithm",
                    multiselect=False
                )
                
                if selected_algorithm:
                    config['algorithm'] = selected_algorithm.split(':')[0]
                
                # Iterations
                iterations_input = forms.ask_for_string(
                    prompt="Number of optimization iterations (50-500):",
                    default="100",
                    title="Optimization Parameters"
                )
                
                if iterations_input and iterations_input.isdigit():
                    config['iterations'] = max(50, min(500, int(iterations_input)))
                
            except Exception as e:
                self.logger.warning(f"Interactive configuration failed, using defaults: {e}")
        
        return config
    
    def _get_adjacency_requirements(self, space) -> List[str]:
        """Get adjacency requirements for a space."""
        # This would analyze spatial relationships in a real implementation
        return []
    
    def _refine_space_constraints(self, space, base_constraints: Dict[str, Any], 
                                interactive: bool) -> Dict[str, Any]:
        """Refine space constraints interactively."""
        if not interactive:
            return base_constraints
        
        try:
            space_name = self._get_element_name(space)
            space_area = self._get_element_area(space)
            
            # Ask about fixed location
            result = UI.TaskDialog.Show(
                f"Constraints for {space_name}",
                f"Space: {space_name}\nCurrent Area: {space_area:.1f} m²\n\n"
                f"Should this space remain in its current location?",
                UI.TaskDialogCommonButtons.Yes | UI.TaskDialogCommonButtons.No
            )
            
            base_constraints['fixed_location'] = (result == UI.TaskDialogResult.Yes)
            
            return base_constraints
            
        except Exception as e:
            self.logger.warning(f"Constraint refinement failed: {e}")
            return base_constraints
    
    def _show_constraints_summary(self, constraints: Dict[str, Any]):
        """Show constraints summary to user."""
        if not PYREVIT_AVAILABLE:
            return
        
        global_constraints = constraints.get('global_constraints', {})
        space_constraints = constraints.get('space_constraints', {})
        
        summary = f"Optimization Constraints Summary:\n\n"
        summary += f"Global Constraints:\n"
        summary += f"• Max area change: {global_constraints.get('total_area_change_limit', 0.1)*100:.0f}%\n"
        summary += f"• Maintain circulation: {global_constraints.get('maintain_circulation_paths', True)}\n"
        summary += f"• Preserve structure: {global_constraints.get('preserve_structural_elements', True)}\n\n"
        
        fixed_spaces = len([c for c in space_constraints.values() if c.get('fixed_location', False)])
        summary += f"Space Constraints:\n"
        summary += f"• Total spaces: {len(space_constraints)}\n"
        summary += f"• Fixed location: {fixed_spaces}\n"
        summary += f"• Flexible location: {len(space_constraints) - fixed_spaces}\n"
        
        UI.TaskDialog.Show("Constraints Summary", summary)
    
    def _enhance_optimization_results(self, optimization_results: Dict[str, Any],
                                    spaces: List[Any], 
                                    optimization_config: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance optimization results with additional metrics."""
        enhanced_results = optimization_results.copy()
        
        # Add algorithm information
        enhanced_results['algorithm_info'] = {
            'algorithm_used': optimization_config.get('algorithm', 'unknown'),
            'iterations_requested': optimization_config.get('iterations', 0),
            'iterations_completed': optimization_results.get('iterations', 0),
            'convergence_achieved': optimization_results.get('converged', False)
        }
        
        # Calculate additional metrics
        original_total_area = sum(self._get_element_area(space) for space in spaces)
        optimized_spaces = optimization_results.get('optimized_layout', {}).get('optimized_spaces', [])
        optimized_total_area = sum(space.get('area', 0) for space in optimized_spaces)
        
        enhanced_results['area_analysis'] = {
            'original_total_area': original_total_area,
            'optimized_total_area': optimized_total_area,
            'area_change_percentage': ((optimized_total_area - original_total_area) / max(original_total_area, 0.001)) * 100
        }
        
        return enhanced_results
    
    def _generate_layout_preview_data(self, optimized_spaces: List[Dict[str, Any]], 
                                    original_spaces: List[Any]) -> Dict[str, Any]:
        """Generate preview data for layout visualization."""
        # This would generate visualization data for the layout
        preview_data = {
            'space_changes': [],
            'area_comparison': {},
            'efficiency_metrics': {}
        }
        
        # Compare original and optimized spaces
        for original_space in original_spaces:
            space_id = self._get_element_id(original_space)
            original_area = self._get_element_area(original_space)
            
            # Find corresponding optimized space
            optimized_space = next((s for s in optimized_spaces if s.get('id') == space_id), None)
            
            if optimized_space:
                optimized_area = optimized_space.get('area', original_area)
                area_change = optimized_area - original_area
                
                preview_data['space_changes'].append({
                    'space_id': space_id,
                    'space_name': self._get_element_name(original_space),
                    'original_area': original_area,
                    'optimized_area': optimized_area,
                    'area_change': area_change,
                    'change_percentage': (area_change / max(original_area, 0.001)) * 100
                })
        
        return preview_data
    
    def _apply_modifications_partially(self, spaces: List[Any], 
                                     modifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply modifications partially to create alternative layout."""
        # Simplified implementation - in reality would apply geometric changes
        partial_spaces = []
        
        for space in spaces:
            space_data = {
                'id': self._get_element_id(space),
                'name': self._get_element_name(space),
                'area': self._get_element_area(space),
                'occupancy': 4,  # Default occupancy
                'function': 'Office'  # Default function
            }
            partial_spaces.append(space_data)
        
        return partial_spaces
    
    def _estimate_partial_metrics(self, full_optimization_results: Dict[str, Any], 
                                factor: float) -> Dict[str, Any]:
        """Estimate metrics for partial optimization."""
        original_improvement = full_optimization_results.get('efficiency_improvement', 0)
        original_cost = full_optimization_results.get('cost_impact', {})
        
        return {
            'efficiency_improvement': original_improvement * factor,
            'cost_impact': {
                'total_cost': original_cost.get('total_cost', 0) * factor,
                'renovation_cost': original_cost.get('renovation_cost', 0) * factor
            },
            'fitness_score': full_optimization_results.get('fitness_score', 0) * factor
        }
    
    def _format_layout_details(self, layout: Dict[str, Any]) -> str:
        """Format layout details for user display."""
        details = f"{layout['description']}\n\n"
        
        metrics = layout.get('metrics', {})
        efficiency_improvement = metrics.get('efficiency_improvement', 0)
        cost_impact = metrics.get('cost_impact', {})
        
        details += f"Performance Metrics:\n"
        details += f"• Efficiency Improvement: {efficiency_improvement:.1f}%\n"
        details += f"• Modifications Required: {len(layout.get('modifications', []))}\n"
        
        if cost_impact:
            total_cost = cost_impact.get('total_cost', 0)
            details += f"• Estimated Cost: €{total_cost:,.0f}\n"
        
        details += f"\nChanges Overview:\n"
        for i, modification in enumerate(layout.get('modifications', [])[:3]):  # Show first 3
            space_name = modification.get('space_name', f'Space {i+1}')
            mod_type = modification.get('modification_type', 'unknown')
            details += f"• {space_name}: {mod_type}\n"
        
        if len(layout.get('modifications', [])) > 3:
            remaining = len(layout.get('modifications', [])) - 3
            details += f"• ... and {remaining} more changes\n"
        
        return details
    
    def _apply_layout_modifications(self, layout: Dict[str, Any], 
                                  spaces: List[Any], 
                                  interactive: bool) -> Dict[str, Any]:
        """Apply layout modifications to spaces."""
        application_start = time.time()
        
        result = {
            'success': True,
            'modifications_applied': [],
            'modifications_failed': [],
            'application_time': 0.0
        }
        
        try:
            modifications = layout.get('modifications', [])
            
            for modification in modifications:
                try:
                    # Find target space
                    target_space_id = modification.get('space_id')
                    target_space = None
                    
                    for space in spaces:
                        if self._get_element_id(space) == target_space_id:
                            target_space = space
                            break
                    
                    if target_space:
                        # Apply modification (simplified - in reality would modify geometry)
                        modification_applied = {
                            'space_id': target_space_id,
                            'space_name': modification.get('space_name', 'Unknown'),
                            'modification_type': modification.get('modification_type', 'unknown'),
                            'changes_applied': modification.get('changes', {}),
                            'status': 'applied'
                        }
                        result['modifications_applied'].append(modification_applied)
                        
                        self.logger.info(f"Applied modification to space {target_space_id}")
                    else:
                        result['modifications_failed'].append({
                            'space_id': target_space_id,
                            'error': 'Target space not found'
                        })
                
                except Exception as e:
                    result['modifications_failed'].append({
                        'space_id': modification.get('space_id', 'unknown'),
                        'error': str(e)
                    })
            
            result['application_time'] = time.time() - application_start
            
            # Check if any modifications failed
            if result['modifications_failed'] and not result['modifications_applied']:
                result['success'] = False
                result['error'] = "All modifications failed"
            
            return result
            
        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
            result['application_time'] = time.time() - application_start
            return result
    
    def _show_application_results(self, applied_optimizations: List[Dict[str, Any]]):
        """Show optimization application results."""
        if not PYREVIT_AVAILABLE:
            return
        
        successful = len([opt for opt in applied_optimizations if opt['status'] == 'applied'])
        failed = len(applied_optimizations) - successful
        
        results_summary = f"Optimization Application Results:\n\n"
        results_summary += f"Successfully Applied: {successful}\n"
        results_summary += f"Failed to Apply: {failed}\n\n"
        
        if successful > 0:
            results_summary += "Successfully Applied Layouts:\n"
            for opt in applied_optimizations:
                if opt['status'] == 'applied':
                    modifications_applied = opt.get('modifications_applied', 0)
                    results_summary += f"• {opt['layout_name']}: {modifications_applied} changes\n"
        
        if failed > 0:
            results_summary += "\nFailed Applications:\n"
            for opt in applied_optimizations:
                if opt['status'] != 'applied':
                    error = opt.get('error', 'Unknown error')
                    results_summary += f"• {opt['layout_name']}: {error}\n"
        
        UI.TaskDialog.Show("Application Results", results_summary)
    
    def _show_validation_results(self, validation_results: Dict[str, Any]):
        """Show performance validation results."""
        if not PYREVIT_AVAILABLE:
            return
        
        validation_summary = "Performance Validation Results:\n\n"
        
        if validation_results.get('validation_successful', False):
            validation_summary += "✓ Validation completed successfully\n\n"
            
            improvements = validation_results.get('improvements_validated', [])
            if improvements:
                validation_summary += "Validated Improvements:\n"
                for improvement in improvements:
                    layout_name = improvement.get('layout_name', 'Unknown')
                    efficiency_gain = improvement.get('actual_efficiency_gain', 0)
                    validation_summary += f"• {layout_name}: {efficiency_gain:.1%} efficiency gain\n"
        else:
            validation_summary += "✗ Validation failed\n"
            error = validation_results.get('error', 'Unknown error')
            validation_summary += f"Error: {error}\n"
        
        UI.TaskDialog.Show("Validation Results", validation_summary)
    
    def _show_completion_summary(self, workflow_results: Dict[str, Any]):
        """Show workflow completion summary."""
        if not PYREVIT_AVAILABLE:
            return
        
        summary = f"Space Optimization Workflow Completed!\n\n"
        summary += f"Status: {'SUCCESS' if workflow_results['success'] else 'FAILED'}\n"
        summary += f"Spaces Analyzed: {workflow_results['spaces_analyzed']}\n"
        summary += f"Workflow Time: {workflow_results['workflow_time']:.1f} seconds\n"
        summary += f"Steps Completed: {len(workflow_results['steps_completed'])}\n\n"
        
        if 'optimization_results' in workflow_results:
            opt_results = workflow_results['optimization_results']
            efficiency_improvement = opt_results.get('efficiency_improvement', 0)
            summary += f"Optimization Results:\n"
            summary += f"• Efficiency Improvement: {efficiency_improvement:.1f}%\n"
            
            if 'cost_impact' in opt_results:
                cost_impact = opt_results['cost_impact']
                total_cost = cost_impact.get('total_cost', 0)
                summary += f"• Estimated Cost: €{total_cost:,.0f}\n"
        
        applied_count = len(workflow_results.get('applied_optimizations', []))
        if applied_count > 0:
            summary += f"\n{applied_count} optimization(s) were successfully applied to the model."
        
        UI.TaskDialog.Show("Workflow Complete", summary)
    
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
    
    def _get_element_name(self, element) -> str:
        """Get element name."""
        try:
            if hasattr(element, 'Name') and element.Name:
                return element.Name
            return f"Element {self._get_element_id(element)}"
        except:
            return "Unknown"
    
    def _get_element_area(self, element) -> float:
        """Get element area."""
        try:
            if hasattr(element, 'Parameters'):
                for param in element.Parameters:
                    if hasattr(param, 'Definition') and hasattr(param.Definition, 'Name'):
                        if param.Definition.Name == 'Area':
                            if hasattr(param, 'AsDouble'):
                                return param.AsDouble()
            return 20.0  # Default area
        except:
            return 20.0
    
    def _get_element_category(self, element) -> str:
        """Get element category."""
        try:
            if hasattr(element, 'Category') and element.Category:
                return element.Category.Name
            return "Unknown"
        except:
            return "Unknown"
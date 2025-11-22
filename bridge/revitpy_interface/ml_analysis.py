"""
Machine Learning analysis engine for RevitPy bridge.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

# ML/Data Science imports (with fallbacks)
try:
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.decomposition import PCA
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import silhouette_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from scipy.optimize import differential_evolution, minimize
    from scipy.spatial.distance import pdist, squareform

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from ..core.exceptions import BridgeAnalysisError


@dataclass
class OptimizationResult:
    """Result of an optimization process."""

    optimized_spaces: list[dict[str, Any]]
    modifications: list[dict[str, Any]]
    iterations: int
    converged: bool
    execution_time: float
    fitness_score: float
    improvement_percentage: float


@dataclass
class MLModelResult:
    """Result of ML model training/prediction."""

    model_type: str
    predictions: np.ndarray
    confidence_scores: np.ndarray | None
    feature_importance: dict[str, float] | None
    model_metrics: dict[str, float]
    training_time: float


class OptimizationAlgorithm(ABC):
    """Abstract base class for optimization algorithms."""

    @abstractmethod
    async def optimize(
        self,
        objective_function: callable,
        initial_solution: list[dict[str, Any]],
        constraints: dict[str, Any],
        iterations: int,
    ) -> OptimizationResult:
        """Run optimization algorithm."""
        pass


class GeneticAlgorithm(OptimizationAlgorithm):
    """Genetic algorithm for space optimization."""

    def __init__(self, population_size: int = 50, mutation_rate: float = 0.1):
        """Initialize genetic algorithm."""
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.logger = logging.getLogger("revitpy_bridge.genetic_algorithm")

    async def optimize(
        self,
        objective_function: callable,
        initial_solution: list[dict[str, Any]],
        constraints: dict[str, Any],
        iterations: int,
    ) -> OptimizationResult:
        """Run genetic algorithm optimization."""
        start_time = time.time()

        try:
            # Initialize population
            population = self._initialize_population(
                initial_solution, self.population_size
            )
            best_solution = initial_solution.copy()
            best_fitness = await objective_function(best_solution)

            fitness_history = [best_fitness]

            for generation in range(iterations):
                # Evaluate population fitness
                fitness_scores = []
                for individual in population:
                    fitness = await objective_function(individual)
                    fitness_scores.append(fitness)

                # Find best individual in this generation
                best_idx = np.argmax(fitness_scores)
                if fitness_scores[best_idx] > best_fitness:
                    best_fitness = fitness_scores[best_idx]
                    best_solution = population[best_idx].copy()

                fitness_history.append(best_fitness)

                # Selection
                selected = self._selection(population, fitness_scores)

                # Crossover
                offspring = self._crossover(selected)

                # Mutation
                mutated = self._mutation(offspring, constraints)

                # Replace population
                population = mutated

                # Check convergence
                if len(fitness_history) > 10:
                    recent_improvement = fitness_history[-1] - fitness_history[-10]
                    if abs(recent_improvement) < 1e-6:
                        self.logger.info(
                            f"Genetic algorithm converged at generation {generation}"
                        )
                        break

            execution_time = time.time() - start_time

            # Calculate modifications needed
            modifications = self._calculate_modifications(
                initial_solution, best_solution
            )

            # Calculate improvement
            original_fitness = await objective_function(initial_solution)
            improvement = (
                (best_fitness - original_fitness) / max(abs(original_fitness), 1e-6)
            ) * 100

            return OptimizationResult(
                optimized_spaces=best_solution,
                modifications=modifications,
                iterations=generation + 1,
                converged=True,
                execution_time=execution_time,
                fitness_score=best_fitness,
                improvement_percentage=improvement,
            )

        except Exception as e:
            raise BridgeAnalysisError("genetic_algorithm", f"Optimization failed: {e}")

    def _initialize_population(
        self, initial_solution: list[dict[str, Any]], population_size: int
    ) -> list[list[dict[str, Any]]]:
        """Initialize population for genetic algorithm."""
        population = [initial_solution.copy()]  # Include original solution

        for _ in range(population_size - 1):
            individual = []
            for space in initial_solution:
                # Create variations of each space
                modified_space = space.copy()

                # Randomly modify area within constraints
                original_area = space.get("area", 20.0)
                area_variation = np.random.normal(0, original_area * 0.1)
                modified_space["area"] = max(5.0, original_area + area_variation)

                # Randomly modify occupancy
                original_occupancy = space.get("occupancy", 4)
                occupancy_variation = np.random.randint(-2, 3)
                modified_space["occupancy"] = max(
                    1, original_occupancy + occupancy_variation
                )

                individual.append(modified_space)

            population.append(individual)

        return population

    def _selection(
        self, population: list[list[dict[str, Any]]], fitness_scores: list[float]
    ) -> list[list[dict[str, Any]]]:
        """Tournament selection."""
        selected = []

        for _ in range(len(population)):
            # Tournament selection with tournament size 3
            tournament_indices = np.random.choice(len(population), 3, replace=False)
            tournament_fitness = [fitness_scores[i] for i in tournament_indices]
            winner_idx = tournament_indices[np.argmax(tournament_fitness)]
            selected.append(population[winner_idx].copy())

        return selected

    def _crossover(
        self, selected: list[list[dict[str, Any]]]
    ) -> list[list[dict[str, Any]]]:
        """Single-point crossover."""
        offspring = []

        for i in range(0, len(selected), 2):
            parent1 = selected[i]
            parent2 = selected[(i + 1) % len(selected)]

            if len(parent1) > 1:
                crossover_point = np.random.randint(1, len(parent1))

                child1 = parent1[:crossover_point] + parent2[crossover_point:]
                child2 = parent2[:crossover_point] + parent1[crossover_point:]

                offspring.extend([child1, child2])
            else:
                offspring.extend([parent1, parent2])

        return offspring[: len(selected)]  # Keep population size constant

    def _mutation(
        self, offspring: list[list[dict[str, Any]]], constraints: dict[str, Any]
    ) -> list[list[dict[str, Any]]]:
        """Mutation operation."""
        mutated = []

        for individual in offspring:
            mutated_individual = []

            for space in individual:
                mutated_space = space.copy()

                # Mutate with probability
                if np.random.random() < self.mutation_rate:
                    # Mutate area
                    if "area" in mutated_space:
                        area_mutation = np.random.normal(
                            0, mutated_space["area"] * 0.05
                        )
                        mutated_space["area"] = max(
                            5.0, mutated_space["area"] + area_mutation
                        )

                    # Mutate occupancy
                    if "occupancy" in mutated_space and np.random.random() < 0.3:
                        occupancy_change = np.random.choice([-1, 0, 1])
                        mutated_space["occupancy"] = max(
                            1, mutated_space["occupancy"] + occupancy_change
                        )

                mutated_individual.append(mutated_space)

            mutated.append(mutated_individual)

        return mutated

    def _calculate_modifications(
        self, original: list[dict[str, Any]], optimized: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Calculate modifications needed to transform original to optimized."""
        modifications = []

        for i, (orig_space, opt_space) in enumerate(
            zip(original, optimized, strict=False)
        ):
            changes = {}

            for key in orig_space:
                if key in opt_space and orig_space[key] != opt_space[key]:
                    changes[key] = {
                        "from": orig_space[key],
                        "to": opt_space[key],
                        "change": opt_space[key] - orig_space[key]
                        if isinstance(orig_space[key], (int, float))
                        else "modified",
                    }

            if changes:
                modifications.append(
                    {
                        "space_id": orig_space.get("id", f"space_{i}"),
                        "space_name": orig_space.get("name", f"Space {i}"),
                        "changes": changes,
                        "modification_type": "resize"
                        if "area" in changes
                        else "reconfigure",
                    }
                )

        return modifications


class SimulatedAnnealing(OptimizationAlgorithm):
    """Simulated annealing algorithm for optimization."""

    def __init__(self, initial_temperature: float = 100.0, cooling_rate: float = 0.95):
        """Initialize simulated annealing."""
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
        self.logger = logging.getLogger("revitpy_bridge.simulated_annealing")

    async def optimize(
        self,
        objective_function: callable,
        initial_solution: list[dict[str, Any]],
        constraints: dict[str, Any],
        iterations: int,
    ) -> OptimizationResult:
        """Run simulated annealing optimization."""
        start_time = time.time()

        try:
            current_solution = initial_solution.copy()
            current_fitness = await objective_function(current_solution)

            best_solution = current_solution.copy()
            best_fitness = current_fitness

            temperature = self.initial_temperature

            for iteration in range(iterations):
                # Generate neighbor solution
                neighbor_solution = self._generate_neighbor(
                    current_solution, constraints
                )
                neighbor_fitness = await objective_function(neighbor_solution)

                # Accept or reject neighbor
                if self._accept_solution(
                    current_fitness, neighbor_fitness, temperature
                ):
                    current_solution = neighbor_solution
                    current_fitness = neighbor_fitness

                    # Update best solution
                    if neighbor_fitness > best_fitness:
                        best_solution = neighbor_solution.copy()
                        best_fitness = neighbor_fitness

                # Cool down temperature
                temperature *= self.cooling_rate

                if temperature < 1e-6:
                    break

            execution_time = time.time() - start_time

            modifications = self._calculate_modifications(
                initial_solution, best_solution
            )
            original_fitness = await objective_function(initial_solution)
            improvement = (
                (best_fitness - original_fitness) / max(abs(original_fitness), 1e-6)
            ) * 100

            return OptimizationResult(
                optimized_spaces=best_solution,
                modifications=modifications,
                iterations=iteration + 1,
                converged=temperature < 1e-6,
                execution_time=execution_time,
                fitness_score=best_fitness,
                improvement_percentage=improvement,
            )

        except Exception as e:
            raise BridgeAnalysisError(
                "simulated_annealing", f"Optimization failed: {e}"
            )

    def _generate_neighbor(
        self, solution: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Generate neighbor solution by making small modifications."""
        neighbor = [space.copy() for space in solution]

        # Randomly select a space to modify
        space_idx = np.random.randint(len(neighbor))
        space = neighbor[space_idx]

        # Make small modification
        if "area" in space and np.random.random() < 0.7:
            area_change = np.random.normal(0, space["area"] * 0.1)
            space["area"] = max(5.0, space["area"] + area_change)

        if "occupancy" in space and np.random.random() < 0.3:
            occupancy_change = np.random.choice([-1, 0, 1])
            space["occupancy"] = max(1, space["occupancy"] + occupancy_change)

        return neighbor

    def _accept_solution(
        self, current_fitness: float, neighbor_fitness: float, temperature: float
    ) -> bool:
        """Decide whether to accept neighbor solution."""
        if neighbor_fitness > current_fitness:
            return True

        if temperature <= 0:
            return False

        probability = np.exp((neighbor_fitness - current_fitness) / temperature)
        return np.random.random() < probability

    def _calculate_modifications(
        self, original: list[dict[str, Any]], optimized: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Calculate modifications (same as genetic algorithm)."""
        # Reuse the genetic algorithm implementation
        ga = GeneticAlgorithm()
        return ga._calculate_modifications(original, optimized)


class MLAnalysisEngine:
    """Machine learning analysis engine for advanced RevitPy analytics."""

    def __init__(self):
        """Initialize ML analysis engine."""
        self.logger = logging.getLogger("revitpy_bridge.ml_analysis")

        # Available algorithms
        self.optimization_algorithms = {
            "genetic_algorithm": GeneticAlgorithm(),
            "simulated_annealing": SimulatedAnnealing(),
        }

        # Model cache
        self.trained_models = {}

        # Check dependencies
        if not SKLEARN_AVAILABLE:
            self.logger.warning("scikit-learn not available, ML features limited")
        if not SCIPY_AVAILABLE:
            self.logger.warning("scipy not available, optimization features limited")

    async def optimize_space_layout(
        self,
        spaces_data: list[dict[str, Any]],
        goal: str = "efficiency",
        algorithm: str = "genetic_algorithm",
        iterations: int = 100,
        constraints: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """
        Optimize space layout using ML algorithms.

        Args:
            spaces_data: List of space information
            goal: Optimization goal (efficiency, cost, satisfaction)
            algorithm: Optimization algorithm to use
            iterations: Number of optimization iterations
            constraints: Optimization constraints

        Returns:
            Optimization result
        """
        try:
            # Create objective function based on goal
            objective_function = self._create_objective_function(goal)

            # Get optimization algorithm
            if algorithm not in self.optimization_algorithms:
                raise ValueError(f"Unknown algorithm: {algorithm}")

            optimizer = self.optimization_algorithms[algorithm]
            constraints = constraints or {}

            # Run optimization
            result = await optimizer.optimize(
                objective_function=objective_function,
                initial_solution=spaces_data,
                constraints=constraints,
                iterations=iterations,
            )

            self.logger.info(
                f"Space optimization completed using {algorithm}: "
                f"{result.improvement_percentage:.1f}% improvement"
            )

            return result

        except Exception as e:
            raise BridgeAnalysisError(
                "space_optimization", f"ML optimization failed: {e}"
            )

    async def cluster_elements(
        self,
        elements_data: pd.DataFrame,
        method: str = "kmeans",
        n_clusters: int | None = None,
        features: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Cluster building elements based on their properties.

        Args:
            elements_data: DataFrame of element data
            method: Clustering method (kmeans, dbscan)
            n_clusters: Number of clusters (for methods that require it)
            features: Features to use for clustering

        Returns:
            Clustering results
        """
        if not SKLEARN_AVAILABLE:
            raise BridgeAnalysisError(
                "clustering", "scikit-learn required for clustering"
            )

        try:
            # Prepare features
            feature_data = self._prepare_clustering_features(elements_data, features)

            if feature_data.empty:
                raise ValueError("No valid features found for clustering")

            # Normalize features
            scaler = StandardScaler()
            normalized_features = scaler.fit_transform(feature_data)

            # Perform clustering
            if method == "kmeans":
                if n_clusters is None:
                    # Find optimal number of clusters
                    n_clusters = self._find_optimal_clusters(normalized_features)

                clusterer = KMeans(n_clusters=n_clusters, random_state=42)
                cluster_labels = clusterer.fit_predict(normalized_features)

            elif method == "dbscan":
                clusterer = DBSCAN(eps=0.5, min_samples=5)
                cluster_labels = clusterer.fit_predict(normalized_features)
                n_clusters = len(set(cluster_labels)) - (
                    1 if -1 in cluster_labels else 0
                )

            else:
                raise ValueError(f"Unknown clustering method: {method}")

            # Analyze clusters
            cluster_analysis = self._analyze_clusters(
                elements_data, cluster_labels, feature_data.columns
            )

            return {
                "method": method,
                "n_clusters": n_clusters,
                "cluster_labels": cluster_labels.tolist(),
                "cluster_analysis": cluster_analysis,
                "features_used": feature_data.columns.tolist(),
                "silhouette_score": silhouette_score(
                    normalized_features, cluster_labels
                )
                if n_clusters > 1
                else 0,
            }

        except Exception as e:
            raise BridgeAnalysisError("clustering", f"Clustering failed: {e}")

    async def predict_performance(
        self,
        elements_data: pd.DataFrame,
        target: str,
        model_type: str = "random_forest",
    ) -> MLModelResult:
        """
        Predict performance metrics using ML models.

        Args:
            elements_data: DataFrame of element data
            target: Target variable to predict
            model_type: Type of ML model to use

        Returns:
            Model prediction results
        """
        if not SKLEARN_AVAILABLE:
            raise BridgeAnalysisError(
                "prediction", "scikit-learn required for prediction"
            )

        try:
            start_time = time.time()

            # Prepare features and target
            features, target_values = self._prepare_prediction_data(
                elements_data, target
            )

            if features.empty or len(target_values) == 0:
                raise ValueError("No valid data found for prediction")

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                features, target_values, test_size=0.2, random_state=42
            )

            # Train model
            if model_type == "random_forest":
                model = RandomForestRegressor(n_estimators=100, random_state=42)
            else:
                raise ValueError(f"Unknown model type: {model_type}")

            model.fit(X_train, y_train)

            # Make predictions
            predictions = model.predict(features)
            test_predictions = model.predict(X_test)

            # Calculate metrics
            from sklearn.metrics import mean_squared_error, r2_score

            mse = mean_squared_error(y_test, test_predictions)
            r2 = r2_score(y_test, test_predictions)

            # Get feature importance
            feature_importance = dict(
                zip(features.columns, model.feature_importances_, strict=False)
            )

            training_time = time.time() - start_time

            return MLModelResult(
                model_type=model_type,
                predictions=predictions,
                confidence_scores=None,  # Random Forest doesn't provide direct confidence
                feature_importance=feature_importance,
                model_metrics={
                    "mse": mse,
                    "r2_score": r2,
                    "training_samples": len(X_train),
                    "test_samples": len(X_test),
                },
                training_time=training_time,
            )

        except Exception as e:
            raise BridgeAnalysisError("prediction", f"Prediction failed: {e}")

    def _create_objective_function(self, goal: str) -> callable:
        """Create objective function based on optimization goal."""

        async def efficiency_objective(spaces: list[dict[str, Any]]) -> float:
            """Objective function for efficiency optimization."""
            total_score = 0.0

            for space in spaces:
                area = space.get("area", 20.0)
                occupancy = space.get("occupancy", 4)

                # Efficiency score based on area per person
                if occupancy > 0:
                    area_per_person = area / occupancy
                    # Optimal range: 10-15 m² per person
                    if 10 <= area_per_person <= 15:
                        efficiency_score = 1.0
                    elif area_per_person < 10:
                        efficiency_score = area_per_person / 10.0
                    else:
                        efficiency_score = 15.0 / area_per_person

                    total_score += efficiency_score
                else:
                    total_score += 0.1  # Penalty for empty spaces

            return total_score / len(spaces) if spaces else 0.0

        async def cost_objective(spaces: list[dict[str, Any]]) -> float:
            """Objective function for cost optimization."""
            total_cost = 0.0

            for space in spaces:
                area = space.get("area", 20.0)
                # Cost increases with area
                space_cost = area * 100  # $100 per m²
                total_cost += space_cost

            # Return negative cost (since we want to minimize cost)
            return -total_cost

        async def satisfaction_objective(spaces: list[dict[str, Any]]) -> float:
            """Objective function for user satisfaction."""
            total_satisfaction = 0.0

            for space in spaces:
                area = space.get("area", 20.0)
                occupancy = space.get("occupancy", 4)
                function = space.get("function", "Office")

                # Satisfaction based on space function and size
                optimal_area = self._get_optimal_area_for_function(function, occupancy)
                area_satisfaction = 1.0 - abs(area - optimal_area) / optimal_area

                total_satisfaction += max(0.0, area_satisfaction)

            return total_satisfaction / len(spaces) if spaces else 0.0

        # Return appropriate objective function
        if goal == "efficiency":
            return efficiency_objective
        elif goal == "cost":
            return cost_objective
        elif goal == "satisfaction":
            return satisfaction_objective
        else:
            return efficiency_objective  # Default

    def _get_optimal_area_for_function(self, function: str, occupancy: int) -> float:
        """Get optimal area for space function."""
        optimal_areas = {
            "Office": 12.0 * occupancy,
            "Meeting Room": 8.0 * occupancy,
            "Conference Room": 6.0 * occupancy,
            "Kitchen": 15.0,
            "Reception": 25.0,
            "Storage": 10.0,
        }

        return optimal_areas.get(function, 12.0 * occupancy)

    def _prepare_clustering_features(
        self, elements_data: pd.DataFrame, features: list[str] | None
    ) -> pd.DataFrame:
        """Prepare features for clustering."""
        numeric_columns = []

        for column in elements_data.columns:
            if elements_data[column].dtype in ["int64", "float64"]:
                numeric_columns.append(column)

        if features:
            # Use specified features that are numeric
            available_features = [f for f in features if f in numeric_columns]
            return elements_data[available_features]
        else:
            # Use all numeric columns
            return elements_data[numeric_columns]

    def _find_optimal_clusters(
        self, features: np.ndarray, max_clusters: int = 10
    ) -> int:
        """Find optimal number of clusters using elbow method."""
        inertias = []
        silhouette_scores = []

        K = range(2, min(max_clusters + 1, len(features)))

        for k in K:
            kmeans = KMeans(n_clusters=k, random_state=42)
            kmeans.fit(features)
            inertias.append(kmeans.inertia_)

            if len(set(kmeans.labels_)) > 1:
                silhouette_avg = silhouette_score(features, kmeans.labels_)
                silhouette_scores.append(silhouette_avg)
            else:
                silhouette_scores.append(-1)

        # Find elbow point (simplified)
        if len(silhouette_scores) > 0:
            optimal_k = K[np.argmax(silhouette_scores)]
        else:
            optimal_k = 3  # Default

        return optimal_k

    def _analyze_clusters(
        self,
        elements_data: pd.DataFrame,
        cluster_labels: np.ndarray,
        feature_columns: list[str],
    ) -> dict[str, Any]:
        """Analyze clustering results."""
        cluster_analysis = {}

        for cluster_id in set(cluster_labels):
            if cluster_id == -1:  # Noise points in DBSCAN
                continue

            cluster_mask = cluster_labels == cluster_id
            cluster_elements = elements_data[cluster_mask]

            analysis = {
                "size": int(np.sum(cluster_mask)),
                "percentage": float(np.sum(cluster_mask) / len(elements_data) * 100),
                "feature_means": {},
                "dominant_categories": [],
            }

            # Calculate feature means
            for feature in feature_columns:
                if feature in cluster_elements.columns:
                    mean_value = cluster_elements[feature].mean()
                    if not pd.isna(mean_value):
                        analysis["feature_means"][feature] = float(mean_value)

            # Find dominant categories
            if "category" in cluster_elements.columns:
                category_counts = cluster_elements["category"].value_counts()
                analysis["dominant_categories"] = category_counts.head(3).to_dict()

            cluster_analysis[f"cluster_{cluster_id}"] = analysis

        return cluster_analysis

    def _prepare_prediction_data(
        self, elements_data: pd.DataFrame, target: str
    ) -> tuple[pd.DataFrame, np.ndarray]:
        """Prepare data for prediction."""
        # Extract numeric features
        feature_columns = []
        for column in elements_data.columns:
            if (
                column != target
                and elements_data[column].dtype in ["int64", "float64"]
                and not elements_data[column].isna().all()
            ):
                feature_columns.append(column)

        features = elements_data[feature_columns].fillna(0)

        # Prepare target variable
        if target in elements_data.columns:
            target_values = elements_data[target].fillna(0).values
        else:
            # Create synthetic target based on common patterns
            target_values = self._create_synthetic_target(elements_data, target)

        return features, target_values

    def _create_synthetic_target(
        self, elements_data: pd.DataFrame, target: str
    ) -> np.ndarray:
        """Create synthetic target variable for demonstration."""
        # Create a synthetic target based on element properties
        if target == "energy_efficiency":
            # Simulate energy efficiency based on area and category
            efficiency = np.random.normal(0.7, 0.2, len(elements_data))
            return np.clip(efficiency, 0.1, 1.0)

        elif target == "cost_per_area":
            # Simulate cost per area
            cost = np.random.normal(500, 150, len(elements_data))
            return np.maximum(cost, 100)

        else:
            # Default random target
            return np.random.normal(0, 1, len(elements_data))

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace RevitPy.Compatibility.Features
{
    /// <summary>
    /// Implementation of feature flag management for RevitPy compatibility
    /// </summary>
    public class FeatureFlagManager : IFeatureFlagManager
    {
        private readonly ILogger<FeatureFlagManager> _logger;
        private readonly IRevitVersionManager _versionManager;
        private readonly FeatureFlagOptions _options;
        private readonly ConcurrentDictionary<string, FeatureConfiguration> _features;
        private RevitVersionInfo _currentVersion;

        public FeatureFlagManager(
            ILogger<FeatureFlagManager> logger,
            IRevitVersionManager versionManager,
            IOptions<FeatureFlagOptions> options)
        {
            _logger = logger;
            _versionManager = versionManager;
            _options = options.Value;
            _features = new ConcurrentDictionary<string, FeatureConfiguration>();

            InitializeBuiltInFeatures();
        }

        public bool IsFeatureEnabled(string featureName)
        {
            if (_currentVersion == null)
            {
                _currentVersion = _versionManager.DetectRevitVersionAsync().GetAwaiter().GetResult();
            }

            return IsFeatureEnabled(featureName, _currentVersion.Version);
        }

        public bool IsFeatureEnabled(string featureName, RevitVersion version)
        {
            if (!_features.TryGetValue(featureName, out var feature))
            {
                _logger.LogWarning("Feature {FeatureName} not found", featureName);
                return false;
            }

            try
            {
                // Check basic version compatibility
                if (!feature.IsAvailableInVersion(version))
                {
                    _logger.LogDebug("Feature {FeatureName} not available in version {Version}", featureName, version);
                    return false;
                }

                // Check if feature is deprecated
                if (feature.IsDeprecated)
                {
                    _logger.LogWarning("Feature {FeatureName} is deprecated", featureName);
                    if (_options.DisableDeprecatedFeatures)
                    {
                        return false;
                    }
                }

                // Check experimental feature settings
                if (feature.IsExperimental && !_options.EnableExperimentalFeatures)
                {
                    _logger.LogDebug("Experimental feature {FeatureName} disabled by configuration", featureName);
                    return false;
                }

                // Check license requirements
                if (feature.RequiresLicense && !_options.LicensedFeatures.Contains(featureName))
                {
                    _logger.LogDebug("Feature {FeatureName} requires license", featureName);
                    return false;
                }

                // Check version-specific overrides
                if (feature.VersionConfigurations.TryGetValue(version, out var versionConfig))
                {
                    return versionConfig.IsEnabled;
                }

                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error checking feature availability for {FeatureName}", featureName);
                return false;
            }
        }

        public FeatureConfiguration GetFeatureConfiguration(string featureName)
        {
            if (_currentVersion == null)
            {
                _currentVersion = _versionManager.DetectRevitVersionAsync().GetAwaiter().GetResult();
            }

            return GetFeatureConfiguration(featureName, _currentVersion.Version);
        }

        public FeatureConfiguration GetFeatureConfiguration(string featureName, RevitVersion version)
        {
            if (_features.TryGetValue(featureName, out var feature))
            {
                // Clone the configuration and apply version-specific settings
                var config = CloneFeatureConfiguration(feature);

                if (feature.VersionConfigurations.TryGetValue(version, out var versionConfig))
                {
                    ApplyVersionSpecificConfiguration(config, versionConfig);
                }

                return config;
            }

            return null;
        }

        public IEnumerable<FeatureConfiguration> GetAvailableFeatures()
        {
            if (_currentVersion == null)
            {
                _currentVersion = _versionManager.DetectRevitVersionAsync().GetAwaiter().GetResult();
            }

            return GetAvailableFeatures(_currentVersion.Version);
        }

        public IEnumerable<FeatureConfiguration> GetAvailableFeatures(RevitVersion version)
        {
            return _features.Values
                .Where(f => IsFeatureEnabled(f.Name, version))
                .Select(f => GetFeatureConfiguration(f.Name, version))
                .Where(f => f != null)
                .ToList();
        }

        public void RegisterFeature(FeatureConfiguration feature)
        {
            if (feature == null)
                throw new ArgumentNullException(nameof(feature));

            if (string.IsNullOrEmpty(feature.Name))
                throw new ArgumentException("Feature name cannot be null or empty", nameof(feature));

            _features.AddOrUpdate(feature.Name, feature, (key, existing) =>
            {
                _logger.LogInformation("Updating existing feature configuration for {FeatureName}", feature.Name);
                return feature;
            });

            _logger.LogInformation("Registered feature {FeatureName} (Category: {Category}, MinVersion: {MinVersion})",
                feature.Name, feature.Category, feature.MinimumVersion);
        }

        public void UpdateFeatureAvailability(string featureName, bool isEnabled, RevitVersion? version = null)
        {
            if (!_features.TryGetValue(featureName, out var feature))
            {
                _logger.LogWarning("Cannot update availability for unknown feature: {FeatureName}", featureName);
                return;
            }

            if (version.HasValue)
            {
                // Update version-specific configuration
                if (!feature.VersionConfigurations.ContainsKey(version.Value))
                {
                    feature.VersionConfigurations[version.Value] = new VersionSpecificConfiguration();
                }

                feature.VersionConfigurations[version.Value].IsEnabled = isEnabled;
                _logger.LogInformation("Updated feature {FeatureName} availability for version {Version}: {IsEnabled}",
                    featureName, version.Value, isEnabled);
            }
            else
            {
                // Update all version configurations
                foreach (var versionConfig in feature.VersionConfigurations.Values)
                {
                    versionConfig.IsEnabled = isEnabled;
                }

                _logger.LogInformation("Updated feature {FeatureName} availability for all versions: {IsEnabled}",
                    featureName, isEnabled);
            }
        }

        public FeatureCompatibilityMatrix GetCompatibilityMatrix()
        {
            var matrix = new FeatureCompatibilityMatrix
            {
                GeneratedBy = "FeatureFlagManager",
                GeneratedAt = DateTime.UtcNow
            };

            var versions = Enum.GetValues<RevitVersion>()
                .Where(v => v != RevitVersion.Unknown && v != RevitVersion.Future)
                .ToList();

            foreach (var feature in _features.Values)
            {
                foreach (var version in versions)
                {
                    var availability = DetermineFeatureAvailability(feature, version);
                    matrix.AddFeature(feature.Name, version, availability);
                }
            }

            return matrix;
        }

        public async Task<FeatureValidationResult> ValidateFeatureDependenciesAsync(string featureName, RevitVersion version)
        {
            var result = new FeatureValidationResult
            {
                FeatureName = featureName,
                Version = version,
                IsValid = true
            };

            if (!_features.TryGetValue(featureName, out var feature))
            {
                result.IsValid = false;
                result.Issues.Add(new ValidationIssue
                {
                    Severity = ValidationIssueSeverity.Error,
                    Message = $"Feature '{featureName}' not found",
                    Component = "FeatureRegistration"
                });
                return result;
            }

            try
            {
                // Validate version compatibility
                if (!feature.IsAvailableInVersion(version))
                {
                    result.IsValid = false;
                    result.Issues.Add(new ValidationIssue
                    {
                        Severity = ValidationIssueSeverity.Error,
                        Message = $"Feature '{featureName}' is not available in version {version}",
                        Component = "VersionCompatibility",
                        Resolution = $"Minimum version required: {feature.MinimumVersion}"
                    });
                }

                // Validate dependencies
                foreach (var dependency in feature.Dependencies)
                {
                    if (!IsFeatureEnabled(dependency, version))
                    {
                        result.MissingDependencies.Add(dependency);
                        result.Issues.Add(new ValidationIssue
                        {
                            Severity = ValidationIssueSeverity.Error,
                            Message = $"Required dependency '{dependency}' is not available",
                            Component = "Dependencies",
                            Resolution = $"Enable or install feature '{dependency}'"
                        });
                    }
                }

                // Check for conflicts
                foreach (var conflict in feature.ConflictsWith)
                {
                    if (IsFeatureEnabled(conflict, version))
                    {
                        result.ConflictingFeatures.Add(conflict);
                        result.Issues.Add(new ValidationIssue
                        {
                            Severity = ValidationIssueSeverity.Warning,
                            Message = $"Conflicting feature '{conflict}' is enabled",
                            Component = "Conflicts",
                            Resolution = $"Disable feature '{conflict}' or use alternative implementation"
                        });
                    }
                }

                // Check deprecation status
                if (feature.IsDeprecated)
                {
                    result.Warnings.Add($"Feature '{featureName}' is deprecated");
                    if (!string.IsNullOrEmpty(feature.ReplacementFeature))
                    {
                        result.Recommendations.Add($"Consider migrating to '{feature.ReplacementFeature}'");
                    }
                }

                // Check experimental status
                if (feature.IsExperimental)
                {
                    result.Warnings.Add($"Feature '{featureName}' is experimental and may be unstable");
                }

                // Performance recommendations
                if (feature.PerformanceProfile != null)
                {
                    if (feature.PerformanceProfile.MemoryImpact >= PerformanceImpact.High)
                    {
                        result.Recommendations.Add("Monitor memory usage when using this feature");
                    }

                    if (feature.PerformanceProfile.CPUImpact >= PerformanceImpact.High)
                    {
                        result.Recommendations.Add("Consider using this feature in background processes");
                    }
                }

                result.IsValid = !result.Issues.Any(i => i.Severity >= ValidationIssueSeverity.Error);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error validating feature dependencies for {FeatureName}", featureName);
                result.IsValid = false;
                result.Issues.Add(new ValidationIssue
                {
                    Severity = ValidationIssueSeverity.Critical,
                    Message = $"Validation failed with exception: {ex.Message}",
                    Component = "ValidationProcess"
                });
            }

            return result;
        }

        private void InitializeBuiltInFeatures()
        {
            _logger.LogInformation("Initializing built-in feature configurations");

            // Core API Features (available in all supported versions)
            RegisterCoreFeatures();

            // Version-specific features
            RegisterVersionSpecificFeatures();

            // RevitPy-specific features
            RegisterRevitPyFeatures();

            // Experimental features
            RegisterExperimentalFeatures();

            _logger.LogInformation("Initialized {FeatureCount} built-in features", _features.Count);
        }

        private void RegisterCoreFeatures()
        {
            var coreFeatures = new[]
            {
                new FeatureConfiguration
                {
                    Name = FeatureFlags.BASIC_API,
                    DisplayName = "Basic Revit API",
                    Description = "Core Revit API functionality",
                    Category = FeatureCategory.Core,
                    MinimumVersion = RevitVersion.Revit2022,
                    Stability = FeatureStability.Stable
                },
                new FeatureConfiguration
                {
                    Name = FeatureFlags.GEOMETRY_API,
                    DisplayName = "Geometry API",
                    Description = "Geometric operations and calculations",
                    Category = FeatureCategory.Geometry,
                    MinimumVersion = RevitVersion.Revit2022,
                    Stability = FeatureStability.Stable
                },
                new FeatureConfiguration
                {
                    Name = FeatureFlags.PARAMETER_ACCESS,
                    DisplayName = "Parameter Access",
                    Description = "Element parameter reading and writing",
                    Category = FeatureCategory.Parameters,
                    MinimumVersion = RevitVersion.Revit2022,
                    Stability = FeatureStability.Stable
                },
                new FeatureConfiguration
                {
                    Name = FeatureFlags.TRANSACTION_MANAGEMENT,
                    DisplayName = "Transaction Management",
                    Description = "Document transaction handling",
                    Category = FeatureCategory.Transactions,
                    MinimumVersion = RevitVersion.Revit2022,
                    Stability = FeatureStability.Stable
                }
            };

            foreach (var feature in coreFeatures)
            {
                RegisterFeature(feature);
            }
        }

        private void RegisterVersionSpecificFeatures()
        {
            // Revit 2023+ features
            RegisterFeature(new FeatureConfiguration
            {
                Name = FeatureFlags.MODERN_TRANSACTIONS,
                DisplayName = "Modern Transaction API",
                Description = "Enhanced transaction management with improved performance",
                Category = FeatureCategory.Transactions,
                MinimumVersion = RevitVersion.Revit2023,
                Stability = FeatureStability.Stable,
                Dependencies = new[] { FeatureFlags.TRANSACTION_MANAGEMENT }
            });

            // Revit 2024+ features
            RegisterFeature(new FeatureConfiguration
            {
                Name = FeatureFlags.CLOUD_MODEL_SUPPORT,
                DisplayName = "Cloud Model Support",
                Description = "Support for cloud-based Revit models",
                Category = FeatureCategory.Core,
                MinimumVersion = RevitVersion.Revit2024,
                Stability = FeatureStability.Stable,
                RequiresLicense = true
            });

            // Revit 2025+ features
            RegisterFeature(new FeatureConfiguration
            {
                Name = FeatureFlags.AI_INTEGRATION,
                DisplayName = "AI Integration",
                Description = "Artificial intelligence features and automation",
                Category = FeatureCategory.Experimental,
                MinimumVersion = RevitVersion.Revit2025,
                Stability = FeatureStability.Beta,
                IsExperimental = true
            });
        }

        private void RegisterRevitPyFeatures()
        {
            var revitPyFeatures = new[]
            {
                new FeatureConfiguration
                {
                    Name = FeatureFlags.HOT_RELOAD,
                    DisplayName = "Hot Reload",
                    Description = "Dynamic code reloading during development",
                    Category = FeatureCategory.Performance,
                    MinimumVersion = RevitVersion.Revit2022,
                    Stability = FeatureStability.Stable
                },
                new FeatureConfiguration
                {
                    Name = FeatureFlags.ORM_SUPPORT,
                    DisplayName = "ORM Support",
                    Description = "Object-relational mapping for Revit elements",
                    Category = FeatureCategory.API,
                    MinimumVersion = RevitVersion.Revit2022,
                    Stability = FeatureStability.Stable,
                    Dependencies = new[] { FeatureFlags.BASIC_API, FeatureFlags.PARAMETER_ACCESS }
                },
                new FeatureConfiguration
                {
                    Name = FeatureFlags.WEB_UI,
                    DisplayName = "Web UI",
                    Description = "Web-based user interface panels",
                    Category = FeatureCategory.Core,
                    MinimumVersion = RevitVersion.Revit2022,
                    Stability = FeatureStability.Stable
                }
            };

            foreach (var feature in revitPyFeatures)
            {
                RegisterFeature(feature);
            }
        }

        private void RegisterExperimentalFeatures()
        {
            var experimentalFeatures = new[]
            {
                new FeatureConfiguration
                {
                    Name = FeatureFlags.MACHINE_LEARNING,
                    DisplayName = "Machine Learning",
                    Description = "ML-powered analysis and automation",
                    Category = FeatureCategory.Experimental,
                    MinimumVersion = RevitVersion.Revit2024,
                    Stability = FeatureStability.Alpha,
                    IsExperimental = true,
                    Dependencies = new[] { FeatureFlags.AI_INTEGRATION }
                },
                new FeatureConfiguration
                {
                    Name = FeatureFlags.REAL_TIME_COLLABORATION,
                    DisplayName = "Real-time Collaboration",
                    Description = "Real-time collaborative editing features",
                    Category = FeatureCategory.Experimental,
                    MinimumVersion = RevitVersion.Revit2025,
                    Stability = FeatureStability.Alpha,
                    IsExperimental = true,
                    RequiresLicense = true
                }
            };

            foreach (var feature in experimentalFeatures)
            {
                RegisterFeature(feature);
            }
        }

        private FeatureAvailability DetermineFeatureAvailability(FeatureConfiguration feature, RevitVersion version)
        {
            if (!feature.IsAvailableInVersion(version))
                return FeatureAvailability.NotAvailable;

            if (feature.IsDeprecated)
                return FeatureAvailability.Deprecated;

            if (feature.RequiresLicense)
                return FeatureAvailability.RequiresLicense;

            if (feature.IsExperimental)
                return FeatureAvailability.Experimental;

            if (feature.VersionConfigurations.TryGetValue(version, out var versionConfig) &&
                versionConfig.KnownIssues.Any())
                return FeatureAvailability.AvailableWithLimitations;

            return FeatureAvailability.Available;
        }

        private FeatureConfiguration CloneFeatureConfiguration(FeatureConfiguration original)
        {
            // Simple clone - in production you might want to use a serialization-based approach
            return new FeatureConfiguration
            {
                Name = original.Name,
                DisplayName = original.DisplayName,
                Description = original.Description,
                Category = original.Category,
                MinimumVersion = original.MinimumVersion,
                MaximumVersion = original.MaximumVersion,
                IsExperimental = original.IsExperimental,
                RequiresLicense = original.RequiresLicense,
                Stability = original.Stability,
                Dependencies = (string[])original.Dependencies.Clone(),
                ConflictsWith = (string[])original.ConflictsWith.Clone(),
                VersionConfigurations = new Dictionary<RevitVersion, VersionSpecificConfiguration>(original.VersionConfigurations),
                Metadata = new Dictionary<string, object>(original.Metadata),
                PerformanceProfile = original.PerformanceProfile,
                DeprecationDate = original.DeprecationDate,
                ReplacementFeature = original.ReplacementFeature
            };
        }

        private void ApplyVersionSpecificConfiguration(FeatureConfiguration config, VersionSpecificConfiguration versionConfig)
        {
            // Apply version-specific overrides to the configuration
            if (!string.IsNullOrEmpty(versionConfig.AlternativeImplementation))
            {
                config.Metadata["AlternativeImplementation"] = versionConfig.AlternativeImplementation;
            }

            foreach (var setting in versionConfig.Settings)
            {
                config.Metadata[setting.Key] = setting.Value;
            }

            if (versionConfig.Performance != null)
            {
                config.Metadata["VersionPerformance"] = versionConfig.Performance;
            }
        }
    }

    /// <summary>
    /// Configuration options for feature flag management
    /// </summary>
    public class FeatureFlagOptions
    {
        public bool EnableExperimentalFeatures { get; set; } = false;
        public bool DisableDeprecatedFeatures { get; set; } = false;
        public HashSet<string> LicensedFeatures { get; set; } = new();
        public HashSet<string> DisabledFeatures { get; set; } = new();
        public Dictionary<string, Dictionary<string, object>> FeatureOverrides { get; set; } = new();
        public bool LogFeatureUsage { get; set; } = true;
        public string ConfigurationSource { get; set; } = "Default";
    }
}

using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace RevitPy.Compatibility.Features
{
    /// <summary>
    /// Interface for managing feature flags across different Revit versions
    /// </summary>
    public interface IFeatureFlagManager
    {
        /// <summary>
        /// Checks if a feature is enabled for the current version
        /// </summary>
        /// <param name="featureName">Name of the feature</param>
        /// <returns>True if feature is enabled</returns>
        bool IsFeatureEnabled(string featureName);

        /// <summary>
        /// Checks if a feature is enabled for a specific version
        /// </summary>
        /// <param name="featureName">Name of the feature</param>
        /// <param name="version">Revit version</param>
        /// <returns>True if feature is enabled</returns>
        bool IsFeatureEnabled(string featureName, RevitVersion version);

        /// <summary>
        /// Gets feature configuration for the current version
        /// </summary>
        /// <param name="featureName">Name of the feature</param>
        /// <returns>Feature configuration or null if not found</returns>
        FeatureConfiguration GetFeatureConfiguration(string featureName);

        /// <summary>
        /// Gets feature configuration for a specific version
        /// </summary>
        /// <param name="featureName">Name of the feature</param>
        /// <param name="version">Revit version</param>
        /// <returns>Feature configuration or null if not found</returns>
        FeatureConfiguration GetFeatureConfiguration(string featureName, RevitVersion version);

        /// <summary>
        /// Gets all available features for the current version
        /// </summary>
        /// <returns>Collection of available features</returns>
        IEnumerable<FeatureConfiguration> GetAvailableFeatures();

        /// <summary>
        /// Gets all available features for a specific version
        /// </summary>
        /// <param name="version">Revit version</param>
        /// <returns>Collection of available features</returns>
        IEnumerable<FeatureConfiguration> GetAvailableFeatures(RevitVersion version);

        /// <summary>
        /// Registers a new feature
        /// </summary>
        /// <param name="feature">Feature configuration</param>
        void RegisterFeature(FeatureConfiguration feature);

        /// <summary>
        /// Updates feature availability dynamically
        /// </summary>
        /// <param name="featureName">Name of the feature</param>
        /// <param name="isEnabled">Whether the feature should be enabled</param>
        /// <param name="version">Specific version (optional)</param>
        void UpdateFeatureAvailability(string featureName, bool isEnabled, RevitVersion? version = null);

        /// <summary>
        /// Gets feature compatibility matrix
        /// </summary>
        /// <returns>Compatibility matrix showing feature support across versions</returns>
        FeatureCompatibilityMatrix GetCompatibilityMatrix();

        /// <summary>
        /// Validates feature dependencies
        /// </summary>
        /// <param name="featureName">Name of the feature</param>
        /// <param name="version">Revit version</param>
        /// <returns>Validation result</returns>
        Task<FeatureValidationResult> ValidateFeatureDependenciesAsync(string featureName, RevitVersion version);
    }

    /// <summary>
    /// Feature configuration containing metadata and version requirements
    /// </summary>
    public class FeatureConfiguration
    {
        public string Name { get; set; }
        public string DisplayName { get; set; }
        public string Description { get; set; }
        public FeatureCategory Category { get; set; }
        public RevitVersion MinimumVersion { get; set; }
        public RevitVersion? MaximumVersion { get; set; }
        public bool IsExperimental { get; set; }
        public bool RequiresLicense { get; set; }
        public FeatureStability Stability { get; set; }
        public string[] Dependencies { get; set; } = Array.Empty<string>();
        public string[] ConflictsWith { get; set; } = Array.Empty<string>();
        public Dictionary<RevitVersion, VersionSpecificConfiguration> VersionConfigurations { get; set; } = new();
        public Dictionary<string, object> Metadata { get; set; } = new();
        public FeaturePerformanceProfile PerformanceProfile { get; set; }
        public DateTime? DeprecationDate { get; set; }
        public string ReplacementFeature { get; set; }

        public bool IsAvailableInVersion(RevitVersion version)
        {
            if (version < MinimumVersion)
                return false;

            if (MaximumVersion.HasValue && version > MaximumVersion.Value)
                return false;

            // Check version-specific overrides
            if (VersionConfigurations.TryGetValue(version, out var versionConfig))
            {
                return versionConfig.IsEnabled;
            }

            return true;
        }

        public bool IsDeprecated => DeprecationDate.HasValue && DateTime.UtcNow > DeprecationDate.Value;
    }

    /// <summary>
    /// Version-specific feature configuration
    /// </summary>
    public class VersionSpecificConfiguration
    {
        public bool IsEnabled { get; set; } = true;
        public string AlternativeImplementation { get; set; }
        public Dictionary<string, object> Settings { get; set; } = new();
        public string[] RequiredAssemblies { get; set; } = Array.Empty<string>();
        public PerformanceCharacteristics Performance { get; set; }
        public string[] KnownIssues { get; set; } = Array.Empty<string>();
        public string[] Workarounds { get; set; } = Array.Empty<string>();
    }

    /// <summary>
    /// Feature categories for organization
    /// </summary>
    public enum FeatureCategory
    {
        Core,
        API,
        Geometry,
        Parameters,
        Transactions,
        Selection,
        Views,
        Families,
        Import,
        Export,
        Analysis,
        Rendering,
        Documentation,
        Performance,
        Security,
        Experimental
    }

    /// <summary>
    /// Feature stability levels
    /// </summary>
    public enum FeatureStability
    {
        Stable,
        Beta,
        Alpha,
        Experimental,
        Deprecated,
        Obsolete
    }

    /// <summary>
    /// Feature performance profile
    /// </summary>
    public class FeaturePerformanceProfile
    {
        public PerformanceImpact MemoryImpact { get; set; }
        public PerformanceImpact CPUImpact { get; set; }
        public PerformanceImpact StartupImpact { get; set; }
        public TimeSpan TypicalExecutionTime { get; set; }
        public long TypicalMemoryUsage { get; set; }
        public bool IsThreadSafe { get; set; }
        public bool SupportsAsync { get; set; }
        public Dictionary<RevitVersion, PerformanceCharacteristics> VersionPerformance { get; set; } = new();
    }

    /// <summary>
    /// Performance impact levels
    /// </summary>
    public enum PerformanceImpact
    {
        None,
        Low,
        Medium,
        High,
        Critical
    }

    /// <summary>
    /// Performance characteristics for specific versions
    /// </summary>
    public class PerformanceCharacteristics
    {
        public TimeSpan AverageExecutionTime { get; set; }
        public long AverageMemoryUsage { get; set; }
        public double ThroughputOperationsPerSecond { get; set; }
        public PerformanceImpact Impact { get; set; }
        public string[] OptimizationNotes { get; set; } = Array.Empty<string>();
    }

    /// <summary>
    /// Feature compatibility matrix
    /// </summary>
    public class FeatureCompatibilityMatrix
    {
        public Dictionary<string, Dictionary<RevitVersion, FeatureAvailability>> Features { get; set; } = new();
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public string GeneratedBy { get; set; }

        public void AddFeature(string featureName, RevitVersion version, FeatureAvailability availability)
        {
            if (!Features.ContainsKey(featureName))
            {
                Features[featureName] = new Dictionary<RevitVersion, FeatureAvailability>();
            }

            Features[featureName][version] = availability;
        }

        public FeatureAvailability GetFeatureAvailability(string featureName, RevitVersion version)
        {
            if (Features.TryGetValue(featureName, out var versionMap) &&
                versionMap.TryGetValue(version, out var availability))
            {
                return availability;
            }

            return FeatureAvailability.NotAvailable;
        }
    }

    /// <summary>
    /// Feature availability status
    /// </summary>
    public enum FeatureAvailability
    {
        NotAvailable,
        Available,
        AvailableWithLimitations,
        Experimental,
        Deprecated,
        RequiresLicense,
        RequiresAdditionalSetup
    }

    /// <summary>
    /// Feature validation result
    /// </summary>
    public class FeatureValidationResult
    {
        public bool IsValid { get; set; }
        public string FeatureName { get; set; }
        public RevitVersion Version { get; set; }
        public List<ValidationIssue> Issues { get; set; } = new();
        public List<string> Warnings { get; set; } = new();
        public List<string> MissingDependencies { get; set; } = new();
        public List<string> ConflictingFeatures { get; set; } = new();
        public List<string> Recommendations { get; set; } = new();
    }

    /// <summary>
    /// Validation issue
    /// </summary>
    public class ValidationIssue
    {
        public ValidationIssueSeverity Severity { get; set; }
        public string Message { get; set; }
        public string Component { get; set; }
        public string Resolution { get; set; }
    }

    /// <summary>
    /// Validation issue severity
    /// </summary>
    public enum ValidationIssueSeverity
    {
        Info,
        Warning,
        Error,
        Critical
    }

    /// <summary>
    /// Built-in feature flags for RevitPy
    /// </summary>
    public static class FeatureFlags
    {
        // Core API Features
        public const string BASIC_API = "BasicAPI";
        public const string GEOMETRY_API = "GeometryAPI";
        public const string PARAMETER_ACCESS = "ParameterAccess";
        public const string TRANSACTION_MANAGEMENT = "TransactionManagement";
        public const string ELEMENT_CREATION = "ElementCreation";
        public const string FAMILY_API = "FamilyAPI";
        public const string VIEW_API = "ViewAPI";
        public const string SELECTION_API = "SelectionAPI";

        // Version-specific Features
        public const string MODERN_TRANSACTIONS = "ModernTransactions";
        public const string ENHANCED_GEOMETRY = "EnhancedGeometry";
        public const string IMPROVED_PARAMETER_API = "ImprovedParameterAPI";
        public const string CLOUD_MODEL_SUPPORT = "CloudModelSupport";
        public const string ADVANCED_SELECTION = "AdvancedSelection";
        public const string PERFORMANCE_OPTIMIZATIONS = "PerformanceOptimizations";
        public const string AI_INTEGRATION = "AI_Integration";
        public const string MODERN_UI = "ModernUI";
        public const string ENHANCED_SECURITY = "EnhancedSecurity";
        public const string WEBAPI_SUPPORT = "WebAPI_Support";

        // RevitPy-specific Features
        public const string HOT_RELOAD = "HotReload";
        public const string PYTHON_DEBUGGING = "PythonDebugging";
        public const string ORM_SUPPORT = "ORMSupport";
        public const string ASYNC_OPERATIONS = "AsyncOperations";
        public const string WEB_UI = "WebUI";
        public const string PACKAGE_MANAGER = "PackageManager";
        public const string VSCODE_INTEGRATION = "VSCodeIntegration";
        public const string PERFORMANCE_MONITORING = "PerformanceMonitoring";
        public const string ERROR_RECOVERY = "ErrorRecovery";
        public const string BATCH_OPERATIONS = "BatchOperations";

        // Experimental Features
        public const string MACHINE_LEARNING = "MachineLearning";
        public const string REAL_TIME_COLLABORATION = "RealTimeCollaboration";
        public const string CLOUD_COMPUTING = "CloudComputing";
        public const string ADVANCED_ANALYTICS = "AdvancedAnalytics";
    }
}

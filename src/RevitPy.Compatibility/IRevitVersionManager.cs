using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace RevitPy.Compatibility
{
    /// <summary>
    /// Interface for managing Revit version detection and compatibility
    /// </summary>
    public interface IRevitVersionManager
    {
        /// <summary>
        /// Detects the current Revit version
        /// </summary>
        /// <returns>Revit version information</returns>
        Task<RevitVersionInfo> DetectRevitVersionAsync();
        
        /// <summary>
        /// Gets supported features for a specific Revit version
        /// </summary>
        /// <param name="version">Revit version</param>
        /// <returns>List of supported features</returns>
        IEnumerable<string> GetSupportedFeatures(RevitVersion version);
        
        /// <summary>
        /// Checks if a feature is available in the specified version
        /// </summary>
        /// <param name="feature">Feature name</param>
        /// <param name="version">Revit version</param>
        /// <returns>True if feature is available</returns>
        bool IsFeatureAvailable(string feature, RevitVersion version);
        
        /// <summary>
        /// Gets the minimum required version for a feature
        /// </summary>
        /// <param name="feature">Feature name</param>
        /// <returns>Minimum Revit version required</returns>
        RevitVersion GetMinimumVersionForFeature(string feature);
        
        /// <summary>
        /// Validates compatibility for current environment
        /// </summary>
        /// <returns>Compatibility validation result</returns>
        Task<CompatibilityResult> ValidateCompatibilityAsync();
        
        /// <summary>
        /// Gets version-specific configuration
        /// </summary>
        /// <param name="version">Revit version</param>
        /// <returns>Version-specific configuration</returns>
        VersionConfiguration GetVersionConfiguration(RevitVersion version);
    }
    
    /// <summary>
    /// Revit version information
    /// </summary>
    public class RevitVersionInfo
    {
        public RevitVersion Version { get; set; }
        public string VersionString { get; set; }
        public string BuildNumber { get; set; }
        public string ProductName { get; set; }
        public DateTime ReleaseDate { get; set; }
        public string[] SupportedLanguages { get; set; }
        public string InstallationPath { get; set; }
        public bool IsValidInstallation { get; set; }
        public Dictionary<string, object> AdditionalInfo { get; set; } = new();
    }
    
    /// <summary>
    /// Revit version enumeration
    /// </summary>
    public enum RevitVersion
    {
        Unknown = 0,
        Revit2022 = 2022,
        Revit2023 = 2023,
        Revit2024 = 2024,
        Revit2025 = 2025,
        Revit2026 = 2026,
        Future = 9999
    }
    
    /// <summary>
    /// Compatibility validation result
    /// </summary>
    public class CompatibilityResult
    {
        public bool IsCompatible { get; set; }
        public RevitVersionInfo DetectedVersion { get; set; }
        public List<CompatibilityIssue> Issues { get; set; } = new();
        public List<string> Warnings { get; set; } = new();
        public List<string> Recommendations { get; set; } = new();
        public Dictionary<string, bool> FeatureCompatibility { get; set; } = new();
    }
    
    /// <summary>
    /// Compatibility issue
    /// </summary>
    public class CompatibilityIssue
    {
        public CompatibilityIssueSeverity Severity { get; set; }
        public string Feature { get; set; }
        public string Message { get; set; }
        public string Recommendation { get; set; }
        public string AlternativeImplementation { get; set; }
    }
    
    /// <summary>
    /// Compatibility issue severity
    /// </summary>
    public enum CompatibilityIssueSeverity
    {
        Info,
        Warning,
        Error,
        Critical
    }
    
    /// <summary>
    /// Version-specific configuration
    /// </summary>
    public class VersionConfiguration
    {
        public RevitVersion Version { get; set; }
        public string DotNetVersion { get; set; }
        public string[] RequiredAssemblies { get; set; }
        public Dictionary<string, string> APIEndpoints { get; set; } = new();
        public Dictionary<string, object> VersionSpecificSettings { get; set; } = new();
        public string[] DeprecatedMethods { get; set; }
        public Dictionary<string, string> MethodMappings { get; set; } = new();
    }
}
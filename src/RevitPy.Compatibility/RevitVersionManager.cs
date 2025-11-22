using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Win32;

namespace RevitPy.Compatibility
{
    /// <summary>
    /// Implementation of Revit version detection and compatibility management
    /// </summary>
    public class RevitVersionManager : IRevitVersionManager
    {
        private readonly ILogger<RevitVersionManager> _logger;
        private readonly Dictionary<RevitVersion, VersionConfiguration> _versionConfigurations;
        private readonly Dictionary<string, RevitVersion> _featureMinVersions;

        private static readonly Dictionary<RevitVersion, string[]> VersionFeatures = new()
        {
            {
                RevitVersion.Revit2022,
                new[]
                {
                    "BasicAPI", "GeometryAPI", "ParameterAccess", "TransactionManagement",
                    "ElementCreation", "FamilyAPI", "ViewAPI", "SelectionAPI"
                }
            },
            {
                RevitVersion.Revit2023,
                new[]
                {
                    "BasicAPI", "GeometryAPI", "ParameterAccess", "TransactionManagement",
                    "ElementCreation", "FamilyAPI", "ViewAPI", "SelectionAPI",
                    "ModernTransactions", "EnhancedGeometry", "ImprovedParameterAPI"
                }
            },
            {
                RevitVersion.Revit2024,
                new[]
                {
                    "BasicAPI", "GeometryAPI", "ParameterAccess", "TransactionManagement",
                    "ElementCreation", "FamilyAPI", "ViewAPI", "SelectionAPI",
                    "ModernTransactions", "EnhancedGeometry", "ImprovedParameterAPI",
                    "CloudModelSupport", "AdvancedSelection", "PerformanceOptimizations"
                }
            },
            {
                RevitVersion.Revit2025,
                new[]
                {
                    "BasicAPI", "GeometryAPI", "ParameterAccess", "TransactionManagement",
                    "ElementCreation", "FamilyAPI", "ViewAPI", "SelectionAPI",
                    "ModernTransactions", "EnhancedGeometry", "ImprovedParameterAPI",
                    "CloudModelSupport", "AdvancedSelection", "PerformanceOptimizations",
                    "AI_Integration", "ModernUI", "EnhancedSecurity", "WebAPI_Support"
                }
            }
        };

        public RevitVersionManager(ILogger<RevitVersionManager> logger)
        {
            _logger = logger;
            _versionConfigurations = InitializeVersionConfigurations();
            _featureMinVersions = InitializeFeatureMinVersions();
        }

        public async Task<RevitVersionInfo> DetectRevitVersionAsync()
        {
            try
            {
                _logger.LogInformation("Starting Revit version detection");

                // Try multiple detection methods
                var versionInfo = await TryDetectFromRegistryAsync() ??
                                 await TryDetectFromApplicationAsync() ??
                                 await TryDetectFromFileSystemAsync() ??
                                 await TryDetectFromEnvironmentAsync();

                if (versionInfo != null)
                {
                    _logger.LogInformation("Detected Revit version: {Version} ({VersionString})",
                        versionInfo.Version, versionInfo.VersionString);
                    return versionInfo;
                }

                _logger.LogWarning("Could not detect Revit version, returning unknown");
                return new RevitVersionInfo
                {
                    Version = RevitVersion.Unknown,
                    VersionString = "Unknown",
                    IsValidInstallation = false
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during Revit version detection");
                throw;
            }
        }

        public IEnumerable<string> GetSupportedFeatures(RevitVersion version)
        {
            if (VersionFeatures.TryGetValue(version, out var features))
            {
                return features;
            }

            _logger.LogWarning("No features defined for Revit version: {Version}", version);
            return Enumerable.Empty<string>();
        }

        public bool IsFeatureAvailable(string feature, RevitVersion version)
        {
            var supportedFeatures = GetSupportedFeatures(version);
            return supportedFeatures.Contains(feature, StringComparer.OrdinalIgnoreCase);
        }

        public RevitVersion GetMinimumVersionForFeature(string feature)
        {
            if (_featureMinVersions.TryGetValue(feature, out var version))
            {
                return version;
            }

            // Find the minimum version that supports this feature
            foreach (var kvp in VersionFeatures.OrderBy(x => x.Key))
            {
                if (kvp.Value.Contains(feature, StringComparer.OrdinalIgnoreCase))
                {
                    return kvp.Key;
                }
            }

            return RevitVersion.Unknown;
        }

        public async Task<CompatibilityResult> ValidateCompatibilityAsync()
        {
            var result = new CompatibilityResult();

            try
            {
                _logger.LogInformation("Starting compatibility validation");

                // Detect current version
                result.DetectedVersion = await DetectRevitVersionAsync();

                if (result.DetectedVersion.Version == RevitVersion.Unknown)
                {
                    result.IsCompatible = false;
                    result.Issues.Add(new CompatibilityIssue
                    {
                        Severity = CompatibilityIssueSeverity.Critical,
                        Feature = "VersionDetection",
                        Message = "Could not detect Revit version",
                        Recommendation = "Ensure Revit is properly installed and accessible"
                    });
                    return result;
                }

                // Check minimum version requirement
                if (result.DetectedVersion.Version < RevitVersion.Revit2022)
                {
                    result.IsCompatible = false;
                    result.Issues.Add(new CompatibilityIssue
                    {
                        Severity = CompatibilityIssueSeverity.Critical,
                        Feature = "MinimumVersion",
                        Message = $"Revit {result.DetectedVersion.Version} is not supported. Minimum version is Revit 2022",
                        Recommendation = "Upgrade to Revit 2022 or later"
                    });
                    return result;
                }

                // Validate features
                await ValidateFeaturesAsync(result);

                // Check .NET compatibility
                await ValidateDotNetCompatibilityAsync(result);

                // Check installation integrity
                await ValidateInstallationAsync(result);

                result.IsCompatible = !result.Issues.Any(i =>
                    i.Severity == CompatibilityIssueSeverity.Critical ||
                    i.Severity == CompatibilityIssueSeverity.Error);

                _logger.LogInformation("Compatibility validation completed. Compatible: {IsCompatible}", result.IsCompatible);

                return result;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during compatibility validation");
                result.IsCompatible = false;
                result.Issues.Add(new CompatibilityIssue
                {
                    Severity = CompatibilityIssueSeverity.Critical,
                    Feature = "ValidationProcess",
                    Message = $"Compatibility validation failed: {ex.Message}",
                    Recommendation = "Check system requirements and installation"
                });
                return result;
            }
        }

        public VersionConfiguration GetVersionConfiguration(RevitVersion version)
        {
            if (_versionConfigurations.TryGetValue(version, out var config))
            {
                return config;
            }

            _logger.LogWarning("No configuration found for Revit version: {Version}", version);
            return new VersionConfiguration { Version = version };
        }

        private async Task<RevitVersionInfo> TryDetectFromRegistryAsync()
        {
            try
            {
                var registryPaths = new[]
                {
                    @"SOFTWARE\Autodesk\Revit",
                    @"SOFTWARE\WOW6432Node\Autodesk\Revit"
                };

                foreach (var path in registryPaths)
                {
                    using var key = Registry.LocalMachine.OpenSubKey(path);
                    if (key == null) continue;

                    foreach (var subKeyName in key.GetSubKeyNames())
                    {
                        if (TryParseVersionFromKey(subKeyName, out var version, out var versionString))
                        {
                            using var versionKey = key.OpenSubKey(subKeyName);
                            if (versionKey == null) continue;

                            var installPath = versionKey.GetValue("InstallationPath") as string;
                            var productName = versionKey.GetValue("ProductName") as string;

                            return new RevitVersionInfo
                            {
                                Version = version,
                                VersionString = versionString,
                                ProductName = productName ?? $"Autodesk Revit {version}",
                                InstallationPath = installPath,
                                IsValidInstallation = !string.IsNullOrEmpty(installPath) && Directory.Exists(installPath)
                            };
                        }
                    }
                }

                return null;
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Registry detection failed");
                return null;
            }
        }

        private async Task<RevitVersionInfo> TryDetectFromApplicationAsync()
        {
            try
            {
                // Try to detect from loaded Revit assemblies
                var revitAssemblies = AppDomain.CurrentDomain.GetAssemblies()
                    .Where(a => a.FullName.Contains("RevitAPI") || a.FullName.Contains("Autodesk.Revit"))
                    .ToList();

                foreach (var assembly in revitAssemblies)
                {
                    var version = assembly.GetName().Version;
                    if (version != null && TryParseRevitVersion(version.Major.ToString(), out var revitVersion))
                    {
                        return new RevitVersionInfo
                        {
                            Version = revitVersion,
                            VersionString = version.ToString(),
                            ProductName = assembly.GetName().Name,
                            IsValidInstallation = true
                        };
                    }
                }

                return null;
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Application detection failed");
                return null;
            }
        }

        private async Task<RevitVersionInfo> TryDetectFromFileSystemAsync()
        {
            try
            {
                var commonPaths = new[]
                {
                    @"C:\Program Files\Autodesk",
                    @"C:\Program Files (x86)\Autodesk"
                };

                foreach (var basePath in commonPaths)
                {
                    if (!Directory.Exists(basePath)) continue;

                    var revitDirs = Directory.GetDirectories(basePath, "Revit*", SearchOption.TopDirectoryOnly);

                    foreach (var dir in revitDirs)
                    {
                        var dirName = Path.GetFileName(dir);
                        if (TryParseVersionFromPath(dirName, out var version, out var versionString))
                        {
                            var executablePath = Path.Combine(dir, "Revit.exe");
                            if (File.Exists(executablePath))
                            {
                                var fileInfo = new FileInfo(executablePath);
                                return new RevitVersionInfo
                                {
                                    Version = version,
                                    VersionString = versionString,
                                    InstallationPath = dir,
                                    ProductName = $"Autodesk Revit {version}",
                                    IsValidInstallation = true,
                                    AdditionalInfo = { ["ExecutablePath"] = executablePath }
                                };
                            }
                        }
                    }
                }

                return null;
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "File system detection failed");
                return null;
            }
        }

        private async Task<RevitVersionInfo> TryDetectFromEnvironmentAsync()
        {
            try
            {
                // Check environment variables
                var revitPath = Environment.GetEnvironmentVariable("REVIT_PATH");
                if (!string.IsNullOrEmpty(revitPath) && Directory.Exists(revitPath))
                {
                    // Try to determine version from path or executable
                    var executablePath = Path.Combine(revitPath, "Revit.exe");
                    if (File.Exists(executablePath))
                    {
                        var fileVersionInfo = System.Diagnostics.FileVersionInfo.GetVersionInfo(executablePath);
                        if (TryParseRevitVersion(fileVersionInfo.ProductMajorPart.ToString(), out var version))
                        {
                            return new RevitVersionInfo
                            {
                                Version = version,
                                VersionString = fileVersionInfo.ProductVersion ?? fileVersionInfo.FileVersion,
                                InstallationPath = revitPath,
                                ProductName = fileVersionInfo.ProductName,
                                IsValidInstallation = true
                            };
                        }
                    }
                }

                return null;
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Environment detection failed");
                return null;
            }
        }

        private bool TryParseVersionFromKey(string keyName, out RevitVersion version, out string versionString)
        {
            version = RevitVersion.Unknown;
            versionString = keyName;

            // Extract year from key name (e.g., "2025" from "Revit 2025")
            var yearMatch = System.Text.RegularExpressions.Regex.Match(keyName, @"(\d{4})");
            if (yearMatch.Success && int.TryParse(yearMatch.Groups[1].Value, out var year))
            {
                return TryParseRevitVersion(year.ToString(), out version);
            }

            return false;
        }

        private bool TryParseVersionFromPath(string pathName, out RevitVersion version, out string versionString)
        {
            version = RevitVersion.Unknown;
            versionString = pathName;

            // Extract year from path name (e.g., "2025" from "Revit 2025")
            var yearMatch = System.Text.RegularExpressions.Regex.Match(pathName, @"(\d{4})");
            if (yearMatch.Success && int.TryParse(yearMatch.Groups[1].Value, out var year))
            {
                return TryParseRevitVersion(year.ToString(), out version);
            }

            return false;
        }

        private bool TryParseRevitVersion(string versionString, out RevitVersion version)
        {
            version = RevitVersion.Unknown;

            if (int.TryParse(versionString, out var year))
            {
                version = year switch
                {
                    2022 => RevitVersion.Revit2022,
                    2023 => RevitVersion.Revit2023,
                    2024 => RevitVersion.Revit2024,
                    2025 => RevitVersion.Revit2025,
                    2026 => RevitVersion.Revit2026,
                    _ when year > 2026 => RevitVersion.Future,
                    _ => RevitVersion.Unknown
                };

                return version != RevitVersion.Unknown;
            }

            return false;
        }

        private async Task ValidateFeaturesAsync(CompatibilityResult result)
        {
            var supportedFeatures = GetSupportedFeatures(result.DetectedVersion.Version);

            foreach (var feature in supportedFeatures)
            {
                result.FeatureCompatibility[feature] = true;
            }

            // Check for missing features in older versions
            if (result.DetectedVersion.Version < RevitVersion.Revit2023)
            {
                result.Warnings.Add("Modern transaction API is not available in this version. Legacy API will be used.");
            }

            if (result.DetectedVersion.Version < RevitVersion.Revit2024)
            {
                result.Warnings.Add("Cloud model support is not available in this version.");
            }
        }

        private async Task ValidateDotNetCompatibilityAsync(CompatibilityResult result)
        {
            var config = GetVersionConfiguration(result.DetectedVersion.Version);

            // Check .NET Framework version
            var currentFramework = Environment.Version;
            _logger.LogDebug("Current .NET Framework version: {Version}", currentFramework);

            // Add framework compatibility check based on Revit version
            if (result.DetectedVersion.Version >= RevitVersion.Revit2025)
            {
                result.Recommendations.Add("Consider using .NET 8+ features when available");
            }
        }

        private async Task ValidateInstallationAsync(CompatibilityResult result)
        {
            if (string.IsNullOrEmpty(result.DetectedVersion.InstallationPath))
            {
                result.Warnings.Add("Installation path could not be determined");
                return;
            }

            if (!Directory.Exists(result.DetectedVersion.InstallationPath))
            {
                result.Issues.Add(new CompatibilityIssue
                {
                    Severity = CompatibilityIssueSeverity.Error,
                    Feature = "Installation",
                    Message = "Installation directory does not exist",
                    Recommendation = "Reinstall Revit or check installation path"
                });
            }
        }

        private Dictionary<RevitVersion, VersionConfiguration> InitializeVersionConfigurations()
        {
            return new Dictionary<RevitVersion, VersionConfiguration>
            {
                {
                    RevitVersion.Revit2022,
                    new VersionConfiguration
                    {
                        Version = RevitVersion.Revit2022,
                        DotNetVersion = "4.8",
                        RequiredAssemblies = new[] { "RevitAPI.dll", "RevitAPIUI.dll" },
                        DeprecatedMethods = new[] { "LegacyParameterAccess", "OldTransactionAPI" }
                    }
                },
                {
                    RevitVersion.Revit2023,
                    new VersionConfiguration
                    {
                        Version = RevitVersion.Revit2023,
                        DotNetVersion = "4.8",
                        RequiredAssemblies = new[] { "RevitAPI.dll", "RevitAPIUI.dll" },
                        DeprecatedMethods = new[] { "LegacyParameterAccess" }
                    }
                },
                {
                    RevitVersion.Revit2024,
                    new VersionConfiguration
                    {
                        Version = RevitVersion.Revit2024,
                        DotNetVersion = "4.8",
                        RequiredAssemblies = new[] { "RevitAPI.dll", "RevitAPIUI.dll" }
                    }
                },
                {
                    RevitVersion.Revit2025,
                    new VersionConfiguration
                    {
                        Version = RevitVersion.Revit2025,
                        DotNetVersion = "4.8",
                        RequiredAssemblies = new[] { "RevitAPI.dll", "RevitAPIUI.dll" }
                    }
                }
            };
        }

        private Dictionary<string, RevitVersion> InitializeFeatureMinVersions()
        {
            return new Dictionary<string, RevitVersion>
            {
                { "BasicAPI", RevitVersion.Revit2022 },
                { "GeometryAPI", RevitVersion.Revit2022 },
                { "ParameterAccess", RevitVersion.Revit2022 },
                { "TransactionManagement", RevitVersion.Revit2022 },
                { "ModernTransactions", RevitVersion.Revit2023 },
                { "EnhancedGeometry", RevitVersion.Revit2023 },
                { "CloudModelSupport", RevitVersion.Revit2024 },
                { "AdvancedSelection", RevitVersion.Revit2024 },
                { "AI_Integration", RevitVersion.Revit2025 },
                { "ModernUI", RevitVersion.Revit2025 },
                { "WebAPI_Support", RevitVersion.Revit2025 }
            };
        }
    }
}

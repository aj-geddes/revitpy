using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using System.ComponentModel.DataAnnotations;
using System.Net.NetworkInformation;
using System.Reflection;

namespace RevitPy.Host;

/// <summary>
/// Provides comprehensive validation of RevitPy configuration
/// </summary>
public class ConfigurationValidator : IConfigurationValidator
{
    private readonly ILogger<ConfigurationValidator> _logger;

    public ConfigurationValidator(ILogger<ConfigurationValidator> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Validates the complete RevitPy configuration
    /// </summary>
    /// <param name="configuration">Configuration to validate</param>
    /// <returns>Validation result</returns>
    public async Task<ConfigurationValidationResult> ValidateAsync(IConfiguration configuration)
    {
        var result = new ConfigurationValidationResult();
        var stopwatch = System.Diagnostics.Stopwatch.StartNew();

        _logger.LogInformation("Starting configuration validation...");

        try
        {
            // Parse RevitPy options
            var options = new RevitPyOptions();
            var section = configuration.GetSection(RevitPyOptions.SectionName);
            section.Bind(options);

            // Validate data annotations
            await ValidateDataAnnotationsAsync(options, result);

            // Validate Python configuration
            await ValidatePythonConfigurationAsync(options, result);

            // Validate server configuration
            await ValidateServerConfigurationAsync(options, result);

            // Validate paths and directories
            await ValidatePathsAsync(options, result);

            // Validate security configuration
            await ValidateSecurityConfigurationAsync(options, result);

            // Validate extension configuration
            await ValidateExtensionConfigurationAsync(options, result);

            // Validate resource limits
            await ValidateResourceLimitsAsync(options, result);

            // Validate environment dependencies
            await ValidateEnvironmentAsync(result);

            result.IsValid = !result.Errors.Any();
        }
        catch (Exception ex)
        {
            result.Errors.Add($"Configuration validation failed with exception: {ex.Message}");
            result.IsValid = false;
            _logger.LogError(ex, "Configuration validation failed");
        }

        stopwatch.Stop();
        result.ValidationTime = stopwatch.Elapsed;

        var level = result.IsValid ? LogLevel.Information : LogLevel.Error;
        _logger.Log(level, "Configuration validation completed in {Duration}ms. Valid: {IsValid}, Errors: {ErrorCount}, Warnings: {WarningCount}",
            result.ValidationTime.TotalMilliseconds,
            result.IsValid,
            result.Errors.Count,
            result.Warnings.Count);

        return result;
    }

    /// <summary>
    /// Validates only critical configuration required for startup
    /// </summary>
    /// <param name="configuration">Configuration to validate</param>
    /// <returns>True if critical configuration is valid</returns>
    public async Task<bool> ValidateCriticalAsync(IConfiguration configuration)
    {
        try
        {
            var options = new RevitPyOptions();
            var section = configuration.GetSection(RevitPyOptions.SectionName);
            section.Bind(options);

            // Check only critical settings
            var criticalChecks = new[]
            {
                !string.IsNullOrWhiteSpace(options.PythonVersion),
                options.MaxInterpreters > 0,
                options.PythonTimeout > 0,
                !options.EnableDebugServer || (options.DebugServerPort > 0 && options.DebugServerPort <= 65535)
            };

            return criticalChecks.All(check => check);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Critical configuration validation failed");
            return false;
        }
    }

    private async Task ValidateDataAnnotationsAsync(RevitPyOptions options, ConfigurationValidationResult result)
    {
        var context = new ValidationContext(options, null, null);
        var validationResults = new List<ValidationResult>();

        if (!Validator.TryValidateObjectRecursively(options, context, validationResults))
        {
            foreach (var validationResult in validationResults)
            {
                var memberNames = validationResult.MemberNames.Any() 
                    ? string.Join(", ", validationResult.MemberNames) 
                    : "Unknown";
                result.Errors.Add($"Validation error for {memberNames}: {validationResult.ErrorMessage}");
            }
        }

        await Task.CompletedTask;
    }

    private async Task ValidatePythonConfigurationAsync(RevitPyOptions options, ConfigurationValidationResult result)
    {
        // Validate Python version format
        if (!IsValidPythonVersion(options.PythonVersion))
        {
            result.Errors.Add($"Invalid Python version format: {options.PythonVersion}. Expected format: X.Y (e.g., 3.11)");
        }
        else
        {
            // Check for supported Python versions
            var supportedVersions = new[] { "3.8", "3.9", "3.10", "3.11", "3.12" };
            if (!supportedVersions.Contains(options.PythonVersion))
            {
                result.Warnings.Add($"Python version {options.PythonVersion} is not officially supported. Supported versions: {string.Join(", ", supportedVersions)}");
            }
        }

        // Validate Python path if provided
        if (!string.IsNullOrWhiteSpace(options.PythonPath))
        {
            if (!Directory.Exists(options.PythonPath))
            {
                result.Errors.Add($"Python path does not exist: {options.PythonPath}");
            }
            else
            {
                var pythonExecutable = Path.Combine(options.PythonPath, "python.exe");
                if (!File.Exists(pythonExecutable))
                {
                    pythonExecutable = Path.Combine(options.PythonPath, "Scripts", "python.exe");
                    if (!File.Exists(pythonExecutable))
                    {
                        result.Warnings.Add($"Python executable not found in specified path: {options.PythonPath}");
                    }
                }
            }
        }

        // Validate Python library path if provided
        if (!string.IsNullOrWhiteSpace(options.PythonLibPath) && !Directory.Exists(options.PythonLibPath))
        {
            result.Errors.Add($"Python library path does not exist: {options.PythonLibPath}");
        }

        // Validate additional Python paths
        foreach (var pythonPath in options.PythonPaths)
        {
            if (!Directory.Exists(pythonPath))
            {
                result.Warnings.Add($"Additional Python path does not exist: {pythonPath}");
            }
        }

        await Task.CompletedTask;
    }

    private async Task ValidateServerConfigurationAsync(RevitPyOptions options, ConfigurationValidationResult result)
    {
        // Validate debug server configuration
        if (options.EnableDebugServer)
        {
            // Check if port is available
            var isPortAvailable = await IsPortAvailableAsync(options.DebugServerPort);
            if (!isPortAvailable)
            {
                result.Warnings.Add($"Debug server port {options.DebugServerPort} appears to be in use");
            }

            // Validate port range
            if (options.DebugServerPort < 1024)
            {
                result.Warnings.Add($"Debug server port {options.DebugServerPort} is in the system-reserved range (0-1023). Consider using a port above 1024");
            }
        }

        await Task.CompletedTask;
    }

    private async Task ValidatePathsAsync(RevitPyOptions options, ConfigurationValidationResult result)
    {
        // Validate and create temp directory
        try
        {
            if (string.IsNullOrWhiteSpace(options.TempDirectory))
            {
                options.TempDirectory = Path.GetTempPath();
            }

            if (!Directory.Exists(options.TempDirectory))
            {
                Directory.CreateDirectory(options.TempDirectory);
                result.Warnings.Add($"Created temporary directory: {options.TempDirectory}");
            }

            // Test write access
            var testFile = Path.Combine(options.TempDirectory, $"revitpy_test_{Guid.NewGuid():N}.tmp");
            await File.WriteAllTextAsync(testFile, "test");
            File.Delete(testFile);
        }
        catch (Exception ex)
        {
            result.Errors.Add($"Cannot write to temporary directory {options.TempDirectory}: {ex.Message}");
        }

        // Validate and create log directory
        try
        {
            if (!Directory.Exists(options.LogDirectory))
            {
                Directory.CreateDirectory(options.LogDirectory);
                result.Warnings.Add($"Created log directory: {options.LogDirectory}");
            }

            // Test write access
            var testFile = Path.Combine(options.LogDirectory, $"revitpy_test_{Guid.NewGuid():N}.log");
            await File.WriteAllTextAsync(testFile, "test");
            File.Delete(testFile);
        }
        catch (Exception ex)
        {
            result.Errors.Add($"Cannot write to log directory {options.LogDirectory}: {ex.Message}");
        }
    }

    private async Task ValidateSecurityConfigurationAsync(RevitPyOptions options, ConfigurationValidationResult result)
    {
        // Validate sandbox configuration
        if (options.EnableSandbox)
        {
            // Check allowed file paths
            foreach (var allowedPath in options.AllowedFilePaths)
            {
                if (!Directory.Exists(allowedPath) && !File.Exists(allowedPath))
                {
                    result.Warnings.Add($"Allowed file path does not exist: {allowedPath}");
                }
            }

            // Validate blocked modules
            if (!options.BlockedModules.Any())
            {
                result.Warnings.Add("No modules are blocked in sandbox mode. Consider blocking potentially dangerous modules like 'os', 'subprocess', 'shutil'");
            }
        }
        else
        {
            result.Warnings.Add("Sandbox mode is disabled. This may pose security risks in production environments");
        }

        await Task.CompletedTask;
    }

    private async Task ValidateExtensionConfigurationAsync(RevitPyOptions options, ConfigurationValidationResult result)
    {
        // Validate extension search paths
        foreach (var searchPath in options.Extensions.SearchPaths)
        {
            if (!Directory.Exists(searchPath))
            {
                result.Warnings.Add($"Extension search path does not exist: {searchPath}");
            }
        }

        // Validate file patterns
        if (!options.Extensions.FilePatterns.Any())
        {
            result.Warnings.Add("No extension file patterns configured. Extensions may not be loaded");
        }

        // Check security settings for production
        if (options.Extensions.RequireSigned && !options.Extensions.TrustedPublishers.Any())
        {
            result.Warnings.Add("Signed extensions are required but no trusted publishers are configured");
        }

        await Task.CompletedTask;
    }

    private async Task ValidateResourceLimitsAsync(RevitPyOptions options, ConfigurationValidationResult result)
    {
        // Validate memory settings
        var availableMemoryMB = GC.GetTotalMemory(false) / 1024 / 1024;
        var systemMemoryGB = GetSystemMemoryGB();

        if (options.MaxMemoryUsageMB > systemMemoryGB * 1024 * 0.8) // More than 80% of system memory
        {
            result.Warnings.Add($"Maximum memory usage ({options.MaxMemoryUsageMB}MB) is more than 80% of available system memory ({systemMemoryGB}GB)");
        }

        if (options.MaxInterpreters > Environment.ProcessorCount * 2)
        {
            result.Warnings.Add($"Maximum interpreters ({options.MaxInterpreters}) exceeds 2x CPU cores ({Environment.ProcessorCount}). This may cause performance issues");
        }

        // Validate timeout settings
        if (options.PythonTimeout < 5000)
        {
            result.Warnings.Add($"Python timeout ({options.PythonTimeout}ms) is very short and may cause frequent timeouts");
        }

        await Task.CompletedTask;
    }

    private async Task ValidateEnvironmentAsync(ConfigurationValidationResult result)
    {
        // Check .NET version
        var runtimeVersion = Environment.Version;
        var requiredMajorVersion = 6;

        if (runtimeVersion.Major < requiredMajorVersion)
        {
            result.Errors.Add($".NET {requiredMajorVersion} or later is required. Current version: {runtimeVersion}");
        }

        // Check operating system
        if (!OperatingSystem.IsWindows())
        {
            result.Warnings.Add("RevitPy is primarily designed for Windows. Some features may not work on other platforms");
        }

        // Check available disk space
        var tempDrive = new DriveInfo(Path.GetTempPath());
        var availableSpaceGB = tempDrive.AvailableFreeSpace / 1024 / 1024 / 1024;

        if (availableSpaceGB < 1)
        {
            result.Errors.Add($"Insufficient disk space. Available: {availableSpaceGB}GB, Required: 1GB minimum");
        }
        else if (availableSpaceGB < 5)
        {
            result.Warnings.Add($"Low disk space. Available: {availableSpaceGB}GB, Recommended: 5GB or more");
        }

        await Task.CompletedTask;
    }

    private static bool IsValidPythonVersion(string version)
    {
        if (string.IsNullOrWhiteSpace(version))
            return false;

        var parts = version.Split('.');
        return parts.Length == 2 && parts.All(part => int.TryParse(part, out _));
    }

    private static async Task<bool> IsPortAvailableAsync(int port)
    {
        try
        {
            var ipGlobalProperties = IPGlobalProperties.GetIPGlobalProperties();
            var activeTcpListeners = ipGlobalProperties.GetActiveTcpListeners();
            return !activeTcpListeners.Any(endpoint => endpoint.Port == port);
        }
        catch
        {
            return false;
        }
    }

    private static double GetSystemMemoryGB()
    {
        try
        {
            using var searcher = new System.Management.ManagementObjectSearcher("SELECT TotalPhysicalMemory FROM Win32_ComputerSystem");
            foreach (System.Management.ManagementObject obj in searcher.Get())
            {
                var totalMemory = Convert.ToDouble(obj["TotalPhysicalMemory"]);
                return totalMemory / 1024 / 1024 / 1024;
            }
        }
        catch
        {
            // Fallback estimation
            return 8.0; // Assume 8GB as a reasonable default
        }

        return 8.0;
    }
}

/// <summary>
/// Interface for configuration validation
/// </summary>
public interface IConfigurationValidator
{
    /// <summary>
    /// Validates the complete configuration
    /// </summary>
    /// <param name="configuration">Configuration to validate</param>
    /// <returns>Validation result</returns>
    Task<ConfigurationValidationResult> ValidateAsync(IConfiguration configuration);

    /// <summary>
    /// Validates only critical configuration required for startup
    /// </summary>
    /// <param name="configuration">Configuration to validate</param>
    /// <returns>True if critical configuration is valid</returns>
    Task<bool> ValidateCriticalAsync(IConfiguration configuration);
}

/// <summary>
/// Result of configuration validation
/// </summary>
public class ConfigurationValidationResult
{
    /// <summary>
    /// Gets or sets whether the configuration is valid
    /// </summary>
    public bool IsValid { get; set; }

    /// <summary>
    /// Gets validation errors
    /// </summary>
    public List<string> Errors { get; } = new();

    /// <summary>
    /// Gets validation warnings
    /// </summary>
    public List<string> Warnings { get; } = new();

    /// <summary>
    /// Gets validation time
    /// </summary>
    public TimeSpan ValidationTime { get; set; }

    /// <summary>
    /// Gets configuration metadata discovered during validation
    /// </summary>
    public Dictionary<string, object> Metadata { get; } = new();
}

/// <summary>
/// Extensions for validator
/// </summary>
public static class ValidatorExtensions
{
    /// <summary>
    /// Validates an object and its nested objects recursively
    /// </summary>
    /// <param name="obj">Object to validate</param>
    /// <param name="context">Validation context</param>
    /// <param name="results">Validation results</param>
    /// <returns>True if valid</returns>
    public static bool TryValidateObjectRecursively(object obj, ValidationContext context, ICollection<ValidationResult> results)
    {
        var isValid = Validator.TryValidateObject(obj, context, results, true);

        var properties = context.ObjectType.GetProperties();
        foreach (var property in properties)
        {
            if (property.CanRead)
            {
                var value = property.GetValue(context.ObjectInstance);
                if (value != null)
                {
                    var nestedContext = new ValidationContext(value, null, null);
                    var nestedResults = new List<ValidationResult>();
                    
                    if (!Validator.TryValidateObject(value, nestedContext, nestedResults, true))
                    {
                        foreach (var nestedResult in nestedResults)
                        {
                            results.Add(new ValidationResult(
                                $"{property.Name}.{nestedResult.ErrorMessage}",
                                nestedResult.MemberNames.Select(m => $"{property.Name}.{m}")
                            ));
                        }
                        isValid = false;
                    }
                }
            }
        }

        return isValid;
    }
}
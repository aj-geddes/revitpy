using System.ComponentModel.DataAnnotations;

namespace RevitPy.Core.Configuration;

/// <summary>
/// Configuration options for RevitPy
/// </summary>
public class RevitPyOptions
{
    /// <summary>
    /// Configuration section name
    /// </summary>
    public const string SectionName = "RevitPy";

    /// <summary>
    /// Path to the Python installation
    /// </summary>
    [Required]
    public string PythonPath { get; set; } = string.Empty;

    /// <summary>
    /// Python version (e.g., "3.11")
    /// </summary>
    [Required]
    public string PythonVersion { get; set; } = "3.11";

    /// <summary>
    /// Path to the Python standard library
    /// </summary>
    public string? PythonLibPath { get; set; }

    /// <summary>
    /// Additional Python paths to add to sys.path
    /// </summary>
    public List<string> PythonPaths { get; set; } = new();

    /// <summary>
    /// Maximum number of Python interpreters to maintain in pool
    /// </summary>
    [Range(1, 50)]
    public int MaxInterpreters { get; set; } = 5;

    /// <summary>
    /// Timeout for Python operations in milliseconds
    /// </summary>
    [Range(1000, 300000)]
    public int PythonTimeout { get; set; } = 30000;

    /// <summary>
    /// Enable hot-reload functionality
    /// </summary>
    public bool EnableHotReload { get; set; } = true;

    /// <summary>
    /// Port for the WebSocket debug server
    /// </summary>
    [Range(1024, 65535)]
    public int DebugServerPort { get; set; } = 8080;

    /// <summary>
    /// Enable debug server
    /// </summary>
    public bool EnableDebugServer { get; set; } = true;

    /// <summary>
    /// Directory for storing temporary files
    /// </summary>
    public string TempDirectory { get; set; } = Path.GetTempPath();

    /// <summary>
    /// Directory for storing log files
    /// </summary>
    public string LogDirectory { get; set; } = Path.Combine(Path.GetTempPath(), "RevitPy", "Logs");

    /// <summary>
    /// Maximum log file size in MB
    /// </summary>
    [Range(1, 1000)]
    public int MaxLogFileSizeMB { get; set; } = 50;

    /// <summary>
    /// Number of log files to retain
    /// </summary>
    [Range(1, 100)]
    public int MaxLogFiles { get; set; } = 10;

    /// <summary>
    /// Enable memory profiling
    /// </summary>
    public bool EnableMemoryProfiling { get; set; } = false;

    /// <summary>
    /// Memory check interval in milliseconds
    /// </summary>
    [Range(1000, 60000)]
    public int MemoryCheckInterval { get; set; } = 5000;

    /// <summary>
    /// Maximum memory usage in MB before triggering cleanup
    /// </summary>
    [Range(100, 8192)]
    public int MaxMemoryUsageMB { get; set; } = 1024;

    /// <summary>
    /// Enable security sandbox
    /// </summary>
    public bool EnableSandbox { get; set; } = true;

    /// <summary>
    /// Allowed file access patterns for sandboxed execution
    /// </summary>
    public List<string> AllowedFilePaths { get; set; } = new();

    /// <summary>
    /// Blocked Python modules for sandboxed execution
    /// </summary>
    public List<string> BlockedModules { get; set; } = new()
    {
        "os",
        "subprocess",
        "shutil",
        "tempfile"
    };

    /// <summary>
    /// Extension loading configuration
    /// </summary>
    public ExtensionOptions Extensions { get; set; } = new();
}

/// <summary>
/// Configuration options for extension loading
/// </summary>
public class ExtensionOptions
{
    /// <summary>
    /// Directories to search for extensions
    /// </summary>
    public List<string> SearchPaths { get; set; } = new();

    /// <summary>
    /// Extension file patterns to load
    /// </summary>
    public List<string> FilePatterns { get; set; } = new()
    {
        "*.py",
        "*.rpx"
    };

    /// <summary>
    /// Enable automatic extension discovery
    /// </summary>
    public bool EnableAutoDiscovery { get; set; } = true;

    /// <summary>
    /// Enable extension validation
    /// </summary>
    public bool EnableValidation { get; set; } = true;

    /// <summary>
    /// Require signed extensions
    /// </summary>
    public bool RequireSigned { get; set; } = false;

    /// <summary>
    /// Trusted extension publishers
    /// </summary>
    public List<string> TrustedPublishers { get; set; } = new();

    /// <summary>
    /// Extension loading timeout in milliseconds
    /// </summary>
    [Range(1000, 60000)]
    public int LoadTimeout { get; set; } = 10000;
}
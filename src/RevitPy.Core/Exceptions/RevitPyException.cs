namespace RevitPy.Core.Exceptions;

/// <summary>
/// Base exception for all RevitPy-related errors
/// </summary>
public class RevitPyException : Exception
{
    /// <summary>
    /// Gets or sets the error code
    /// </summary>
    public string? ErrorCode { get; set; }

    /// <summary>
    /// Gets or sets additional error details
    /// </summary>
    public Dictionary<string, object>? Details { get; set; }

    public RevitPyException() { }

    public RevitPyException(string message) : base(message) { }

    public RevitPyException(string message, Exception innerException) : base(message, innerException) { }

    public RevitPyException(string message, string errorCode) : base(message)
    {
        ErrorCode = errorCode;
    }

    public RevitPyException(string message, string errorCode, Dictionary<string, object> details) : base(message)
    {
        ErrorCode = errorCode;
        Details = details;
    }
}

/// <summary>
/// Exception thrown when Python interpreter initialization fails
/// </summary>
public class PythonInitializationException : RevitPyException
{
    public PythonInitializationException(string message) : base(message, "PYTHON_INIT_FAILED") { }

    public PythonInitializationException(string message, Exception innerException)
        : base(message, innerException)
    {
        ErrorCode = "PYTHON_INIT_FAILED";
    }
}

/// <summary>
/// Exception thrown when Python execution fails
/// </summary>
public class PythonExecutionException : RevitPyException
{
    /// <summary>
    /// Gets the Python stack trace
    /// </summary>
    public string? PythonStackTrace { get; set; }

    /// <summary>
    /// Gets the Python error type
    /// </summary>
    public string? PythonErrorType { get; set; }

    public PythonExecutionException(string message) : base(message, "PYTHON_EXECUTION_FAILED") { }

    public PythonExecutionException(string message, string pythonErrorType, string pythonStackTrace)
        : base(message, "PYTHON_EXECUTION_FAILED")
    {
        PythonErrorType = pythonErrorType;
        PythonStackTrace = pythonStackTrace;
    }

    public PythonExecutionException(string message, Exception innerException)
        : base(message, innerException)
    {
        ErrorCode = "PYTHON_EXECUTION_FAILED";
    }
}

/// <summary>
/// Exception thrown when Revit API operations fail
/// </summary>
public class RevitApiException : RevitPyException
{
    /// <summary>
    /// Gets the Revit error message
    /// </summary>
    public string? RevitErrorMessage { get; set; }

    /// <summary>
    /// Gets the Revit error severity
    /// </summary>
    public string? RevitErrorSeverity { get; set; }

    public RevitApiException(string message) : base(message, "REVIT_API_FAILED") { }

    public RevitApiException(string message, string revitErrorMessage, string revitErrorSeverity)
        : base(message, "REVIT_API_FAILED")
    {
        RevitErrorMessage = revitErrorMessage;
        RevitErrorSeverity = revitErrorSeverity;
    }

    public RevitApiException(string message, Exception innerException)
        : base(message, innerException)
    {
        ErrorCode = "REVIT_API_FAILED";
    }
}

/// <summary>
/// Exception thrown when extension loading fails
/// </summary>
public class ExtensionLoadException : RevitPyException
{
    /// <summary>
    /// Gets the extension path
    /// </summary>
    public string? ExtensionPath { get; set; }

    /// <summary>
    /// Gets the extension name
    /// </summary>
    public string? ExtensionName { get; set; }

    public ExtensionLoadException(string message) : base(message, "EXTENSION_LOAD_FAILED") { }

    public ExtensionLoadException(string message, string extensionPath, string extensionName)
        : base(message, "EXTENSION_LOAD_FAILED")
    {
        ExtensionPath = extensionPath;
        ExtensionName = extensionName;
    }

    public ExtensionLoadException(string message, Exception innerException)
        : base(message, innerException)
    {
        ErrorCode = "EXTENSION_LOAD_FAILED";
    }
}

/// <summary>
/// Exception thrown when configuration validation fails
/// </summary>
public class ConfigurationException : RevitPyException
{
    /// <summary>
    /// Gets the configuration section that failed validation
    /// </summary>
    public string? ConfigurationSection { get; set; }

    public ConfigurationException(string message) : base(message, "CONFIGURATION_INVALID") { }

    public ConfigurationException(string message, string configurationSection)
        : base(message, "CONFIGURATION_INVALID")
    {
        ConfigurationSection = configurationSection;
    }

    public ConfigurationException(string message, Exception innerException)
        : base(message, innerException)
    {
        ErrorCode = "CONFIGURATION_INVALID";
    }
}

/// <summary>
/// Exception thrown when security validation fails
/// </summary>
public class SecurityException : RevitPyException
{
    /// <summary>
    /// Gets the security violation type
    /// </summary>
    public string? ViolationType { get; set; }

    /// <summary>
    /// Gets the resource that was accessed
    /// </summary>
    public string? Resource { get; set; }

    public SecurityException(string message) : base(message, "SECURITY_VIOLATION") { }

    public SecurityException(string message, string violationType, string resource)
        : base(message, "SECURITY_VIOLATION")
    {
        ViolationType = violationType;
        Resource = resource;
    }

    public SecurityException(string message, Exception innerException)
        : base(message, innerException)
    {
        ErrorCode = "SECURITY_VIOLATION";
    }
}

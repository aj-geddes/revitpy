using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Python.Runtime;
using RevitPy.Core.Configuration;
using RevitPy.Core.Exceptions;
using System.Diagnostics;
using System.Text;

namespace RevitPy.Runtime;

/// <summary>
/// Implementation of IPythonInterpreter using Python.Runtime
/// </summary>
public class PythonInterpreter : IPythonInterpreter
{
    private readonly ILogger<PythonInterpreter> _logger;
    private readonly RevitPyOptions _options;
    private readonly string _id;
    private readonly object _lock = new();
    private readonly StringBuilder _stdoutBuffer = new();
    private readonly StringBuilder _stderrBuffer = new();

    private IntPtr _threadState;
    private bool _isInitialized;
    private bool _isBusy;
    private bool _isDisposed;
    private DateTime _lastActivity;

    public string Id => _id;
    public bool IsInitialized => _isInitialized;
    public bool IsBusy => _isBusy;
    public DateTime LastActivity => _lastActivity;

    public PythonInterpreter(ILogger<PythonInterpreter> logger, IOptions<RevitPyOptions> options)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        _id = Guid.NewGuid().ToString("N")[..8];
        _lastActivity = DateTime.UtcNow;
    }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_isInitialized)
            return;

        lock (_lock)
        {
            if (_isInitialized)
                return;

            try
            {
                _logger.LogInformation("Initializing Python interpreter {InterpreterId}", _id);

                // Initialize Python engine if not already done
                if (!PythonEngine.IsInitialized)
                {
                    InitializePythonEngine();
                }

                // Create a new thread state for this interpreter
                using (Py.GIL())
                {
                    _threadState = PythonEngine.BeginAllowThreads();
                }

                // Set up standard streams redirection
                SetupStreamRedirection();

                // Add configured Python paths
                foreach (var path in _options.PythonPaths)
                {
                    AddPathInternal(path);
                }

                _isInitialized = true;
                _lastActivity = DateTime.UtcNow;

                _logger.LogInformation("Python interpreter {InterpreterId} initialized successfully", _id);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to initialize Python interpreter {InterpreterId}", _id);
                throw new PythonInitializationException($"Failed to initialize Python interpreter {_id}", ex);
            }
        }

        await Task.CompletedTask;
    }

    public async Task<PythonExecutionResult> ExecuteAsync(
        string code,
        Dictionary<string, object>? globals = null,
        Dictionary<string, object>? locals = null,
        CancellationToken cancellationToken = default)
    {
        if (!_isInitialized)
            throw new InvalidOperationException("Interpreter is not initialized");

        if (string.IsNullOrWhiteSpace(code))
            throw new ArgumentException("Code cannot be null or whitespace", nameof(code));

        var result = new PythonExecutionResult();
        var stopwatch = Stopwatch.StartNew();

        lock (_lock)
        {
            if (_isBusy)
                throw new InvalidOperationException("Interpreter is busy");

            _isBusy = true;
            _lastActivity = DateTime.UtcNow;
        }

        try
        {
            using (Py.GIL())
            {
                PythonEngine.EndAllowThreads(_threadState);

                try
                {
                    // Clear output buffers
                    _stdoutBuffer.Clear();
                    _stderrBuffer.Clear();

                    // Set up execution context
                    using var scope = Py.CreateScope();

                    // Add global variables if provided
                    if (globals != null)
                    {
                        foreach (var kvp in globals)
                        {
                            scope.Set(kvp.Key, kvp.Value.ToPython());
                        }
                    }

                    // Add local variables if provided
                    if (locals != null)
                    {
                        foreach (var kvp in locals)
                        {
                            scope.Set(kvp.Key, kvp.Value.ToPython());
                        }
                    }

                    // Execute the code
                    var pyResult = scope.Exec(code);

                    // Capture result if any
                    if (pyResult != null && !pyResult.IsNone())
                    {
                        result.ReturnValue = pyResult.AsManagedObject(typeof(object));
                    }

                    result.Success = true;
                    result.StandardOutput = _stdoutBuffer.ToString();
                    result.StandardError = _stderrBuffer.ToString();
                }
                catch (PythonException pyEx)
                {
                    result.Success = false;
                    result.Exception = new PythonExecutionException(
                        pyEx.Message, 
                        pyEx.Type?.Name ?? "Unknown", 
                        pyEx.StackTrace ?? string.Empty);
                    result.PythonStackTrace = pyEx.StackTrace;
                    result.StandardError = _stderrBuffer.ToString();

                    _logger.LogWarning("Python execution failed in interpreter {InterpreterId}: {Error}", 
                        _id, pyEx.Message);
                }
                finally
                {
                    _threadState = PythonEngine.BeginAllowThreads();
                }
            }
        }
        catch (Exception ex)
        {
            result.Success = false;
            result.Exception = ex;
            _logger.LogError(ex, "Unexpected error during Python execution in interpreter {InterpreterId}", _id);
        }
        finally
        {
            stopwatch.Stop();
            result.ExecutionTime = stopwatch.Elapsed;

            lock (_lock)
            {
                _isBusy = false;
                _lastActivity = DateTime.UtcNow;
            }
        }

        return result;
    }

    public async Task<T?> EvaluateAsync<T>(
        string expression,
        Dictionary<string, object>? globals = null,
        Dictionary<string, object>? locals = null,
        CancellationToken cancellationToken = default)
    {
        if (!_isInitialized)
            throw new InvalidOperationException("Interpreter is not initialized");

        if (string.IsNullOrWhiteSpace(expression))
            throw new ArgumentException("Expression cannot be null or whitespace", nameof(expression));

        lock (_lock)
        {
            if (_isBusy)
                throw new InvalidOperationException("Interpreter is busy");

            _isBusy = true;
            _lastActivity = DateTime.UtcNow;
        }

        try
        {
            using (Py.GIL())
            {
                PythonEngine.EndAllowThreads(_threadState);

                try
                {
                    using var scope = Py.CreateScope();

                    // Add global variables if provided
                    if (globals != null)
                    {
                        foreach (var kvp in globals)
                        {
                            scope.Set(kvp.Key, kvp.Value.ToPython());
                        }
                    }

                    // Add local variables if provided
                    if (locals != null)
                    {
                        foreach (var kvp in locals)
                        {
                            scope.Set(kvp.Key, kvp.Value.ToPython());
                        }
                    }

                    // Evaluate the expression
                    using var pyResult = scope.Eval(expression);
                    
                    if (pyResult.IsNone())
                        return default(T);

                    return pyResult.AsManagedObject(typeof(T)) is T result ? result : default(T);
                }
                finally
                {
                    _threadState = PythonEngine.BeginAllowThreads();
                }
            }
        }
        catch (PythonException pyEx)
        {
            _logger.LogWarning("Python evaluation failed in interpreter {InterpreterId}: {Error}", 
                _id, pyEx.Message);
            throw new PythonExecutionException(pyEx.Message, pyEx.Type?.Name ?? "Unknown", 
                pyEx.StackTrace ?? string.Empty);
        }
        finally
        {
            lock (_lock)
            {
                _isBusy = false;
                _lastActivity = DateTime.UtcNow;
            }
        }
    }

    public async Task ImportModuleAsync(string moduleName, string? alias = null, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(moduleName))
            throw new ArgumentException("Module name cannot be null or whitespace", nameof(moduleName));

        var importCode = alias != null ? $"import {moduleName} as {alias}" : $"import {moduleName}";
        var result = await ExecuteAsync(importCode, cancellationToken: cancellationToken);

        if (!result.Success)
        {
            throw result.Exception ?? new PythonExecutionException($"Failed to import module {moduleName}");
        }
    }

    public async Task AddPathAsync(string path, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new ArgumentException("Path cannot be null or whitespace", nameof(path));

        AddPathInternal(path);
        await Task.CompletedTask;
    }

    public async Task SetVariableAsync(string name, object? value, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(name))
            throw new ArgumentException("Variable name cannot be null or whitespace", nameof(name));

        if (!_isInitialized)
            throw new InvalidOperationException("Interpreter is not initialized");

        lock (_lock)
        {
            if (_isBusy)
                throw new InvalidOperationException("Interpreter is busy");

            _isBusy = true;
            _lastActivity = DateTime.UtcNow;
        }

        try
        {
            using (Py.GIL())
            {
                PythonEngine.EndAllowThreads(_threadState);

                try
                {
                    using var scope = Py.CreateScope();
                    scope.Set(name, value?.ToPython() ?? new PyObject());
                }
                finally
                {
                    _threadState = PythonEngine.BeginAllowThreads();
                }
            }
        }
        finally
        {
            lock (_lock)
            {
                _isBusy = false;
                _lastActivity = DateTime.UtcNow;
            }
        }

        await Task.CompletedTask;
    }

    public async Task<T?> GetVariableAsync<T>(string name, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(name))
            throw new ArgumentException("Variable name cannot be null or whitespace", nameof(name));

        return await EvaluateAsync<T>(name, cancellationToken: cancellationToken);
    }

    public async Task ResetAsync(CancellationToken cancellationToken = default)
    {
        if (!_isInitialized)
            return;

        lock (_lock)
        {
            if (_isBusy)
                throw new InvalidOperationException("Cannot reset interpreter while it's busy");

            _isBusy = true;
        }

        try
        {
            _logger.LogInformation("Resetting Python interpreter {InterpreterId}", _id);

            using (Py.GIL())
            {
                PythonEngine.EndAllowThreads(_threadState);

                try
                {
                    // Clear all variables and modules
                    using var scope = Py.CreateScope();
                    scope.Exec("import sys");
                    scope.Exec("for module in list(sys.modules.keys()): del sys.modules[module]");
                    scope.Exec("import gc; gc.collect()");
                }
                finally
                {
                    _threadState = PythonEngine.BeginAllowThreads();
                }
            }

            // Re-add configured Python paths
            foreach (var path in _options.PythonPaths)
            {
                AddPathInternal(path);
            }

            _lastActivity = DateTime.UtcNow;
            _logger.LogInformation("Python interpreter {InterpreterId} reset successfully", _id);
        }
        finally
        {
            lock (_lock)
            {
                _isBusy = false;
            }
        }

        await Task.CompletedTask;
    }

    public PythonMemoryInfo GetMemoryInfo()
    {
        var memoryInfo = new PythonMemoryInfo();

        if (!_isInitialized)
            return memoryInfo;

        try
        {
            using (Py.GIL())
            {
                PythonEngine.EndAllowThreads(_threadState);

                try
                {
                    using var scope = Py.CreateScope();
                    
                    // Get memory information using Python's gc module
                    scope.Exec("import gc, sys");
                    
                    var objCount = scope.Eval("len(gc.get_objects())");
                    memoryInfo.ObjectCount = objCount.AsManagedObject(typeof(long)) as long? ?? 0;

                    var refCount = scope.Eval("len(gc.get_referrers())") ;
                    memoryInfo.ActiveReferences = refCount.AsManagedObject(typeof(long)) as long? ?? 0;

                    // Get GC stats
                    scope.Exec("gc_stats = gc.get_stats()");
                    var gcStats = scope.Get("gc_stats");
                    
                    if (gcStats != null)
                    {
                        using var pyList = gcStats.AsPyList();
                        for (int i = 0; i < pyList.Length(); i++)
                        {
                            using var item = pyList[i];
                            if (item.HasAttr("collections"))
                            {
                                var collections = item.GetAttr("collections");
                                memoryInfo.GcCounts[i] = collections.AsManagedObject(typeof(long)) as long? ?? 0;
                            }
                        }
                    }
                }
                finally
                {
                    _threadState = PythonEngine.BeginAllowThreads();
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning("Failed to get memory info for interpreter {InterpreterId}: {Error}", 
                _id, ex.Message);
        }

        return memoryInfo;
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        lock (_lock)
        {
            if (_isDisposed)
                return;

            _logger.LogInformation("Disposing Python interpreter {InterpreterId}", _id);

            try
            {
                if (_isInitialized && _threadState != IntPtr.Zero)
                {
                    using (Py.GIL())
                    {
                        PythonEngine.EndAllowThreads(_threadState);
                        // Thread state cleanup is handled by PythonEngine
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogWarning("Error disposing interpreter {InterpreterId}: {Error}", _id, ex.Message);
            }
            finally
            {
                _isDisposed = true;
                _isInitialized = false;
            }
        }
    }

    private void InitializePythonEngine()
    {
        if (!string.IsNullOrWhiteSpace(_options.PythonPath))
        {
            Environment.SetEnvironmentVariable("PYTHONHOME", _options.PythonPath);
        }

        if (!string.IsNullOrWhiteSpace(_options.PythonLibPath))
        {
            Environment.SetEnvironmentVariable("PYTHONPATH", _options.PythonLibPath);
        }

        PythonEngine.Initialize();
        PythonEngine.BeginAllowThreads();
    }

    private void SetupStreamRedirection()
    {
        // This is a simplified version - in a full implementation,
        // you would set up proper stdout/stderr redirection
        // using Python's sys module and custom stream classes
    }

    private void AddPathInternal(string path)
    {
        if (!_isInitialized || string.IsNullOrWhiteSpace(path))
            return;

        try
        {
            using (Py.GIL())
            {
                PythonEngine.EndAllowThreads(_threadState);

                try
                {
                    using var scope = Py.CreateScope();
                    scope.Exec($"import sys; sys.path.insert(0, r'{path}')");
                }
                finally
                {
                    _threadState = PythonEngine.BeginAllowThreads();
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning("Failed to add path {Path} to interpreter {InterpreterId}: {Error}", 
                path, _id, ex.Message);
        }
    }
}
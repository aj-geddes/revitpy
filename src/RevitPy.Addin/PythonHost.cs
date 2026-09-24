using System;
using System.Diagnostics;
using System.IO;
using Autodesk.Revit.UI;
using Python.Runtime;

namespace RevitPy.Addin;

/// <summary>
/// Owns the embedded CPython runtime. Python is initialized lazily on first use (or at
/// startup when configured) and scripts run on Revit's main thread with <c>__revit__</c>
/// bound to the <see cref="UIApplication"/>.
/// </summary>
public static class PythonHost
{
    private static readonly object InitLock = new object();
    private static IntPtr _mainThreadState = IntPtr.Zero;

    public static bool IsInitialized { get; private set; }

    public static string? PythonVersion { get; private set; }

    public static void Initialize(AddinSettings settings, RevitDispatcher dispatcher)
    {
        lock (InitLock)
        {
            if (IsInitialized)
            {
                return;
            }

            var dll = settings.ResolvePythonDll();
            if (dll == null)
            {
                throw new InvalidOperationException(
                    "No Python 3.11-3.14 (x64) installation was found. Set 'python_dll' in "
                    + settings.SettingsPath
                    + " or the REVITPY_PYTHON_DLL environment variable to the full path of python3XX.dll.");
            }

            Runtime.PythonDLL = dll;
            if (!string.IsNullOrEmpty(settings.PythonHome))
            {
                PythonEngine.PythonHome = settings.PythonHome!;
            }

            // Initialize() leaves the GIL held by this (Revit's main) thread.
            PythonEngine.Initialize();

            using (var scope = Py.CreateScope())
            {
                scope.Set("_revitpy_paths", settings.PythonPaths.ToArray());
                scope.Set("_revitpy_dispatcher", dispatcher.ToPython());
                scope.Exec(
                    "import builtins, sys\n"
                    + "for _p in _revitpy_paths:\n"
                    + "    _p = str(_p)\n"
                    + "    if _p not in sys.path:\n"
                    + "        sys.path.append(_p)\n"
                    + "builtins.__revitpy_dispatcher__ = _revitpy_dispatcher\n"
                    + "_revitpy_version = sys.version.split()[0]\n");
                PythonVersion = scope.Get("_revitpy_version").ToString();
            }

            // Release the GIL so Python background threads (e.g. the MCP server's event
            // loop) can run while Revit is idle. Later calls re-acquire it via Py.GIL().
            _mainThreadState = PythonEngine.BeginAllowThreads();
            IsInitialized = true;
        }

        foreach (var script in settings.StartupScripts)
        {
            try
            {
                var result = RunFile(script, null);
                if (!result.Success)
                {
                    Trace.TraceError("RevitPy startup script '{0}' failed:\n{1}", script, result.Error);
                }
            }
            catch (Exception ex)
            {
                Trace.TraceError("RevitPy startup script '{0}' failed: {1}", script, ex);
            }
        }
    }

    public static ScriptResult RunFile(string path, UIApplication? uiApplication)
    {
        return RunCode(File.ReadAllText(path), path, uiApplication);
    }

    /// <summary>
    /// Executes <paramref name="code"/> as <c>__main__</c>, capturing stdout/stderr.
    /// Must be called on Revit's main thread when <paramref name="uiApplication"/> is given.
    /// </summary>
    public static ScriptResult RunCode(string code, string fileName, UIApplication? uiApplication)
    {
        if (!IsInitialized)
        {
            throw new InvalidOperationException("Python has not been initialized.");
        }

        using (Py.GIL())
        using (var scope = Py.CreateScope())
        {
            scope.Set("__name__", "__main__");
            scope.Set("__file__", fileName);
            if (uiApplication != null)
            {
                scope.Set("__revit__", uiApplication.ToPython());
            }

            scope.Exec(
                "import io as _io, sys as _sys\n"
                + "__revitpy_out__ = _io.StringIO()\n"
                + "_revitpy_saved = (_sys.stdout, _sys.stderr)\n"
                + "_sys.stdout = _sys.stderr = __revitpy_out__\n");

            string? error = null;
            try
            {
                scope.Exec(code);
            }
            catch (PythonException ex)
            {
                error = ex.Format();
            }
            finally
            {
                scope.Exec("_sys.stdout, _sys.stderr = _revitpy_saved\n");
            }

            var output = scope.Get("__revitpy_out__").InvokeMethod("getvalue").ToString() ?? string.Empty;
            return error == null ? ScriptResult.Ok(output) : ScriptResult.Failure(output, error);
        }
    }

    public static void Shutdown()
    {
        lock (InitLock)
        {
            if (!IsInitialized)
            {
                return;
            }

            try
            {
                PythonEngine.EndAllowThreads(_mainThreadState);

                // Stop background Python work (the MCP server thread) before the
                // interpreter is finalized underneath it.
                using (var scope = Py.CreateScope())
                {
                    scope.Exec(
                        "import sys\n"
                        + "_host = sys.modules.get('revitpy.revit.host')\n"
                        + "if _host is not None:\n"
                        + "    _host.stop_mcp_server(timeout=2.0)\n");
                }

                PythonEngine.Shutdown();
            }
            catch (Exception ex)
            {
                // Revit is exiting; a failed interpreter teardown must not block that.
                Trace.TraceError("RevitPy Python shutdown failed: {0}", ex);
            }
            finally
            {
                IsInitialized = false;
                PythonVersion = null;
                _mainThreadState = IntPtr.Zero;
            }
        }
    }
}

/// <summary>Outcome of running Python code.</summary>
public sealed class ScriptResult
{
    private ScriptResult(bool success, string output, string? error)
    {
        Success = success;
        Output = output;
        Error = error;
    }

    public bool Success { get; }

    public string Output { get; }

    public string? Error { get; }

    public static ScriptResult Ok(string output) => new ScriptResult(true, output, null);

    public static ScriptResult Failure(string output, string error) => new ScriptResult(false, output, error);
}

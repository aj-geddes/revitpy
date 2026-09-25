using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace RevitPy.Addin;

/// <summary>
/// Add-in settings read from <c>%APPDATA%\RevitPy\settings.ini</c> and overridden by
/// <c>REVITPY_PYTHON_DLL</c>, <c>REVITPY_PYTHON_HOME</c> and <c>REVITPY_PYTHON_PATH</c>.
/// </summary>
/// <example>
/// <code>
/// # settings.ini
/// python_dll = C:\Python312\python312.dll
/// python_path = C:\projects\my-venv\Lib\site-packages
/// startup_script = %USERPROFILE%\revitpy\startup.py
/// initialize_on_startup = false
/// start_live_server = false
/// </code>
/// </example>
public sealed class AddinSettings
{
    private const int MinPythonMinor = 11;
    private const int MaxPythonMinor = 14;

    public AddinSettings()
        : this(DefaultPath)
    {
    }

    private AddinSettings(string settingsPath)
    {
        SettingsPath = settingsPath;
    }

    public static string DefaultPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "RevitPy",
        "settings.ini");

    public string? PythonDll { get; private set; }

    public string? PythonHome { get; private set; }

    public List<string> PythonPaths { get; } = new List<string>();

    public List<string> StartupScripts { get; } = new List<string>();

    public bool InitializeOnStartup { get; private set; }

    /// <summary>Start the RevitPy Live Server (for VS Code / dev tools) when Revit starts.</summary>
    public bool StartLiveServer { get; private set; }

    public string SettingsPath { get; }

    public static AddinSettings Load() => Load(DefaultPath);

    /// <summary>Loads settings from <paramref name="path"/>; a missing file yields defaults.</summary>
    public static AddinSettings Load(string path)
    {
        var settings = File.Exists(path)
            ? Parse(File.ReadAllLines(path), path)
            : new AddinSettings(path);
        settings.ApplyEnvironmentOverrides();
        return settings;
    }

    /// <summary>Parses settings lines without consulting the environment.</summary>
    public static AddinSettings Parse(IEnumerable<string> lines, string sourcePath)
    {
        var settings = new AddinSettings(sourcePath);

        foreach (var rawLine in lines)
        {
            var line = rawLine.Trim();
            if (line.Length == 0 || line.StartsWith("#", StringComparison.Ordinal) || line.StartsWith(";", StringComparison.Ordinal))
            {
                continue;
            }

            var separator = line.IndexOf('=');
            if (separator <= 0)
            {
                continue;
            }

            var key = line.Substring(0, separator).Trim().ToLowerInvariant();
            var value = line.Substring(separator + 1).Trim();

            switch (key)
            {
                case "python_dll":
                    settings.PythonDll = Expand(value);
                    break;
                case "python_home":
                    settings.PythonHome = Expand(value);
                    break;
                case "python_path":
                    settings.PythonPaths.AddRange(SplitPaths(value));
                    break;
                case "startup_script":
                    if (value.Length > 0)
                    {
                        settings.StartupScripts.Add(Expand(value));
                    }

                    break;
                case "initialize_on_startup":
                    settings.InitializeOnStartup = ParseBool(value);
                    break;
                case "start_live_server":
                    settings.StartLiveServer = ParseBool(value);
                    break;
            }
        }

        return settings;
    }

    /// <summary>
    /// Finds a CPython 3.11-3.14 DLL: the configured <see cref="PythonDll"/>, then
    /// <see cref="PythonHome"/>, then <c>PATH</c> and per-user Python installs.
    /// </summary>
    public string? ResolvePythonDll()
    {
        if (!string.IsNullOrEmpty(PythonDll) && File.Exists(PythonDll))
        {
            return PythonDll;
        }

        var directories = new List<string>();
        if (!string.IsNullOrEmpty(PythonHome))
        {
            directories.Add(PythonHome!);
        }

        var pathVariable = Environment.GetEnvironmentVariable("PATH");
        if (!string.IsNullOrEmpty(pathVariable))
        {
            directories.AddRange(pathVariable!.Split(Path.PathSeparator).Where(d => d.Trim().Length > 0));
        }

        var userPythonRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs",
            "Python");
        if (Directory.Exists(userPythonRoot))
        {
            directories.AddRange(Directory.GetDirectories(userPythonRoot, "Python3*"));
        }

        foreach (var directory in directories)
        {
            var dll = FindPythonDll(directory);
            if (dll != null)
            {
                return dll;
            }
        }

        return null;
    }

    private static string? FindPythonDll(string directory)
    {
        string[] files;
        try
        {
            files = Directory.GetFiles(directory.Trim(), "python3*.dll");
        }
        catch (Exception ex) when (ex is IOException || ex is UnauthorizedAccessException || ex is ArgumentException)
        {
            return null;
        }

        return files
            .Select(f => new { Path = f, Minor = ParseMinorVersion(System.IO.Path.GetFileNameWithoutExtension(f)) })
            .Where(c => c.Minor >= MinPythonMinor && c.Minor <= MaxPythonMinor)
            .OrderByDescending(c => c.Minor)
            .Select(c => c.Path)
            .FirstOrDefault();
    }

    /// <summary>Returns 12 for "python312", -1 for "python3" or unexpected names.</summary>
    private static int ParseMinorVersion(string fileNameWithoutExtension)
    {
        const string prefix = "python3";
        if (!fileNameWithoutExtension.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
        {
            return -1;
        }

        var digits = fileNameWithoutExtension.Substring(prefix.Length);
        return int.TryParse(digits, out var minor) ? minor : -1;
    }

    private void ApplyEnvironmentOverrides()
    {
        var dll = Environment.GetEnvironmentVariable("REVITPY_PYTHON_DLL");
        if (!string.IsNullOrEmpty(dll))
        {
            PythonDll = Expand(dll!);
        }

        var home = Environment.GetEnvironmentVariable("REVITPY_PYTHON_HOME");
        if (!string.IsNullOrEmpty(home))
        {
            PythonHome = Expand(home!);
        }

        var paths = Environment.GetEnvironmentVariable("REVITPY_PYTHON_PATH");
        if (!string.IsNullOrEmpty(paths))
        {
            PythonPaths.AddRange(SplitPaths(paths!));
        }
    }

    private static IEnumerable<string> SplitPaths(string value) =>
        value.Split(';').Select(p => Expand(p.Trim())).Where(p => p.Length > 0);

    private static string Expand(string value) => Environment.ExpandEnvironmentVariables(value);

    private static bool ParseBool(string value)
    {
        switch (value.Trim().ToLowerInvariant())
        {
            case "true":
            case "1":
            case "yes":
                return true;
            default:
                return false;
        }
    }
}

using System;
using System.Diagnostics;
using Autodesk.Revit.UI;

namespace RevitPy.Addin;

/// <summary>
/// Revit entry point (referenced by <c>RevitPy.addin</c>). Adds the RevitPy ribbon tab and
/// hosts CPython for the <c>revitpy</c> package.
/// </summary>
public sealed class RevitPyApplication : IExternalApplication
{
    private const string TabName = "RevitPy";

    public static AddinSettings Settings { get; private set; } = new AddinSettings();

    public static RevitDispatcher Dispatcher { get; } = new RevitDispatcher();

    public Result OnStartup(UIControlledApplication application)
    {
        try
        {
            Settings = AddinSettings.Load();
            Dispatcher.Register();
            CreateRibbon(application);

            if (Settings.InitializeOnStartup || Settings.StartLiveServer)
            {
                application.ControlledApplication.ApplicationInitialized += (sender, _) =>
                {
                    try
                    {
                        EnsurePython();
                        if (Settings.StartLiveServer && sender is Autodesk.Revit.ApplicationServices.Application app)
                        {
                            var result = PythonHost.RunCode(
                                LiveServerCommand.ToggleCode, "<revitpy-live>", new UIApplication(app));
                            if (!result.Success)
                            {
                                Trace.TraceError("RevitPy: Live Server failed to start:\n{0}", result.Error);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        Trace.TraceError("RevitPy: Python initialization failed: {0}", ex);
                    }
                };
            }

            return Result.Succeeded;
        }
        catch (Exception ex)
        {
            Trace.TraceError("RevitPy: startup failed: {0}", ex);
            return Result.Failed;
        }
    }

    public Result OnShutdown(UIControlledApplication application)
    {
        PythonHost.Shutdown();
        return Result.Succeeded;
    }

    /// <summary>Initializes Python on first use.</summary>
    /// <exception cref="InvalidOperationException">Python could not be initialized.</exception>
    public static void EnsurePython()
    {
        if (PythonHost.IsInitialized)
        {
            return;
        }

        try
        {
            PythonHost.Initialize(Settings, Dispatcher);
        }
        catch (InvalidOperationException)
        {
            throw;
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException("Failed to initialize Python: " + ex.Message, ex);
        }
    }

    private static void CreateRibbon(UIControlledApplication application)
    {
        try
        {
            application.CreateRibbonTab(TabName);
        }
        catch (Autodesk.Revit.Exceptions.ArgumentException)
        {
            // The tab already exists (e.g. created by another RevitPy component).
        }

        var panel = application.CreateRibbonPanel(TabName, "Python");
        var assemblyPath = typeof(RevitPyApplication).Assembly.Location;

        AddButton(panel, assemblyPath, "RunScript", "Run\nScript", typeof(RunScriptCommand), "Run a Python script with RevitPy");
        AddButton(panel, assemblyPath, "RerunScript", "Rerun", typeof(RerunScriptCommand), "Run the last script again");
        AddButton(panel, assemblyPath, "LiveServer", "Live\nServer", typeof(LiveServerCommand), "Start or stop the Live Server used by VS Code and the dev server");
        AddButton(panel, assemblyPath, "McpServer", "MCP\nServer", typeof(McpServerCommand), "Start or stop the RevitPy MCP server for AI agents");
        AddButton(panel, assemblyPath, "About", "About", typeof(AboutCommand), "RevitPy version and Python status");
    }

    private static void AddButton(RibbonPanel panel, string assemblyPath, string name, string text, Type command, string tooltip)
    {
        var data = new PushButtonData(name, text, assemblyPath, command.FullName) { ToolTip = tooltip };
        panel.AddItem(data);
    }
}

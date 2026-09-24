using System;
using System.IO;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace RevitPy.Addin;

/// <summary>Prompts for a <c>.py</c> file and runs it with <c>__revit__</c> bound.</summary>
[Transaction(TransactionMode.Manual)]
[Regeneration(RegenerationOption.Manual)]
public class RunScriptCommand : IExternalCommand
{
    internal static string? LastScriptPath { get; private set; }

    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        using var dialog = new FileOpenDialog("Python scripts (*.py)|*.py") { Title = "Run Python script" };
        if (dialog.Show() != ItemSelectionDialogResult.Confirmed)
        {
            return Result.Cancelled;
        }

        var path = ModelPathUtils.ConvertModelPathToUserVisiblePath(dialog.GetSelectedModelPath());
        LastScriptPath = path;
        return RunAndReport(path, commandData.Application, ref message);
    }

    internal static Result RunAndReport(string path, UIApplication app, ref string message)
    {
        ScriptResult result;
        try
        {
            RevitPyApplication.EnsurePython();
            result = PythonHost.RunFile(path, app);
        }
        catch (InvalidOperationException ex)
        {
            message = ex.Message;
            return Result.Failed;
        }

        return Report(Path.GetFileName(path), result, ref message);
    }

    internal static Result Report(string title, ScriptResult result, ref string message)
    {
        if (result.Success)
        {
            if (result.Output.Length > 0)
            {
                new TaskDialog("RevitPy") { MainInstruction = title, MainContent = Truncate(result.Output) }.Show();
            }

            return Result.Succeeded;
        }

        var error = result.Error ?? "Unknown error";
        new TaskDialog("RevitPy")
        {
            MainInstruction = title + " failed",
            MainContent = Truncate(error),
            ExpandedContent = Truncate(result.Output),
        }.Show();

        message = FirstLine(error);
        return Result.Failed;
    }

    private static string Truncate(string text) => text.Length <= 4000 ? text : text.Substring(0, 4000) + "\n...";

    private static string FirstLine(string text)
    {
        var newline = text.IndexOf('\n');
        return newline > 0 ? text.Substring(0, newline) : text;
    }
}

/// <summary>Runs the most recently run script again.</summary>
[Transaction(TransactionMode.Manual)]
[Regeneration(RegenerationOption.Manual)]
public class RerunScriptCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        var path = RunScriptCommand.LastScriptPath;
        if (string.IsNullOrEmpty(path))
        {
            TaskDialog.Show("RevitPy", "No script has been run yet.");
            return Result.Cancelled;
        }

        return RunScriptCommand.RunAndReport(path!, commandData.Application, ref message);
    }
}

/// <summary>Starts or stops the RevitPy MCP server inside this Revit session.</summary>
[Transaction(TransactionMode.Manual)]
[Regeneration(RegenerationOption.Manual)]
public class McpServerCommand : IExternalCommand
{
    private const string ToggleCode =
        "from revitpy.revit.host import toggle_mcp_server\n"
        + "print(toggle_mcp_server(__revit__))\n";

    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        ScriptResult result;
        try
        {
            RevitPyApplication.EnsurePython();
            result = PythonHost.RunCode(ToggleCode, "<revitpy-mcp>", commandData.Application);
        }
        catch (InvalidOperationException ex)
        {
            message = ex.Message;
            return Result.Failed;
        }

        return RunScriptCommand.Report("RevitPy MCP server", result, ref message);
    }
}

/// <summary>Shows version, Python status and the settings file location.</summary>
[Transaction(TransactionMode.ReadOnly)]
[Regeneration(RegenerationOption.Manual)]
public class AboutCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        var python = PythonHost.IsInitialized ? PythonHost.PythonVersion ?? "unknown" : "not initialized";
        var content =
            "Add-in: " + typeof(AboutCommand).Assembly.GetName().Version + "\n"
            + "Revit: " + commandData.Application.Application.VersionNumber + "\n"
            + "Python: " + python + "\n"
            + "Settings: " + RevitPyApplication.Settings.SettingsPath;

        new TaskDialog("About RevitPy") { MainInstruction = "RevitPy", MainContent = content }.Show();
        return Result.Succeeded;
    }
}

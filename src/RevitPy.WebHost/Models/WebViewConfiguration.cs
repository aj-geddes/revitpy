using System;
using System.Collections.Generic;

namespace RevitPy.WebHost.Models;

/// <summary>
/// Configuration options for WebView2 panels
/// </summary>
public class WebViewConfiguration
{
    /// <summary>
    /// Unique identifier for the panel
    /// </summary>
    public string Id { get; set; } = string.Empty;

    /// <summary>
    /// Display title for the panel
    /// </summary>
    public string Title { get; set; } = string.Empty;

    /// <summary>
    /// URL to load in the WebView
    /// </summary>
    public string Url { get; set; } = string.Empty;

    /// <summary>
    /// Panel type (dockable, modal, modeless)
    /// </summary>
    public PanelType Type { get; set; } = PanelType.Dockable;

    /// <summary>
    /// Initial position of the panel
    /// </summary>
    public PanelPosition Position { get; set; } = PanelPosition.Right;

    /// <summary>
    /// Initial size of the panel
    /// </summary>
    public PanelSize Size { get; set; } = new();

    /// <summary>
    /// Whether the panel can be resized
    /// </summary>
    public bool Resizable { get; set; } = true;

    /// <summary>
    /// Whether the panel can be closed by the user
    /// </summary>
    public bool Closable { get; set; } = true;

    /// <summary>
    /// Whether the panel is initially visible
    /// </summary>
    public bool Visible { get; set; } = true;

    /// <summary>
    /// Permissions for the WebView (API access, file system, etc.)
    /// </summary>
    public List<string> Permissions { get; set; } = new();

    /// <summary>
    /// Development mode settings
    /// </summary>
    public bool DevelopmentMode { get; set; } = false;

    /// <summary>
    /// Enable hot reload for development
    /// </summary>
    public bool HotReload { get; set; } = false;

    /// <summary>
    /// WebView2 specific options
    /// </summary>
    public WebView2Options WebView2 { get; set; } = new();

    /// <summary>
    /// Custom CSS to inject
    /// </summary>
    public string? CustomCss { get; set; }

    /// <summary>
    /// Custom JavaScript to inject
    /// </summary>
    public string? CustomJs { get; set; }

    /// <summary>
    /// Context data to pass to the web application
    /// </summary>
    public Dictionary<string, object> Context { get; set; } = new();
}

/// <summary>
/// Panel type enumeration
/// </summary>
public enum PanelType
{
    /// <summary>
    /// Dockable panel that can be docked to Revit's interface
    /// </summary>
    Dockable,

    /// <summary>
    /// Modal dialog that blocks interaction with Revit
    /// </summary>
    Modal,

    /// <summary>
    /// Modeless dialog that allows interaction with Revit
    /// </summary>
    Modeless
}

/// <summary>
/// Panel position enumeration
/// </summary>
public enum PanelPosition
{
    /// <summary>
    /// Left side of the screen
    /// </summary>
    Left,

    /// <summary>
    /// Right side of the screen
    /// </summary>
    Right,

    /// <summary>
    /// Bottom of the screen
    /// </summary>
    Bottom,

    /// <summary>
    /// Floating panel
    /// </summary>
    Floating
}

/// <summary>
/// Panel size configuration
/// </summary>
public class PanelSize
{
    /// <summary>
    /// Width in pixels
    /// </summary>
    public int Width { get; set; } = 400;

    /// <summary>
    /// Height in pixels
    /// </summary>
    public int Height { get; set; } = 600;

    /// <summary>
    /// Minimum width in pixels
    /// </summary>
    public int? MinWidth { get; set; }

    /// <summary>
    /// Minimum height in pixels
    /// </summary>
    public int? MinHeight { get; set; }

    /// <summary>
    /// Maximum width in pixels
    /// </summary>
    public int? MaxWidth { get; set; }

    /// <summary>
    /// Maximum height in pixels
    /// </summary>
    public int? MaxHeight { get; set; }
}

/// <summary>
/// WebView2 specific configuration options
/// </summary>
public class WebView2Options
{
    /// <summary>
    /// User data folder path
    /// </summary>
    public string? UserDataFolder { get; set; }

    /// <summary>
    /// Enable developer tools
    /// </summary>
    public bool DevToolsEnabled { get; set; } = false;

    /// <summary>
    /// Enable script debugging
    /// </summary>
    public bool ScriptDebuggingEnabled { get; set; } = false;

    /// <summary>
    /// Enable context menu
    /// </summary>
    public bool ContextMenuEnabled { get; set; } = true;

    /// <summary>
    /// Enable zoom control
    /// </summary>
    public bool ZoomControlEnabled { get; set; } = false;

    /// <summary>
    /// Default background color
    /// </summary>
    public string BackgroundColor { get; set; } = "#FFFFFF";

    /// <summary>
    /// Additional browser arguments
    /// </summary>
    public List<string> AdditionalBrowserArguments { get; set; } = new();

    /// <summary>
    /// Custom user agent string
    /// </summary>
    public string? UserAgent { get; set; }

    /// <summary>
    /// Language preference
    /// </summary>
    public string Language { get; set; } = "en-US";
}
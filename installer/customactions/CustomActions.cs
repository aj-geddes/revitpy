using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.Deployment.WindowsInstaller;
using Microsoft.Win32;
using System.Diagnostics;
using System.ServiceProcess;
using System.Text.Json;
using System.Threading.Tasks;

namespace RevitPy.Installer.CustomActions
{
    public class CustomActions
    {
        /// <summary>
        /// Detects installed Revit versions by scanning registry and file system
        /// </summary>
        /// <param name="session">Windows Installer session</param>
        /// <returns>Success or failure code</returns>
        [CustomAction]
        public static ActionResult DetectRevitInstallations(Session session)
        {
            session.Log("Starting Revit installation detection...");

            try
            {
                var detectedVersions = new List<string>();
                var revitVersions = new[] { "2022", "2023", "2024", "2025" };

                foreach (var version in revitVersions)
                {
                    if (IsRevitVersionInstalled(session, version))
                    {
                        detectedVersions.Add(version);
                        session[$ "REVIT_{version}_INSTALLED"] = "1";
                        session.Log($"Revit {version} detected");
                    }
                    else
                    {
                        session[$ "REVIT_{version}_INSTALLED"] = "";
                        session.Log($"Revit {version} not found");
                    }
                }

                // Set combined property for all detected versions
                session["REVIT_VERSIONS"] = string.Join(",", detectedVersions);
                session.Log($"Total Revit versions detected: {detectedVersions.Count}");

                if (detectedVersions.Any())
                {
                    session.Log("Revit detection completed successfully");
                    return ActionResult.Success;
                }
                else
                {
                    session.Log("WARNING: No Revit installations detected");
                    // Still return success to allow user to install for future Revit installations
                    return ActionResult.Success;
                }
            }
            catch (Exception ex)
            {
                session.Log($"ERROR: Revit detection failed: {ex.Message}");
                return ActionResult.Failure;
            }
        }

        /// <summary>
        /// Detects Python installation
        /// </summary>
        /// <param name="session">Windows Installer session</param>
        /// <returns>Success or failure code</returns>
        [CustomAction]
        public static ActionResult DetectPythonInstallation(Session session)
        {
            session.Log("Starting Python installation detection...");

            try
            {
                var pythonInfo = GetPythonInstallation();

                if (pythonInfo != null)
                {
                    session["PYTHON_INSTALLED"] = "1";
                    session["PYTHON_VERSION"] = pythonInfo.Version;
                    session["PYTHON_PATH"] = pythonInfo.Path;
                    session.Log($"Python {pythonInfo.Version} detected at {pythonInfo.Path}");

                    // Check if Python version meets requirements (3.11+)
                    if (IsPythonVersionSupported(pythonInfo.Version))
                    {
                        session["INSTALL_PYTHON"] = "0"; // Don't install Python by default
                        session.Log("Python version meets requirements");
                    }
                    else
                    {
                        session["INSTALL_PYTHON"] = "1"; // Install Python by default
                        session.Log($"Python version {pythonInfo.Version} is below minimum requirement (3.11)");
                    }
                }
                else
                {
                    session["PYTHON_INSTALLED"] = "";
                    session["PYTHON_VERSION"] = "";
                    session["PYTHON_PATH"] = "";
                    session["INSTALL_PYTHON"] = "1"; // Install Python by default
                    session.Log("Python not detected");
                }

                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"ERROR: Python detection failed: {ex.Message}");
                return ActionResult.Failure;
            }
        }

        /// <summary>
        /// Configures Revit add-ins for detected installations
        /// </summary>
        /// <param name="session">Windows Installer session</param>
        /// <returns>Success or failure code</returns>
        [CustomAction]
        public static ActionResult ConfigureRevitAddins(Session session)
        {
            session.Log("Starting Revit add-in configuration...");

            try
            {
                var installDir = session.CustomActionData["INSTALLDIR"];
                var revitVersions = session.CustomActionData["REVIT_VERSIONS"];

                if (string.IsNullOrEmpty(revitVersions))
                {
                    session.Log("No Revit versions to configure");
                    return ActionResult.Success;
                }

                var versions = revitVersions.Split(',');
                var successCount = 0;

                foreach (var version in versions)
                {
                    if (ConfigureRevitAddin(session, version, installDir))
                    {
                        successCount++;
                        session.Log($"Successfully configured add-in for Revit {version}");
                    }
                    else
                    {
                        session.Log($"WARNING: Failed to configure add-in for Revit {version}");
                    }
                }

                if (successCount > 0)
                {
                    session.Log($"Add-in configuration completed for {successCount} Revit version(s)");
                    return ActionResult.Success;
                }
                else
                {
                    session.Log("ERROR: Failed to configure add-ins for any Revit version");
                    return ActionResult.Failure;
                }
            }
            catch (Exception ex)
            {
                session.Log($"ERROR: Add-in configuration failed: {ex.Message}");
                return ActionResult.Failure;
            }
        }

        /// <summary>
        /// Starts the RevitPy Host Service
        /// </summary>
        /// <param name="session">Windows Installer session</param>
        /// <returns>Success or failure code</returns>
        [CustomAction]
        public static ActionResult StartRevitPyService(Session session)
        {
            session.Log("Starting RevitPy Host Service...");

            try
            {
                using (var serviceController = new ServiceController("RevitPyHost"))
                {
                    if (serviceController.Status == ServiceControllerStatus.Stopped)
                    {
                        serviceController.Start();
                        serviceController.WaitForStatus(ServiceControllerStatus.Running, TimeSpan.FromSeconds(30));
                        session.Log("RevitPy Host Service started successfully");
                    }
                    else
                    {
                        session.Log($"RevitPy Host Service is already {serviceController.Status}");
                    }
                }

                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"WARNING: Failed to start RevitPy Host Service: {ex.Message}");
                // Don't fail installation if service doesn't start
                return ActionResult.Success;
            }
        }

        /// <summary>
        /// Removes Revit integration on uninstall
        /// </summary>
        /// <param name="session">Windows Installer session</param>
        /// <returns>Success or failure code</returns>
        [CustomAction]
        public static ActionResult RemoveRevitIntegration(Session session)
        {
            session.Log("Removing Revit integration...");

            try
            {
                var revitVersions = new[] { "2022", "2023", "2024", "2025" };

                foreach (var version in revitVersions)
                {
                    RemoveRevitAddin(session, version);
                }

                session.Log("Revit integration removal completed");
                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"WARNING: Revit integration removal failed: {ex.Message}");
                // Don't fail uninstallation
                return ActionResult.Success;
            }
        }

        #region Helper Methods

        private static bool IsRevitVersionInstalled(Session session, string version)
        {
            // Check registry for Revit installation
            var registryKeys = new[]
            {
                $@"SOFTWARE\Autodesk\Revit\{version}",
                $@"SOFTWARE\WOW6432Node\Autodesk\Revit\{version}"
            };

            foreach (var keyPath in registryKeys)
            {
                using (var key = Registry.LocalMachine.OpenSubKey(keyPath))
                {
                    if (key != null)
                    {
                        var installPath = key.GetValue("InstallPath") as string;
                        if (!string.IsNullOrEmpty(installPath) && Directory.Exists(installPath))
                        {
                            var revitExe = Path.Combine(installPath, "Revit.exe");
                            if (File.Exists(revitExe))
                            {
                                session.Log($"Found Revit {version} at {installPath}");
                                return true;
                            }
                        }
                    }
                }
            }

            // Check common installation paths
            var commonPaths = new[]
            {
                $@"C:\Program Files\Autodesk\Revit {version}",
                $@"C:\Program Files (x86)\Autodesk\Revit {version}"
            };

            foreach (var path in commonPaths)
            {
                var revitExe = Path.Combine(path, "Revit.exe");
                if (File.Exists(revitExe))
                {
                    session.Log($"Found Revit {version} at {path}");
                    return true;
                }
            }

            return false;
        }

        private static PythonInstallation GetPythonInstallation()
        {
            // Try to find Python in PATH first
            try
            {
                var process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = "python",
                        Arguments = "--version",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        CreateNoWindow = true
                    }
                };

                process.Start();
                var output = process.StandardOutput.ReadToEnd();
                process.WaitForExit();

                if (process.ExitCode == 0 && output.Contains("Python"))
                {
                    var version = output.Replace("Python ", "").Trim();
                    var pythonPath = GetPythonPath();
                    
                    return new PythonInstallation
                    {
                        Version = version,
                        Path = pythonPath
                    };
                }
            }
            catch
            {
                // Fall through to registry check
            }

            // Check registry for Python installations
            var registryPaths = new[]
            {
                @"SOFTWARE\Python\PythonCore",
                @"SOFTWARE\WOW6432Node\Python\PythonCore"
            };

            foreach (var basePath in registryPaths)
            {
                using (var baseKey = Registry.LocalMachine.OpenSubKey(basePath))
                {
                    if (baseKey != null)
                    {
                        var versions = baseKey.GetSubKeyNames()
                            .Where(v => Version.TryParse(v, out _))
                            .OrderByDescending(v => new Version(v));

                        foreach (var version in versions)
                        {
                            using (var versionKey = baseKey.OpenSubKey($@"{version}\InstallPath"))
                            {
                                if (versionKey != null)
                                {
                                    var installPath = versionKey.GetValue("") as string;
                                    if (!string.IsNullOrEmpty(installPath) && Directory.Exists(installPath))
                                    {
                                        var pythonExe = Path.Combine(installPath, "python.exe");
                                        if (File.Exists(pythonExe))
                                        {
                                            return new PythonInstallation
                                            {
                                                Version = version,
                                                Path = pythonExe
                                            };
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            return null;
        }

        private static string GetPythonPath()
        {
            try
            {
                var process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = "where",
                        Arguments = "python",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        CreateNoWindow = true
                    }
                };

                process.Start();
                var output = process.StandardOutput.ReadToEnd();
                process.WaitForExit();

                if (process.ExitCode == 0 && !string.IsNullOrWhiteSpace(output))
                {
                    return output.Split('\n')[0].Trim();
                }
            }
            catch
            {
                // Return empty if detection fails
            }

            return "";
        }

        private static bool IsPythonVersionSupported(string version)
        {
            if (Version.TryParse(version, out var pythonVersion))
            {
                return pythonVersion >= new Version(3, 11);
            }
            return false;
        }

        private static bool ConfigureRevitAddin(Session session, string version, string installDir)
        {
            try
            {
                var addinDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                    "Autodesk", "Revit", "Addins", version);

                if (!Directory.Exists(addinDir))
                {
                    Directory.CreateDirectory(addinDir);
                }

                var addinFilePath = Path.Combine(addinDir, "RevitPy.addin");
                var addinContent = GenerateAddinManifest(version, installDir);

                File.WriteAllText(addinFilePath, addinContent);

                session.Log($"Created add-in manifest at {addinFilePath}");
                return true;
            }
            catch (Exception ex)
            {
                session.Log($"Failed to configure Revit {version} add-in: {ex.Message}");
                return false;
            }
        }

        private static string GenerateAddinManifest(string version, string installDir)
        {
            var assemblyPath = Path.Combine(installDir, "bin", "RevitPy.Bridge.dll");
            var addinId = Guid.NewGuid();

            return $@"<?xml version=""1.0"" encoding=""utf-8""?>
<RevitAddIns>
  <AddIn Type=""Application"">
    <Name>RevitPy</Name>
    <Assembly>{assemblyPath}</Assembly>
    <AddInId>{addinId}</AddInId>
    <FullClassName>RevitPy.Bridge.RevitPyApplication</FullClassName>
    <VendorId>REVITPY</VendorId>
    <VendorDescription>RevitPy Team</VendorDescription>
    <Description>Modern Python Framework for Revit Development</Description>
    <VisibilityMode>NotVisibleWhenNoActiveDocument</VisibilityMode>
  </AddIn>
</RevitAddIns>";
        }

        private static void RemoveRevitAddin(Session session, string version)
        {
            try
            {
                var addinDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                    "Autodesk", "Revit", "Addins", version);

                var addinFilePath = Path.Combine(addinDir, "RevitPy.addin");

                if (File.Exists(addinFilePath))
                {
                    File.Delete(addinFilePath);
                    session.Log($"Removed add-in manifest for Revit {version}");
                }
            }
            catch (Exception ex)
            {
                session.Log($"Failed to remove Revit {version} add-in: {ex.Message}");
            }
        }

        #endregion

        #region Helper Classes

        private class PythonInstallation
        {
            public string Version { get; set; }
            public string Path { get; set; }
        }

        #endregion
    }
}
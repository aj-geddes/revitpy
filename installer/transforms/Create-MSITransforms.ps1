#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Creates MSI transform files for enterprise customization of RevitPy installer

.DESCRIPTION
    This script creates MSI transform (.mst) files that allow organizations to customize
    the RevitPy installation behavior without modifying the original MSI package.

    Transforms can customize:
    - Installation directory
    - Feature selection
    - Registry settings
    - Configuration files
    - Revit version targeting

.PARAMETER MSIPath
    Path to the RevitPy MSI file

.PARAMETER OutputPath
    Directory where transform files will be created

.PARAMETER OrganizationName
    Name of the organization for customization

.EXAMPLE
    .\Create-MSITransforms.ps1 -MSIPath "RevitPy-1.0.0.msi" -OutputPath ".\transforms" -OrganizationName "Contoso"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MSIPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [Parameter()]
    [string]$OrganizationName = "Enterprise",

    [Parameter()]
    [switch]$Force
)

# Import Windows Installer COM object
$WindowsInstaller = New-Object -ComObject WindowsInstaller.Installer

# Transform configuration templates
$TransformConfigurations = @{
    "Enterprise-Silent" = @{
        Description = "Enterprise deployment with silent installation"
        Properties = @{
            "INSTALLDIR" = "C:\Program Files\RevitPy"
            "ALLUSERS" = "1"
            "MSIRESTARTMANAGERCONTROL" = "Disable"
            "REBOOT" = "ReallySuppress"
            "INSTALL_PYTHON" = "1"
            "REVIT_VERSIONS" = "2023,2024,2025"
        }
        Features = @{
            "MainFeature" = "install"
            "PythonRuntimeFeature" = "install"
            "Revit2022Feature" = "absent"
            "Revit2023Feature" = "install"
            "Revit2024Feature" = "install"
            "Revit2025Feature" = "install"
        }
        Registry = @{
            "HKLM\SOFTWARE\RevitPy\Enterprise\Deployment" = @{
                "OrganizationName" = $OrganizationName
                "DeploymentDate" = (Get-Date).ToString("yyyy-MM-dd")
                "ConfigurationProfile" = "Enterprise-Silent"
            }
        }
    }

    "Developer-Workstation" = @{
        Description = "Developer workstation with all features"
        Properties = @{
            "INSTALLDIR" = "C:\Program Files\RevitPy"
            "ALLUSERS" = "1"
            "INSTALL_PYTHON" = "1"
            "REVIT_VERSIONS" = "2022,2023,2024,2025"
        }
        Features = @{
            "MainFeature" = "install"
            "PythonRuntimeFeature" = "install"
            "Revit2022Feature" = "install"
            "Revit2023Feature" = "install"
            "Revit2024Feature" = "install"
            "Revit2025Feature" = "install"
        }
        Registry = @{
            "HKLM\SOFTWARE\RevitPy\Enterprise\Deployment" = @{
                "OrganizationName" = $OrganizationName
                "DeploymentDate" = (Get-Date).ToString("yyyy-MM-dd")
                "ConfigurationProfile" = "Developer-Workstation"
            }
        }
    }

    "Revit2024-Only" = @{
        Description = "Revit 2024 specific deployment"
        Properties = @{
            "INSTALLDIR" = "C:\Program Files\RevitPy"
            "ALLUSERS" = "1"
            "INSTALL_PYTHON" = "1"
            "REVIT_VERSIONS" = "2024"
        }
        Features = @{
            "MainFeature" = "install"
            "PythonRuntimeFeature" = "install"
            "Revit2022Feature" = "absent"
            "Revit2023Feature" = "absent"
            "Revit2024Feature" = "install"
            "Revit2025Feature" = "absent"
        }
        Registry = @{
            "HKLM\SOFTWARE\RevitPy\Enterprise\Deployment" = @{
                "OrganizationName" = $OrganizationName
                "DeploymentDate" = (Get-Date).ToString("yyyy-MM-dd")
                "ConfigurationProfile" = "Revit2024-Only"
            }
        }
    }

    "Minimal-Installation" = @{
        Description = "Minimal installation without Python runtime"
        Properties = @{
            "INSTALLDIR" = "C:\Program Files\RevitPy"
            "ALLUSERS" = "1"
            "INSTALL_PYTHON" = "0"
            "REVIT_VERSIONS" = "2024,2025"
        }
        Features = @{
            "MainFeature" = "install"
            "PythonRuntimeFeature" = "absent"
            "Revit2022Feature" = "absent"
            "Revit2023Feature" = "absent"
            "Revit2024Feature" = "install"
            "Revit2025Feature" = "install"
        }
        Registry = @{
            "HKLM\SOFTWARE\RevitPy\Enterprise\Deployment" = @{
                "OrganizationName" = $OrganizationName
                "DeploymentDate" = (Get-Date).ToString("yyyy-MM-dd")
                "ConfigurationProfile" = "Minimal-Installation"
            }
        }
    }
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "Info"
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "Error" { "Red" }
        "Warning" { "Yellow" }
        "Info" { "Green" }
        default { "White" }
    }

    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function New-MSITransform {
    param(
        [string]$MSIPath,
        [string]$TransformName,
        [hashtable]$Configuration,
        [string]$OutputPath
    )

    Write-Log "Creating transform: $TransformName"

    try {
        # Open the MSI database
        $database = $WindowsInstaller.OpenDatabase($MSIPath, 1) # msiOpenDatabaseModeTransact

        # Create transform
        $transformPath = Join-Path $OutputPath "$TransformName.mst"

        # Apply property changes
        if ($Configuration.Properties) {
            Write-Log "Applying property changes for $TransformName"

            foreach ($property in $Configuration.Properties.GetEnumerator()) {
                $query = "SELECT * FROM Property WHERE Property = '$($property.Key)'"
                $view = $database.OpenView($query)
                $view.Execute()

                $record = $view.Fetch()
                if ($record) {
                    # Update existing property
                    $record.StringData(2) = $property.Value
                    $view.Modify(2, $record) # msiViewModifyUpdate
                    Write-Log "Updated property: $($property.Key) = $($property.Value)"
                }
                else {
                    # Insert new property
                    $insertQuery = "INSERT INTO Property (Property, Value) VALUES (?, ?)"
                    $insertView = $database.OpenView($insertQuery)
                    $insertRecord = $WindowsInstaller.CreateRecord(2)
                    $insertRecord.StringData(1) = $property.Key
                    $insertRecord.StringData(2) = $property.Value
                    $insertView.Execute($insertRecord)
                    Write-Log "Added property: $($property.Key) = $($property.Value)"
                    $insertView.Close()
                }

                $view.Close()
            }
        }

        # Apply feature changes
        if ($Configuration.Features) {
            Write-Log "Applying feature changes for $TransformName"

            foreach ($feature in $Configuration.Features.GetEnumerator()) {
                $installLevel = switch ($feature.Value) {
                    "install" { 1 }
                    "absent" { 0 }
                    default { 1 }
                }

                $query = "UPDATE Feature SET Level = $installLevel WHERE Feature = '$($feature.Key)'"
                $view = $database.OpenView($query)
                $view.Execute()
                $view.Close()
                Write-Log "Set feature $($feature.Key) to $($feature.Value) (level $installLevel)"
            }
        }

        # Apply registry changes
        if ($Configuration.Registry) {
            Write-Log "Applying registry changes for $TransformName"

            foreach ($registryKey in $Configuration.Registry.GetEnumerator()) {
                $keyPath = $registryKey.Key
                $values = $registryKey.Value

                # Parse registry key
                $parts = $keyPath -split '\\'
                $root = $parts[0]
                $key = ($parts[1..($parts.Length-1)]) -join '\'

                $rootValue = switch ($root) {
                    "HKLM" { -2147483646 }  # HKEY_LOCAL_MACHINE
                    "HKCU" { -2147483647 }  # HKEY_CURRENT_USER
                    default { -2147483646 }
                }

                foreach ($regValue in $values.GetEnumerator()) {
                    # Generate unique component and registry IDs
                    $componentId = "Reg_" + ($TransformName -replace '[^A-Za-z0-9]', '') + "_" + ($regValue.Key -replace '[^A-Za-z0-9]', '')
                    $registryId = $componentId + "_Value"

                    # Insert registry entry
                    $insertQuery = "INSERT INTO Registry (Registry, Root, Key, Name, Value, Component_) VALUES (?, ?, ?, ?, ?, ?)"
                    $insertView = $database.OpenView($insertQuery)
                    $insertRecord = $WindowsInstaller.CreateRecord(6)
                    $insertRecord.StringData(1) = $registryId
                    $insertRecord.IntegerData(2) = $rootValue
                    $insertRecord.StringData(3) = $key
                    $insertRecord.StringData(4) = $regValue.Key
                    $insertRecord.StringData(5) = $regValue.Value
                    $insertRecord.StringData(6) = $componentId

                    try {
                        $insertView.Execute($insertRecord)
                        Write-Log "Added registry value: $keyPath\$($regValue.Key) = $($regValue.Value)"
                    }
                    catch {
                        Write-Log "Warning: Could not add registry value: $($_.Exception.Message)" -Level Warning
                    }

                    $insertView.Close()
                }
            }
        }

        # Generate transform
        $referenceDatabase = $WindowsInstaller.OpenDatabase($MSIPath, 0) # msiOpenDatabaseModeReadOnly
        $database.GenerateTransform($referenceDatabase, $transformPath)
        $database.CreateTransformSummaryInfo($referenceDatabase, $transformPath, 0, 0)

        $database.Commit()
        $referenceDatabase.Close()
        $database.Close()

        if (Test-Path $transformPath) {
            Write-Log "Transform created successfully: $transformPath"
            return $transformPath
        }
        else {
            Write-Log "Failed to create transform: $transformPath" -Level Error
            return $null
        }
    }
    catch {
        Write-Log "Error creating transform $TransformName : $($_.Exception.Message)" -Level Error
        return $null
    }
}

function New-TransformDocumentation {
    param(
        [string]$OutputPath,
        [hashtable]$Configurations
    )

    Write-Log "Creating transform documentation"

    $docPath = Join-Path $OutputPath "Transform-Documentation.md"

    $documentation = @"
# RevitPy MSI Transform Documentation

This document describes the available MSI transforms for customizing RevitPy deployment.

## Available Transforms

"@

    foreach ($config in $Configurations.GetEnumerator()) {
        $transformName = $config.Key
        $details = $config.Value

        $documentation += @"

### $transformName

**Description:** $($details.Description)

**Properties:**
"@

        if ($details.Properties) {
            foreach ($prop in $details.Properties.GetEnumerator()) {
                $documentation += "`n- $($prop.Key) = $($prop.Value)"
            }
        }

        $documentation += @"

**Features:**
"@

        if ($details.Features) {
            foreach ($feature in $details.Features.GetEnumerator()) {
                $documentation += "`n- $($feature.Key) = $($feature.Value)"
            }
        }

        $documentation += @"

**Usage:**
``````
msiexec /i RevitPy-1.0.0.msi TRANSFORMS=$transformName.mst /quiet
``````

"@
    }

    $documentation += @"

## Enterprise Deployment Examples

### Silent Installation with Transform
``````powershell
# Deploy with Enterprise-Silent transform
msiexec /i "RevitPy-1.0.0.msi" TRANSFORMS="Enterprise-Silent.mst" /quiet /log "install.log"

# Deploy with custom Revit versions
msiexec /i "RevitPy-1.0.0.msi" TRANSFORMS="Revit2024-Only.mst" REVIT_VERSIONS="2024" /quiet
``````

### Group Policy Deployment
1. Copy MSI and MST files to a network share accessible by all target computers
2. Create a Group Policy Object (GPO) for software deployment
3. Assign the MSI package with the appropriate transform
4. Configure deployment options (install, upgrade, uninstall)

### PowerShell Deployment Script
``````powershell
# Example deployment script
`$computers = @("PC001", "PC002", "PC003")
`$msiPath = "\\server\share\RevitPy-1.0.0.msi"
`$transformPath = "\\server\share\Enterprise-Silent.mst"

foreach (`$computer in `$computers) {
    Invoke-Command -ComputerName `$computer -ScriptBlock {
        param(`$msi, `$transform)
        Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"`$msi`" TRANSFORMS=`"`$transform`" /quiet /log C:\temp\revitpy-install.log" -Wait
    } -ArgumentList `$msiPath, `$transformPath
}
``````

## Customization Guidelines

### Creating Custom Transforms
1. Use this script to generate base transforms
2. Use Orca or InstEd to make additional customizations
3. Test transforms in a lab environment before production deployment
4. Document all customizations for maintenance

### Best Practices
- Always test transforms before production deployment
- Keep transform files in version control
- Document all customizations
- Use meaningful names for custom transforms
- Validate transforms with multiple MSI validation tools

## Support

For technical support with transforms, contact the RevitPy team or refer to the enterprise deployment documentation.
"@

    Set-Content -Path $docPath -Value $documentation -Encoding UTF8
    Write-Log "Documentation created: $docPath"
}

function New-DeploymentScript {
    param(
        [string]$OutputPath,
        [hashtable]$Configurations
    )

    Write-Log "Creating deployment script template"

    $scriptPath = Join-Path $OutputPath "Deploy-With-Transforms.ps1"

    $deployScript = @'
#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Deploy RevitPy using MSI transforms

.PARAMETER TransformName
    Name of the transform to use

.PARAMETER TargetComputers
    Computers to deploy to

.PARAMETER MSIPath
    Path to RevitPy MSI file

.PARAMETER Silent
    Perform silent installation
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('@ + (($Configurations.Keys | ForEach-Object { "'$_'" }) -join ', ') + @')]
    [string]$TransformName,

    [Parameter()]
    [string[]]$TargetComputers = @($env:COMPUTERNAME),

    [Parameter()]
    [string]$MSIPath = ".\RevitPy-1.0.0.msi",

    [Parameter()]
    [switch]$Silent
)

# Transform configurations
$TransformConfigurations = @{
'@

    foreach ($config in $Configurations.GetEnumerator()) {
        $deployScript += "`n    '$($config.Key)' = @{"
        $deployScript += "`n        Description = '$($config.Value.Description)'"
        $deployScript += "`n        TransformFile = '$($config.Key).mst'"
        $deployScript += "`n    }"
    }

    $deployScript += @'
}

$selectedConfig = $TransformConfigurations[$TransformName]
Write-Host "Deploying RevitPy with transform: $TransformName"
Write-Host "Description: $($selectedConfig.Description)"

$transformPath = Join-Path $PSScriptRoot $selectedConfig.TransformFile

if (-not (Test-Path $transformPath)) {
    Write-Error "Transform file not found: $transformPath"
    exit 1
}

foreach ($computer in $TargetComputers) {
    Write-Host "Deploying to $computer..."

    $arguments = @(
        "/i", "`"$MSIPath`""
        "TRANSFORMS=`"$transformPath`""
    )

    if ($Silent) {
        $arguments += "/quiet"
    }

    $arguments += "/log", "C:\temp\revitpy-install-$computer.log"

    if ($computer -eq $env:COMPUTERNAME) {
        Start-Process -FilePath "msiexec.exe" -ArgumentList $arguments -Wait
    }
    else {
        Invoke-Command -ComputerName $computer -ScriptBlock {
            param($MSI, $Transform, $Silent)

            $args = @("/i", "`"$MSI`"", "TRANSFORMS=`"$Transform`"")
            if ($Silent) { $args += "/quiet" }
            $args += "/log", "C:\temp\revitpy-install.log"

            Start-Process -FilePath "msiexec.exe" -ArgumentList $args -Wait
        } -ArgumentList $MSIPath, $transformPath, $Silent.IsPresent
    }

    Write-Host "Deployment to $computer completed."
}
'@

    Set-Content -Path $scriptPath -Value $deployScript -Encoding UTF8
    Write-Log "Deployment script created: $scriptPath"
}

# Main execution
try {
    Write-Log "Starting MSI transform creation for RevitPy"

    if (-not (Test-Path $MSIPath)) {
        throw "MSI file not found: $MSIPath"
    }

    if (-not (Test-Path $OutputPath)) {
        New-Item -Path $OutputPath -ItemType Directory -Force | Out-Null
    }

    $createdTransforms = @()

    foreach ($config in $TransformConfigurations.GetEnumerator()) {
        $transformPath = New-MSITransform -MSIPath $MSIPath -TransformName $config.Key -Configuration $config.Value -OutputPath $OutputPath

        if ($transformPath) {
            $createdTransforms += @{
                Name = $config.Key
                Path = $transformPath
                Description = $config.Value.Description
            }
        }
    }

    # Create documentation
    New-TransformDocumentation -OutputPath $OutputPath -Configurations $TransformConfigurations

    # Create deployment script
    New-DeploymentScript -OutputPath $OutputPath -Configurations $TransformConfigurations

    Write-Log "Transform creation completed successfully"
    Write-Log "Created $($createdTransforms.Count) transforms:"

    foreach ($transform in $createdTransforms) {
        Write-Log "  - $($transform.Name): $($transform.Description)"
    }

    Write-Log "Output directory: $OutputPath"
}
catch {
    Write-Log "Transform creation failed: $($_.Exception.Message)" -Level Error
    exit 1
}
finally {
    # Cleanup COM objects
    if ($WindowsInstaller) {
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($WindowsInstaller) | Out-Null
    }
}

import * as vscode from 'vscode';
import * as path from 'path';
import { Logger } from '../common/logger';
import { ProjectTemplate, RevitPyConfig } from '../common/types';

export class ProjectManager implements vscode.Disposable {
    private templates: ProjectTemplate[] = [];

    constructor(private logger: Logger) {
        this.initializeTemplates();
    }

    private initializeTemplates(): void {
        this.templates = [
            {
                name: 'Basic RevitPy Script',
                description: 'A simple RevitPy script template with basic structure',
                category: 'Basic',
                files: [
                    {
                        path: 'main.py',
                        content: this.getBasicScriptTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'revitpy.json',
                        content: this.getBasicConfigTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'README.md',
                        content: this.getBasicReadmeTemplate(),
                        isTemplate: true
                    }
                ]
            },
            {
                name: 'Revit Add-in',
                description: 'Complete Revit add-in with UI and command structure',
                category: 'Add-in',
                files: [
                    {
                        path: 'src/__init__.py',
                        content: ''
                    },
                    {
                        path: 'src/commands.py',
                        content: this.getAddinCommandsTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'src/ui/dialog.py',
                        content: this.getAddinDialogTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'src/utils/geometry.py',
                        content: this.getGeometryUtilsTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'resources/icons/icon.ico',
                        content: '# Icon file placeholder'
                    },
                    {
                        path: 'manifest.addin',
                        content: this.getAddinManifestTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'revitpy.json',
                        content: this.getAddinConfigTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'README.md',
                        content: this.getAddinReadmeTemplate(),
                        isTemplate: true
                    }
                ],
                dependencies: ['revitpy-ui', 'revitpy-utils']
            },
            {
                name: 'Data Export Tool',
                description: 'Template for creating data export utilities',
                category: 'Utilities',
                files: [
                    {
                        path: 'export_tool.py',
                        content: this.getExportToolTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'config/export_config.json',
                        content: this.getExportConfigTemplate()
                    },
                    {
                        path: 'output/.gitkeep',
                        content: ''
                    },
                    {
                        path: 'revitpy.json',
                        content: this.getUtilityConfigTemplate(),
                        isTemplate: true
                    }
                ],
                dependencies: ['revitpy-utils'],
                postInstallInstructions: 'Configure the export settings in config/export_config.json'
            },
            {
                name: 'Revit API Test Suite',
                description: 'Testing framework for Revit API functionality',
                category: 'Testing',
                files: [
                    {
                        path: 'tests/__init__.py',
                        content: ''
                    },
                    {
                        path: 'tests/test_elements.py',
                        content: this.getTestElementsTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'tests/test_geometry.py',
                        content: this.getTestGeometryTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'tests/fixtures/sample_data.json',
                        content: this.getTestFixturesTemplate()
                    },
                    {
                        path: 'run_tests.py',
                        content: this.getTestRunnerTemplate(),
                        isTemplate: true
                    },
                    {
                        path: 'revitpy.json',
                        content: this.getTestConfigTemplate(),
                        isTemplate: true
                    }
                ],
                dependencies: ['pytest', 'revitpy-utils']
            }
        ];
    }

    async createProject(): Promise<void> {
        try {
            // Show template selection
            const selectedTemplate = await this.showTemplateSelector();
            if (!selectedTemplate) return;

            // Get project location
            const projectLocation = await this.getProjectLocation();
            if (!projectLocation) return;

            // Get project name
            const projectName = await this.getProjectName();
            if (!projectName) return;

            // Create project
            await this.createProjectFromTemplate(selectedTemplate, projectLocation, projectName);

            // Open the new project
            await this.openProject(path.join(projectLocation, projectName));

            vscode.window.showInformationMessage(`RevitPy project '${projectName}' created successfully!`);
        } catch (error) {
            this.logger.error('Failed to create project', error);
            vscode.window.showErrorMessage(`Failed to create project: ${error}`);
        }
    }

    private async showTemplateSelector(): Promise<ProjectTemplate | undefined> {
        interface TemplateQuickPickItem extends vscode.QuickPickItem {
            template: ProjectTemplate;
        }

        const items: TemplateQuickPickItem[] = this.templates.map(template => ({
            label: template.name,
            description: template.category,
            detail: template.description,
            template
        }));

        const selectedItem = await vscode.window.showQuickPick(items, {
            placeHolder: 'Select a project template',
            matchOnDescription: true,
            matchOnDetail: true
        });

        return selectedItem?.template;
    }

    private async getProjectLocation(): Promise<string | undefined> {
        const folderOptions: vscode.OpenDialogOptions = {
            canSelectMany: false,
            canSelectFiles: false,
            canSelectFolders: true,
            openLabel: 'Select Project Location'
        };

        const folderUri = await vscode.window.showOpenDialog(folderOptions);
        return folderUri?.[0]?.fsPath;
    }

    private async getProjectName(): Promise<string | undefined> {
        return await vscode.window.showInputBox({
            prompt: 'Enter project name',
            validateInput: (value) => {
                if (!value || value.trim() === '') {
                    return 'Project name cannot be empty';
                }
                if (!/^[a-zA-Z0-9_-]+$/.test(value)) {
                    return 'Project name can only contain letters, numbers, hyphens, and underscores';
                }
                return undefined;
            }
        });
    }

    private async createProjectFromTemplate(
        template: ProjectTemplate, 
        location: string, 
        projectName: string
    ): Promise<void> {
        const projectPath = path.join(location, projectName);
        
        // Create project directory
        const projectUri = vscode.Uri.file(projectPath);
        await vscode.workspace.fs.createDirectory(projectUri);

        // Create files
        for (const file of template.files) {
            const filePath = path.join(projectPath, file.path);
            const fileUri = vscode.Uri.file(filePath);
            
            // Create directory if needed
            const dirPath = path.dirname(filePath);
            const dirUri = vscode.Uri.file(dirPath);
            try {
                await vscode.workspace.fs.createDirectory(dirUri);
            } catch {
                // Directory might already exist
            }

            // Process template content
            let content = file.content;
            if (file.isTemplate) {
                content = this.processTemplate(content, {
                    projectName,
                    projectPath,
                    timestamp: new Date().toISOString()
                });
            }

            // Write file
            await vscode.workspace.fs.writeFile(fileUri, Buffer.from(content));
        }

        // Install dependencies if specified
        if (template.dependencies && template.dependencies.length > 0) {
            await this.installTemplateDependencies(projectPath, template.dependencies);
        }

        this.logger.info(`Project created: ${projectPath}`);
    }

    private processTemplate(content: string, variables: Record<string, string>): string {
        let processed = content;
        
        for (const [key, value] of Object.entries(variables)) {
            const placeholder = new RegExp(`\\{\\{\\s*${key}\\s*\\}\\}`, 'g');
            processed = processed.replace(placeholder, value);
        }

        return processed;
    }

    private async installTemplateDependencies(projectPath: string, dependencies: string[]): Promise<void> {
        try {
            // Read existing config
            const configPath = path.join(projectPath, 'revitpy.json');
            const configUri = vscode.Uri.file(configPath);
            
            const configData = await vscode.workspace.fs.readFile(configUri);
            const config: RevitPyConfig = JSON.parse(configData.toString());

            // Add dependencies
            if (!config.dependencies) {
                config.dependencies = {};
            }

            for (const dep of dependencies) {
                config.dependencies[dep] = 'latest';
            }

            // Write updated config
            await vscode.workspace.fs.writeFile(
                configUri,
                Buffer.from(JSON.stringify(config, null, 2))
            );

            this.logger.info(`Added dependencies to project: ${dependencies.join(', ')}`);
        } catch (error) {
            this.logger.warn('Failed to install template dependencies', error);
        }
    }

    private async openProject(projectPath: string): Promise<void> {
        const projectUri = vscode.Uri.file(projectPath);
        await vscode.commands.executeCommand('vscode.openFolder', projectUri);
    }

    // Template content methods
    private getBasicScriptTemplate(): string {
        return `#!/usr/bin/env python3
"""
{{projectName}} - RevitPy Script
Created: {{timestamp}}
"""

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *


def main(doc):
    """Main script function."""
    print("Starting {{projectName}} script...")
    
    # Your code here
    with Transaction(doc, "{{projectName}}") as t:
        t.Start()
        
        # Example: Get all walls
        collector = FilteredElementCollector(doc)
        walls = collector.OfClass(Wall).ToElements()
        
        print(f"Found {len(walls)} walls in the model")
        
        t.Commit()
    
    print("{{projectName}} script completed successfully!")


# Entry point for Revit
if __name__ == "__main__":
    try:
        # Get the active Revit document
        doc = __revit__.ActiveUIDocument.Document
        main(doc)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
`;
    }

    private getBasicConfigTemplate(): string {
        return `{
  "name": "{{projectName}}",
  "version": "1.0.0",
  "description": "RevitPy script for {{projectName}}",
  "author": "",
  "license": "MIT",
  "entryPoint": "main.py",
  "revitVersions": ["2022", "2023", "2024"],
  "pythonVersion": "3.8",
  "dependencies": {},
  "scripts": {
    "run": "python main.py",
    "test": "python -m pytest tests/"
  }
}`;
    }

    private getBasicReadmeTemplate(): string {
        return `# {{projectName}}

A RevitPy script for Autodesk Revit.

## Description

This script demonstrates basic RevitPy functionality and can be used as a starting point for your own Revit automation.

## Installation

1. Ensure RevitPy is installed and configured
2. Open this folder in VS Code with the RevitPy extension
3. Connect to Revit using the RevitPy connection panel

## Usage

1. Open a Revit document
2. Run the script using F5 or the "Run Script in Revit" command
3. Check the output for results

## Requirements

- Autodesk Revit 2022 or later
- RevitPy runtime environment

## License

MIT License - see LICENSE file for details.
`;
    }

    private getAddinCommandsTemplate(): string {
        return `"""
{{projectName}} - Revit Add-in Commands
"""

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
from Autodesk.Revit.Attributes import *


[Transaction(TransactionMode.Manual)]
[Regeneration(RegenerationOption.Manual)]
class {{projectName}}Command(IExternalCommand):
    """Main command for {{projectName}} add-in."""
    
    def Execute(self, commandData, message, elements):
        """Execute the command."""
        try:
            ui_doc = commandData.Application.ActiveUIDocument
            doc = ui_doc.Document
            
            # Show dialog
            from .ui.dialog import {{projectName}}Dialog
            dialog = {{projectName}}Dialog()
            result = dialog.ShowDialog()
            
            if result == True:
                # Process dialog results
                self.process_command(doc, dialog.get_parameters())
                
            return Result.Succeeded
            
        except Exception as e:
            message.Value = str(e)
            return Result.Failed
    
    def process_command(self, doc, parameters):
        """Process the command with given parameters."""
        with Transaction(doc, "{{projectName}} Operation") as t:
            t.Start()
            
            # Your command logic here
            TaskDialog.Show("{{projectName}}", "Command executed successfully!")
            
            t.Commit()


[Transaction(TransactionMode.ReadOnly)]
class {{projectName}}InfoCommand(IExternalCommand):
    """Info command for {{projectName}} add-in."""
    
    def Execute(self, commandData, message, elements):
        """Show add-in information."""
        try:
            info_text = "{{projectName}}\\n\\nVersion: 1.0.0\\nAuthor: Your Name"
            TaskDialog.Show("About {{projectName}}", info_text)
            return Result.Succeeded
        except Exception as e:
            message.Value = str(e)
            return Result.Failed
`;
    }

    private getAddinDialogTemplate(): string {
        return `"""
{{projectName}} - UI Dialog
"""

import clr
clr.AddReference('PresentationCore')
clr.AddReference('PresentationFramework')
clr.AddReference('WindowsBase')

from System.Windows import Window, MessageBox
from System.Windows.Controls import Button, TextBox, Label, StackPanel
from System.Windows.Controls.Primitives import ButtonBase


class {{projectName}}Dialog(Window):
    """Main dialog for {{projectName}} add-in."""
    
    def __init__(self):
        """Initialize the dialog."""
        self.Title = "{{projectName}}"
        self.Width = 400
        self.Height = 300
        self.WindowStartupLocation = WindowStartupLocation.CenterScreen
        
        self.parameters = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        main_panel = StackPanel()
        main_panel.Margin = Thickness(20)
        
        # Title
        title_label = Label()
        title_label.Content = "{{projectName}} Settings"
        title_label.FontSize = 16
        title_label.FontWeight = FontWeights.Bold
        main_panel.Children.Add(title_label)
        
        # Parameter input
        param_label = Label()
        param_label.Content = "Parameter Value:"
        main_panel.Children.Add(param_label)
        
        self.param_textbox = TextBox()
        self.param_textbox.Text = "Default Value"
        self.param_textbox.Margin = Thickness(0, 0, 0, 10)
        main_panel.Children.Add(self.param_textbox)
        
        # Buttons
        button_panel = StackPanel()
        button_panel.Orientation = Orientation.Horizontal
        button_panel.HorizontalAlignment = HorizontalAlignment.Right
        
        ok_button = Button()
        ok_button.Content = "OK"
        ok_button.Width = 80
        ok_button.Margin = Thickness(0, 0, 10, 0)
        ok_button.Click += self.ok_button_click
        button_panel.Children.Add(ok_button)
        
        cancel_button = Button()
        cancel_button.Content = "Cancel"
        cancel_button.Width = 80
        cancel_button.Click += self.cancel_button_click
        button_panel.Children.Add(cancel_button)
        
        main_panel.Children.Add(button_panel)
        
        self.Content = main_panel
    
    def ok_button_click(self, sender, e):
        """Handle OK button click."""
        self.parameters['parameter_value'] = self.param_textbox.Text
        self.DialogResult = True
        self.Close()
    
    def cancel_button_click(self, sender, e):
        """Handle Cancel button click."""
        self.DialogResult = False
        self.Close()
    
    def get_parameters(self):
        """Get dialog parameters."""
        return self.parameters
`;
    }

    private getGeometryUtilsTemplate(): string {
        return `"""
{{projectName}} - Geometry Utilities
"""

import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import *
import math


class GeometryUtils:
    """Utility functions for geometry operations."""
    
    @staticmethod
    def distance_between_points(point1, point2):
        """Calculate distance between two XYZ points."""
        return point1.DistanceTo(point2)
    
    @staticmethod
    def midpoint(point1, point2):
        """Get midpoint between two XYZ points."""
        return XYZ(
            (point1.X + point2.X) / 2,
            (point1.Y + point2.Y) / 2,
            (point1.Z + point2.Z) / 2
        )
    
    @staticmethod
    def angle_between_vectors(vector1, vector2):
        """Calculate angle between two XYZ vectors in radians."""
        dot_product = vector1.DotProduct(vector2)
        magnitude1 = vector1.GetLength()
        magnitude2 = vector2.GetLength()
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
        
        cos_angle = dot_product / (magnitude1 * magnitude2)
        cos_angle = max(-1, min(1, cos_angle))  # Clamp to avoid numerical errors
        
        return math.acos(cos_angle)
    
    @staticmethod
    def point_on_line(start_point, end_point, parameter):
        """Get a point on line at given parameter (0.0 to 1.0)."""
        direction = end_point.Subtract(start_point)
        return start_point.Add(direction.Multiply(parameter))
    
    @staticmethod
    def transform_point(point, transform):
        """Apply transform to a point."""
        return transform.OfPoint(point)
    
    @staticmethod
    def create_transform(origin, x_axis, y_axis):
        """Create a transform from origin and axes."""
        z_axis = x_axis.CrossProduct(y_axis).Normalize()
        
        transform = Transform.Identity
        transform.Origin = origin
        transform.BasisX = x_axis.Normalize()
        transform.BasisY = y_axis.Normalize()
        transform.BasisZ = z_axis
        
        return transform
`;
    }

    private getAddinManifestTemplate(): string {
        return `<?xml version="1.0" encoding="utf-8"?>
<RevitAddIns>
  <AddIn Type="Command">
    <Name>{{projectName}}</Name>
    <Assembly>{{projectName}}.dll</Assembly>
    <AddInId>{{projectName}}-GUID-HERE</AddInId>
    <FullClassName>{{projectName}}.{{projectName}}Command</FullClassName>
    <Text>{{projectName}}</Text>
    <Description>{{projectName}} add-in for Revit</Description>
    <VendorId>YOUR-VENDOR-ID</VendorId>
    <VendorDescription>Your Company</VendorDescription>
    <VisibilityMode>AlwaysVisible</VisibilityMode>
  </AddIn>
</RevitAddIns>
`;
    }

    private getAddinConfigTemplate(): string {
        return `{
  "name": "{{projectName}}",
  "version": "1.0.0",
  "description": "Revit add-in for {{projectName}}",
  "author": "",
  "license": "MIT",
  "entryPoint": "src/commands.py",
  "revitVersions": ["2022", "2023", "2024"],
  "pythonVersion": "3.8",
  "dependencies": {
    "revitpy-ui": "latest",
    "revitpy-utils": "latest"
  },
  "scripts": {
    "build": "python build.py",
    "install": "python install.py",
    "test": "python -m pytest tests/"
  }
}`;
    }

    private getAddinReadmeTemplate(): string {
        return `# {{projectName}} Revit Add-in

A comprehensive Revit add-in built with RevitPy.

## Features

- Custom UI dialogs
- Geometry utilities
- Transaction management
- Error handling

## Installation

1. Build the add-in using \`npm run build\`
2. Install to Revit using \`npm run install\`
3. Restart Revit to load the add-in

## Development

1. Open in VS Code with RevitPy extension
2. Connect to Revit for live debugging
3. Use F5 to test commands

## Structure

- \`src/commands.py\` - Main command classes
- \`src/ui/\` - User interface components
- \`src/utils/\` - Utility functions
- \`resources/\` - Icons and resources
- \`manifest.addin\` - Revit add-in manifest

## License

MIT License
`;
    }

    private getExportToolTemplate(): string {
        return `#!/usr/bin/env python3
"""
{{projectName}} - Data Export Tool
"""

import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import *
import json
import csv
import os
from datetime import datetime


class DataExporter:
    """Export Revit data to various formats."""
    
    def __init__(self, doc):
        self.doc = doc
        self.output_dir = "output"
        self.load_config()
    
    def load_config(self):
        """Load export configuration."""
        config_path = "config/export_config.json"
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except:
            self.config = self.get_default_config()
    
    def get_default_config(self):
        """Get default export configuration."""
        return {
            "export_formats": ["json", "csv"],
            "include_parameters": True,
            "include_geometry": False,
            "categories": ["Walls", "Doors", "Windows"],
            "custom_parameters": []
        }
    
    def export_elements(self):
        """Export elements based on configuration."""
        results = {}
        
        for category_name in self.config["categories"]:
            try:
                category = self.get_category_by_name(category_name)
                if category:
                    elements = self.collect_elements_by_category(category)
                    results[category_name] = self.process_elements(elements)
            except Exception as e:
                print(f"Error exporting {category_name}: {e}")
        
        self.save_results(results)
        return results
    
    def get_category_by_name(self, name):
        """Get BuiltInCategory by name."""
        category_map = {
            "Walls": BuiltInCategory.OST_Walls,
            "Doors": BuiltInCategory.OST_Doors,
            "Windows": BuiltInCategory.OST_Windows,
            "Floors": BuiltInCategory.OST_Floors,
            "Ceilings": BuiltInCategory.OST_Ceilings
        }
        return category_map.get(name)
    
    def collect_elements_by_category(self, category):
        """Collect elements by category."""
        collector = FilteredElementCollector(self.doc)
        return collector.OfCategory(category).WhereElementIsNotElementType().ToElements()
    
    def process_elements(self, elements):
        """Process elements for export."""
        processed = []
        
        for element in elements:
            element_data = {
                "id": element.Id.IntegerValue,
                "name": element.Name,
                "category": element.Category.Name if element.Category else "Unknown"
            }
            
            if self.config["include_parameters"]:
                element_data["parameters"] = self.get_element_parameters(element)
            
            if self.config["include_geometry"]:
                element_data["geometry"] = self.get_element_geometry(element)
            
            processed.append(element_data)
        
        return processed
    
    def get_element_parameters(self, element):
        """Get element parameters."""
        parameters = {}
        
        for param in element.Parameters:
            try:
                param_name = param.Definition.Name
                param_value = self.get_parameter_value(param)
                parameters[param_name] = param_value
            except:
                continue
        
        return parameters
    
    def get_parameter_value(self, param):
        """Get parameter value as string."""
        if param.HasValue:
            if param.StorageType == StorageType.String:
                return param.AsString()
            elif param.StorageType == StorageType.Integer:
                return param.AsInteger()
            elif param.StorageType == StorageType.Double:
                return param.AsDouble()
            elif param.StorageType == StorageType.ElementId:
                return param.AsElementId().IntegerValue
        return None
    
    def get_element_geometry(self, element):
        """Get basic geometry information."""
        try:
            bbox = element.get_BoundingBox(None)
            if bbox:
                return {
                    "min": {"x": bbox.Min.X, "y": bbox.Min.Y, "z": bbox.Min.Z},
                    "max": {"x": bbox.Max.X, "y": bbox.Max.Y, "z": bbox.Max.Z}
                }
        except:
            pass
        return None
    
    def save_results(self, results):
        """Save results to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        if "json" in self.config["export_formats"]:
            json_file = f"{self.output_dir}/export_{timestamp}.json"
            with open(json_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Exported to: {json_file}")
        
        if "csv" in self.config["export_formats"]:
            for category, elements in results.items():
                csv_file = f"{self.output_dir}/{category}_{timestamp}.csv"
                self.save_to_csv(elements, csv_file)
                print(f"Exported to: {csv_file}")
    
    def save_to_csv(self, elements, filename):
        """Save elements to CSV file."""
        if not elements:
            return
        
        # Get all unique keys
        fieldnames = set()
        for element in elements:
            fieldnames.update(element.keys())
            if "parameters" in element:
                fieldnames.update(element["parameters"].keys())
        
        fieldnames = sorted(list(fieldnames))
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for element in elements:
                row = {}
                for field in fieldnames:
                    if field in element:
                        if field == "parameters" and isinstance(element[field], dict):
                            continue
                        row[field] = element[field]
                    elif "parameters" in element and field in element["parameters"]:
                        row[field] = element["parameters"][field]
                writer.writerow(row)


def main(doc):
    """Main export function."""
    print("Starting {{projectName}} export...")
    
    exporter = DataExporter(doc)
    results = exporter.export_elements()
    
    total_elements = sum(len(elements) for elements in results.values())
    print(f"Export completed! Processed {total_elements} elements.")


# Entry point for Revit
if __name__ == "__main__":
    try:
        doc = __revit__.ActiveUIDocument.Document
        main(doc)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
`;
    }

    private getExportConfigTemplate(): string {
        return `{
  "export_formats": ["json", "csv"],
  "include_parameters": true,
  "include_geometry": false,
  "categories": [
    "Walls",
    "Doors", 
    "Windows",
    "Floors"
  ],
  "custom_parameters": [
    "Mark",
    "Comments",
    "Phase Created"
  ],
  "output_settings": {
    "timestamp_format": "%Y%m%d_%H%M%S",
    "include_ids": true,
    "include_categories": true
  }
}`;
    }

    private getUtilityConfigTemplate(): string {
        return `{
  "name": "{{projectName}}",
  "version": "1.0.0",
  "description": "Data export utility for Revit",
  "author": "",
  "license": "MIT",
  "entryPoint": "export_tool.py",
  "revitVersions": ["2022", "2023", "2024"],
  "pythonVersion": "3.8",
  "dependencies": {
    "revitpy-utils": "latest"
  },
  "scripts": {
    "export": "python export_tool.py",
    "test": "python -m pytest tests/"
  }
}`;
    }

    private getTestElementsTemplate(): string {
        return `"""
Tests for element operations
"""

import pytest
import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import *


class TestElements:
    """Test element-related functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # This would typically get a test document
        pass
    
    def test_collect_walls(self):
        """Test wall collection."""
        # Mock test - in real scenario you'd need a test document
        assert True, "Wall collection test placeholder"
    
    def test_element_parameters(self):
        """Test parameter access."""
        assert True, "Parameter test placeholder"
    
    def test_element_geometry(self):
        """Test geometry access."""
        assert True, "Geometry test placeholder"
    
    @pytest.mark.parametrize("category", [
        BuiltInCategory.OST_Walls,
        BuiltInCategory.OST_Doors,
        BuiltInCategory.OST_Windows
    ])
    def test_category_collection(self, category):
        """Test collection by category."""
        assert True, f"Category {category} collection test placeholder"
`;
    }

    private getTestGeometryTemplate(): string {
        return `"""
Tests for geometry operations
"""

import pytest
import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import *
import math


class TestGeometry:
    """Test geometry utility functions."""
    
    def test_xyz_creation(self):
        """Test XYZ point creation."""
        point = XYZ(1.0, 2.0, 3.0)
        assert point.X == 1.0
        assert point.Y == 2.0
        assert point.Z == 3.0
    
    def test_distance_calculation(self):
        """Test distance between points."""
        p1 = XYZ(0, 0, 0)
        p2 = XYZ(3, 4, 0)
        distance = p1.DistanceTo(p2)
        assert abs(distance - 5.0) < 1e-10
    
    def test_vector_operations(self):
        """Test vector operations."""
        v1 = XYZ(1, 0, 0)
        v2 = XYZ(0, 1, 0)
        
        dot_product = v1.DotProduct(v2)
        assert abs(dot_product) < 1e-10
        
        cross_product = v1.CrossProduct(v2)
        expected = XYZ(0, 0, 1)
        assert abs(cross_product.X - expected.X) < 1e-10
        assert abs(cross_product.Y - expected.Y) < 1e-10
        assert abs(cross_product.Z - expected.Z) < 1e-10
    
    def test_transform_operations(self):
        """Test transform operations."""
        transform = Transform.Identity
        point = XYZ(1, 2, 3)
        
        transformed = transform.OfPoint(point)
        assert transformed.IsAlmostEqualTo(point)
`;
    }

    private getTestFixturesTemplate(): string {
        return `{
  "test_walls": [
    {
      "id": 12345,
      "name": "Test Wall 1",
      "length": 10.0,
      "height": 3.0
    },
    {
      "id": 12346,
      "name": "Test Wall 2", 
      "length": 8.0,
      "height": 3.0
    }
  ],
  "test_parameters": {
    "Mark": "A001",
    "Comments": "Test element",
    "Length": 10.0,
    "Height": 3.0
  }
}`;
    }

    private getTestRunnerTemplate(): string {
        return `#!/usr/bin/env python3
"""
{{projectName}} - Test Runner
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import pytest


def run_tests():
    """Run all tests."""
    print("Running {{projectName}} tests...")
    
    # Configure pytest
    args = [
        "-v",
        "--tb=short",
        "tests/"
    ]
    
    # Run tests
    result = pytest.main(args)
    
    if result == 0:
        print("All tests passed!")
    else:
        print(f"Tests failed with code: {result}")
    
    return result


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
`;
    }

    private getTestConfigTemplate(): string {
        return `{
  "name": "{{projectName}}",
  "version": "1.0.0",
  "description": "Test suite for Revit API functionality",
  "author": "",
  "license": "MIT",
  "entryPoint": "run_tests.py",
  "revitVersions": ["2022", "2023", "2024"],
  "pythonVersion": "3.8",
  "dependencies": {
    "pytest": "latest",
    "revitpy-utils": "latest"
  },
  "devDependencies": {
    "pytest-cov": "latest",
    "pytest-html": "latest"
  },
  "scripts": {
    "test": "python run_tests.py",
    "test-coverage": "pytest --cov=src tests/",
    "test-html": "pytest --html=reports/report.html tests/"
  }
}`;
    }

    getAvailableTemplates(): ProjectTemplate[] {
        return [...this.templates];
    }

    dispose(): void {
        // Cleanup if needed
    }
}
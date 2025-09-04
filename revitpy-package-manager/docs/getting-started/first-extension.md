# Building Your First Revit Extension

In this tutorial, we'll create a complete Revit extension with a user interface, demonstrating the full capabilities of RevitPy Package Manager. By the end, you'll have a working extension that adds custom functionality to Revit's ribbon.

!!! info "Prerequisites"
    Before starting, ensure you've completed:
    
    - [Installation Guide](installation.md)
    - [Quick Start Guide](quickstart.md)
    
    **Time required**: 30-45 minutes

## 🎯 What We'll Build

We're creating "Room Area Calculator" - a Revit extension that:

- ✅ Adds a custom ribbon tab and panel
- ✅ Displays a WPF dialog for user interaction
- ✅ Calculates total area of selected rooms
- ✅ Exports results to Excel
- ✅ Handles errors gracefully
- ✅ Follows RevitPy best practices

## Step 1: Project Setup

### Create the Environment

```bash
# Create a new environment for our extension
revitpy-install env create room-calculator --revit-version 2024

# Activate the environment
revitpy-install env activate room-calculator

# Install required packages
revitpy-install install revitpy-core revitpy-ui revitpy-excel
```

### Initialize the Package

```bash
# Create project directory
mkdir revit-room-calculator
cd revit-room-calculator

# Initialize with UI extension template
revitpy-build init --template ui-extension --name revit-room-calculator --author "Your Name"
```

This creates a complete extension structure:

```
revit-room-calculator/
├── pyproject.toml
├── README.md
├── src/
│   └── revit_room_calculator/
│       ├── __init__.py
│       ├── main.py           # Entry point
│       ├── commands/         # Revit commands
│       │   ├── __init__.py
│       │   └── calculate_areas.py
│       ├── ui/               # User interface
│       │   ├── __init__.py
│       │   ├── dialogs/
│       │   └── resources/
│       ├── utils/            # Utilities
│       │   ├── __init__.py
│       │   └── excel_export.py
│       └── ribbon/           # Ribbon configuration
│           ├── __init__.py
│           └── config.yaml
├── resources/                # Images, icons, etc.
├── tests/
└── docs/
```

## Step 2: Implement the Core Command

Edit `src/revit_room_calculator/commands/calculate_areas.py`:

```python
"""Room area calculation command."""

from typing import List, Optional
import clr

# Import Revit API
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import (
    Transaction, 
    FilteredElementCollector, 
    BuiltInCategory,
    Room,
    UnitUtils,
    UnitTypeId
)
from Autodesk.Revit.UI import (
    IExternalCommand,
    TaskDialog,
    TaskDialogType,
    Result
)

from ..ui.dialogs.area_calculator_dialog import AreaCalculatorDialog
from ..utils.excel_export import ExcelExporter


class CalculateRoomAreasCommand(IExternalCommand):
    """Command to calculate and display room areas."""
    
    def Execute(self, commandData, message, elements):
        """Execute the room area calculation command."""
        
        try:
            # Get Revit application and document
            uiapp = commandData.Application
            uidoc = uiapp.ActiveUIDocument
            doc = uidoc.Document
            
            # Get all rooms in the document
            rooms = self._get_all_rooms(doc)
            
            if not rooms:
                TaskDialog.Show(
                    "No Rooms Found",
                    "No rooms were found in the current document. "
                    "Please ensure rooms are placed and try again.",
                    TaskDialogType.TaskDialogType_Ok
                )
                return Result.Cancelled
            
            # Show the area calculator dialog
            dialog = AreaCalculatorDialog(rooms)
            dialog_result = dialog.ShowDialog()
            
            if dialog_result:
                # User clicked OK, get selected rooms and options
                selected_rooms = dialog.get_selected_rooms()
                export_to_excel = dialog.should_export_to_excel()
                
                if selected_rooms:
                    # Calculate areas
                    total_area, room_data = self._calculate_areas(selected_rooms, doc)
                    
                    # Show results
                    self._show_results(total_area, len(selected_rooms))
                    
                    # Export to Excel if requested
                    if export_to_excel:
                        exporter = ExcelExporter()
                        exporter.export_room_data(room_data)
            
            return Result.Succeeded
            
        except Exception as ex:
            message = f"An error occurred: {str(ex)}"
            TaskDialog.Show("Error", message, TaskDialogType.TaskDialogType_Ok)
            return Result.Failed
    
    def _get_all_rooms(self, doc) -> List[Room]:
        """Get all rooms in the document."""
        collector = FilteredElementCollector(doc)
        rooms = collector.OfCategory(BuiltInCategory.OST_Rooms).ToElements()
        
        # Filter out unbounded/unplaced rooms
        valid_rooms = [room for room in rooms if room.Area > 0]
        
        return valid_rooms
    
    def _calculate_areas(self, rooms: List[Room], doc) -> tuple:
        """Calculate total area and prepare room data."""
        total_area = 0.0
        room_data = []
        
        for room in rooms:
            # Get room area (convert from internal units to square feet)
            area_sqft = UnitUtils.ConvertFromInternalUnits(
                room.Area, 
                UnitTypeId.SquareFeet
            )
            
            room_info = {
                'id': room.Id.IntegerValue,
                'name': room.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() or "Unnamed",
                'number': room.get_Parameter(BuiltInParameter.ROOM_NUMBER).AsString() or "",
                'area_sqft': round(area_sqft, 2),
                'level': room.Level.Name if room.Level else "Unknown"
            }
            
            room_data.append(room_info)
            total_area += area_sqft
        
        return round(total_area, 2), room_data
    
    def _show_results(self, total_area: float, room_count: int):
        """Show calculation results to user."""
        message = (
            f"Room Area Calculation Complete!\n\n"
            f"Rooms Processed: {room_count}\n"
            f"Total Area: {total_area:,.2f} sq ft\n"
            f"Average Area: {total_area/room_count:,.2f} sq ft per room"
        )
        
        TaskDialog.Show(
            "Calculation Results", 
            message,
            TaskDialogType.TaskDialogType_Ok
        )
```

## Step 3: Create the User Interface

Create `src/revit_room_calculator/ui/dialogs/area_calculator_dialog.py`:

```python
"""WPF dialog for room area calculation."""

import clr
from typing import List, Optional

# WPF references
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore") 
clr.AddReference("WindowsBase")
clr.AddReference("System.Xaml")

from System.Windows import (
    Window, 
    Application,
    WindowStartupLocation,
    WindowStyle
)
from System.Windows.Controls import (
    Grid, 
    Button, 
    Label, 
    CheckBox,
    ListView,
    StackPanel,
    DockPanel
)
from System.Windows.Controls.Primitives import UniformGrid


class AreaCalculatorDialog(Window):
    """Dialog for selecting rooms and calculation options."""
    
    def __init__(self, rooms: List):
        """Initialize the dialog with available rooms."""
        self.rooms = rooms
        self.selected_rooms = []
        self.export_to_excel = False
        self.result = False
        
        self._initialize_ui()
    
    def _initialize_ui(self):
        """Set up the user interface."""
        # Window properties
        self.Title = "Room Area Calculator"
        self.Width = 500
        self.Height = 600
        self.WindowStartupLocation = WindowStartupLocation.CenterScreen
        self.WindowStyle = WindowStyle.SingleBorderWindow
        
        # Create main grid
        main_grid = Grid()
        self.Content = main_grid
        
        # Define grid structure
        main_grid.RowDefinitions.Add(RowDefinition(Height=GridLength.Auto))  # Header
        main_grid.RowDefinitions.Add(RowDefinition(Height=GridLength.Star))  # Room list  
        main_grid.RowDefinitions.Add(RowDefinition(Height=GridLength.Auto))  # Options
        main_grid.RowDefinitions.Add(RowDefinition(Height=GridLength.Auto))  # Buttons
        
        # Header
        header_label = Label()
        header_label.Content = "Select rooms to include in area calculation:"
        header_label.FontSize = 14
        header_label.FontWeight = FontWeights.Bold
        header_label.Margin = Thickness(10)
        Grid.SetRow(header_label, 0)
        main_grid.Children.Add(header_label)
        
        # Room selection list
        self.room_listview = self._create_room_list()
        Grid.SetRow(self.room_listview, 1)
        main_grid.Children.Add(self.room_listview)
        
        # Options panel
        options_panel = self._create_options_panel()
        Grid.SetRow(options_panel, 2)
        main_grid.Children.Add(options_panel)
        
        # Button panel
        button_panel = self._create_button_panel()
        Grid.SetRow(button_panel, 3)
        main_grid.Children.Add(button_panel)
    
    def _create_room_list(self) -> ListView:
        """Create the room selection list."""
        listview = ListView()
        listview.Margin = Thickness(10)
        listview.SelectionMode = SelectionMode.Multiple
        
        # Add rooms to the list
        for room in self.rooms:
            room_name = room.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() or "Unnamed"
            room_number = room.get_Parameter(BuiltInParameter.ROOM_NUMBER).AsString() or ""
            
            display_text = f"{room_number} - {room_name}" if room_number else room_name
            
            listview.Items.Add(RoomListItem(room, display_text))
        
        # Select all by default
        listview.SelectAll()
        
        return listview
    
    def _create_options_panel(self) -> StackPanel:
        """Create the options panel."""
        panel = StackPanel()
        panel.Margin = Thickness(10)
        panel.Orientation = Orientation.Vertical
        
        # Export to Excel option
        self.excel_checkbox = CheckBox()
        self.excel_checkbox.Content = "Export results to Excel"
        self.excel_checkbox.IsChecked = True
        panel.Children.Add(self.excel_checkbox)
        
        return panel
    
    def _create_button_panel(self) -> UniformGrid:
        """Create the button panel."""
        panel = UniformGrid()
        panel.Rows = 1
        panel.Columns = 3
        panel.Margin = Thickness(10)
        
        # Select All button
        select_all_btn = Button()
        select_all_btn.Content = "Select All"
        select_all_btn.Margin = Thickness(5)
        select_all_btn.Click += self._on_select_all_click
        panel.Children.Add(select_all_btn)
        
        # Calculate button (OK)
        calculate_btn = Button()
        calculate_btn.Content = "Calculate Areas"
        calculate_btn.IsDefault = True
        calculate_btn.Margin = Thickness(5)
        calculate_btn.Click += self._on_calculate_click
        panel.Children.Add(calculate_btn)
        
        # Cancel button
        cancel_btn = Button()
        cancel_btn.Content = "Cancel"
        cancel_btn.IsCancel = True
        cancel_btn.Margin = Thickness(5)
        cancel_btn.Click += self._on_cancel_click
        panel.Children.Add(cancel_btn)
        
        return panel
    
    def _on_select_all_click(self, sender, e):
        """Handle select all button click."""
        self.room_listview.SelectAll()
    
    def _on_calculate_click(self, sender, e):
        """Handle calculate button click."""
        # Get selected rooms
        self.selected_rooms = [
            item.room for item in self.room_listview.SelectedItems
        ]
        
        # Get export option
        self.export_to_excel = bool(self.excel_checkbox.IsChecked)
        
        # Set result and close
        self.result = True
        self.Close()
    
    def _on_cancel_click(self, sender, e):
        """Handle cancel button click."""
        self.result = False
        self.Close()
    
    def get_selected_rooms(self) -> List:
        """Get the list of selected rooms."""
        return self.selected_rooms
    
    def should_export_to_excel(self) -> bool:
        """Check if results should be exported to Excel."""
        return self.export_to_excel


class RoomListItem:
    """Item for the room list view."""
    
    def __init__(self, room, display_text: str):
        self.room = room
        self.display_text = display_text
    
    def __str__(self):
        return self.display_text
```

## Step 4: Excel Export Utility

Create `src/revit_room_calculator/utils/excel_export.py`:

```python
"""Excel export functionality."""

import os
from datetime import datetime
from typing import List, Dict
import clr

# Excel interop references
try:
    clr.AddReference("Microsoft.Office.Interop.Excel")
    from Microsoft.Office.Interop import Excel
    EXCEL_AVAILABLE = True
except:
    EXCEL_AVAILABLE = False

from System.IO import Path
from System.Environment import GetFolderPath, SpecialFolder


class ExcelExporter:
    """Export room data to Excel."""
    
    def __init__(self):
        """Initialize the Excel exporter."""
        if not EXCEL_AVAILABLE:
            raise ImportError(
                "Excel is not available. Please install Microsoft Office to use Excel export features."
            )
    
    def export_room_data(self, room_data: List[Dict]) -> str:
        """Export room data to an Excel file.
        
        Args:
            room_data: List of room dictionaries with area information
            
        Returns:
            Path to the created Excel file
        """
        
        # Create Excel application
        excel_app = Excel.ApplicationClass()
        excel_app.Visible = False
        excel_app.DisplayAlerts = False
        
        try:
            # Create a new workbook
            workbook = excel_app.Workbooks.Add()
            worksheet = workbook.ActiveSheet
            worksheet.Name = "Room Areas"
            
            # Set up headers
            headers = ["Room ID", "Room Number", "Room Name", "Level", "Area (sq ft)"]
            for i, header in enumerate(headers, 1):
                worksheet.Cells[1, i] = header
                worksheet.Cells[1, i].Font.Bold = True
            
            # Add room data
            for row_idx, room in enumerate(room_data, 2):
                worksheet.Cells[row_idx, 1] = room['id']
                worksheet.Cells[row_idx, 2] = room['number']
                worksheet.Cells[row_idx, 3] = room['name']
                worksheet.Cells[row_idx, 4] = room['level']
                worksheet.Cells[row_idx, 5] = room['area_sqft']
            
            # Add totals row
            total_row = len(room_data) + 3
            worksheet.Cells[total_row, 4] = "Total:"
            worksheet.Cells[total_row, 4].Font.Bold = True
            
            # Sum formula for total area
            sum_range = f"E2:E{len(room_data) + 1}"
            worksheet.Cells[total_row, 5] = f"=SUM({sum_range})"
            worksheet.Cells[total_row, 5].Font.Bold = True
            
            # Auto-fit columns
            worksheet.Columns.AutoFit()
            
            # Save the file
            desktop_path = GetFolderPath(SpecialFolder.Desktop)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"Room_Areas_{timestamp}.xlsx"
            file_path = Path.Combine(desktop_path, file_name)
            
            workbook.SaveAs(file_path)
            workbook.Close()
            
            return file_path
            
        finally:
            # Clean up Excel objects
            excel_app.Quit()
            
            # Release COM objects
            if 'worksheet' in locals():
                System.Runtime.InteropServices.Marshal.ReleaseComObject(worksheet)
            if 'workbook' in locals():
                System.Runtime.InteropServices.Marshal.ReleaseComObject(workbook)
            System.Runtime.InteropServices.Marshal.ReleaseComObject(excel_app)
```

## Step 5: Ribbon Configuration

Create `src/revit_room_calculator/ribbon/config.yaml`:

```yaml
ribbon:
  tab:
    name: "RevitPy Tools"
    panels:
      - name: "Room Analysis"
        buttons:
          - name: "Calculate Areas"
            text: "Room\nAreas"
            tooltip: "Calculate total area of selected rooms"
            large_image: "room_calculator_32x32.png"
            small_image: "room_calculator_16x16.png" 
            command_class: "revit_room_calculator.commands.calculate_areas.CalculateRoomAreasCommand"
            assembly: "RevitRoomCalculator.dll"
            availability_class: "revit_room_calculator.availability.RoomCalculatorAvailability"
```

## Step 6: Build and Test

### Build the Package

```bash
# Validate package structure
revitpy-build validate .

# Build the package
revitpy-build package --source .

# Install for testing
revitpy-install install dist/revit-room-calculator-0.1.0.tar.gz
```

### Test in Revit

1. **Start Revit** with your environment activated
2. **Open a project** with rooms
3. **Look for the "RevitPy Tools" tab** in the ribbon
4. **Click "Room Areas"** button
5. **Select rooms** in the dialog
6. **Click "Calculate Areas"** to see results

## Step 7: Package for Distribution

### Add Documentation

Edit `README.md` with usage instructions:

```markdown
# Revit Room Calculator

A RevitPy extension for calculating room areas with Excel export capabilities.

## Features

- Calculate total area of selected rooms
- Export results to Excel
- User-friendly interface
- Error handling and validation

## Usage

1. Open a Revit project with rooms
2. Go to RevitPy Tools > Room Analysis
3. Click "Room Areas"
4. Select rooms to include in calculation
5. Choose export options
6. Click "Calculate Areas"

## Requirements

- Revit 2021 or later
- RevitPy Package Manager
- Microsoft Excel (for export features)
```

### Create Tests

Edit `tests/test_main.py`:

```python
"""Tests for room calculator functionality."""

import pytest
from unittest.mock import Mock, patch

from revit_room_calculator.commands.calculate_areas import CalculateRoomAreasCommand


class TestCalculateRoomAreasCommand:
    """Test the main command functionality."""
    
    def test_command_creation(self):
        """Test command can be created."""
        command = CalculateRoomAreasCommand()
        assert command is not None
    
    def test_get_all_rooms_filters_valid_rooms(self):
        """Test that only rooms with area > 0 are returned."""
        command = CalculateRoomAreasCommand()
        
        # Mock document and rooms
        mock_doc = Mock()
        mock_room_valid = Mock()
        mock_room_valid.Area = 100.0
        mock_room_invalid = Mock()
        mock_room_invalid.Area = 0.0
        
        with patch('FilteredElementCollector') as mock_collector:
            mock_collector.return_value.OfCategory.return_value.ToElements.return_value = [
                mock_room_valid, mock_room_invalid
            ]
            
            rooms = command._get_all_rooms(mock_doc)
            
            assert len(rooms) == 1
            assert rooms[0] == mock_room_valid


def test_excel_exporter_requires_excel():
    """Test that ExcelExporter raises error when Excel not available."""
    with patch('revit_room_calculator.utils.excel_export.EXCEL_AVAILABLE', False):
        from revit_room_calculator.utils.excel_export import ExcelExporter
        
        with pytest.raises(ImportError):
            ExcelExporter()
```

### Sign and Publish

```bash
# Sign the package (if you have signing keys)
revitpy-build sign dist/revit-room-calculator-0.1.0.tar.gz --key signing.pem

# Publish to registry (requires authentication)
revitpy-build publish dist/revit-room-calculator-0.1.0.tar.gz
```

## 🎉 Congratulations!

You've successfully created a complete Revit extension with RevitPy Package Manager! Your extension includes:

✅ **Professional UI** with WPF dialogs  
✅ **Revit Integration** with ribbon customization  
✅ **Data Export** capabilities to Excel  
✅ **Error Handling** for robust operation  
✅ **Testing** for quality assurance  
✅ **Documentation** for users  

## 🚀 Next Steps

Now that you have a working extension:

1. **[Development Setup](development-setup.md)** - Optimize your development environment
2. **[UI Development Tutorial](../tutorials/ui-development.md)** - Learn advanced UI techniques
3. **[Testing & Debugging](../tutorials/testing-debugging.md)** - Master testing strategies
4. **[Package Management](../tutorials/package-management.md)** - Advanced package management

## 💡 Ideas for Enhancement

Consider adding these features to make your extension even better:

- **3D Visualization** of room boundaries
- **PDF Reports** with room layouts  
- **Room Comparison** tools
- **Historical Data** tracking
- **Custom Calculations** (area per person, etc.)

## 🤝 Need Help?

- 📚 [Best Practices Guide](../guides/best-practices.md)
- 🔧 [Troubleshooting](../guides/troubleshooting.md)
- 💬 [Community Forum](https://forum.revitpy.dev)
- 💭 [Discord](https://discord.gg/revitpy)
"""Main script entry point for {{ cookiecutter.project_name }}."""

import revitpy
from revitpy import Transaction, TaskDialog
from revitpy.api import Element, FilteredElementCollector


def run() -> None:
    """Main function to run the RevitPy script."""
    with revitpy.transaction("{{ cookiecutter.project_name }}"):
        try:
            # Get the active document
            doc = revitpy.doc
            if not doc:
                TaskDialog.show("Error", "No active Revit document found.")
                return
            
            # Example: Count all walls in the project
            wall_count = count_walls()
            
            # Show result to user
            TaskDialog.show(
                "{{ cookiecutter.project_name }}", 
                f"Found {wall_count} walls in the project."
            )
            
        except Exception as e:
            TaskDialog.show("Error", f"An error occurred: {str(e)}")
            raise


def count_walls() -> int:
    """Count all walls in the active document.
    
    Returns:
        Number of walls found
    """
    # Get all wall elements
    walls = FilteredElementCollector(revitpy.doc) \
        .OfCategory(revitpy.BuiltInCategory.OST_Walls) \
        .WhereElementIsNotElementType() \
        .ToElements()
    
    return len(walls)


def get_selected_elements() -> list[Element]:
    """Get currently selected elements.
    
    Returns:
        List of selected elements
    """
    selection = revitpy.uidoc.Selection
    element_ids = selection.GetElementIds()
    
    return [revitpy.doc.GetElement(element_id) for element_id in element_ids]


def example_element_modification() -> None:
    """Example function showing how to modify elements."""
    selected_elements = get_selected_elements()
    
    if not selected_elements:
        TaskDialog.show("Info", "Please select elements first.")
        return
    
    with Transaction(revitpy.doc, "Modify Elements") as tx:
        tx.Start()
        
        try:
            for element in selected_elements:
                # Example: Add a comment parameter
                comment_param = element.get_Parameter(revitpy.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
                if comment_param and not comment_param.IsReadOnly:
                    comment_param.Set(f"Modified by {{ cookiecutter.project_name }}")
            
            tx.Commit()
            
        except Exception as e:
            tx.RollBack()
            raise e


if __name__ == "__main__":
    # This allows the script to be run directly for testing
    run()
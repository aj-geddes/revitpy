# Tutorial 1: Your First RevitPy Script

Welcome to RevitPy! In this tutorial, you'll create and run your first RevitPy script in under 15 minutes. By the end, you'll have a working script that queries walls in your Revit model and displays information about them.

## 📋 Overview

**Learning Objectives:**
- Set up your first RevitPy project
- Understand the basic RevitPy structure
- Query Revit elements using the modern ORM syntax
- Run scripts within Revit and see results

**Prerequisites:**
- RevitPy installed ([installation guide](../getting-started/installation.md))
- Revit 2022 or later
- VS Code with RevitPy extension (recommended)
- Basic Python knowledge

**Estimated Time:** 15 minutes

**Files Needed:**
- [Basic Building Model](https://github.com/highvelocitysolutions/revitpy/releases/download/tutorials/basic-building.rvt) (optional)
- Any Revit model with walls will work

## 🛠️ Step 1: Create Your First Project

Let's create a new RevitPy project using the CLI:

```bash
# Create a new project directory
mkdir my-first-revitpy-script
cd my-first-revitpy-script

# Initialize a new RevitPy project
revitpy create . --template basic-script --name "My First Script"
```

This creates the following project structure:

```
my-first-revitpy-script/
├── src/
│   └── main.py              # Your main script
├── tests/
│   └── test_main.py         # Unit tests
├── pyproject.toml           # Project configuration
├── README.md                # Project documentation
└── .revitpy/               # RevitPy configuration
    └── config.yaml
```

### Understanding the Project Structure

- **`src/main.py`** - Your main script file where the magic happens
- **`pyproject.toml`** - Python project configuration with dependencies
- **`.revitpy/config.yaml`** - RevitPy-specific settings like target Revit versions
- **`tests/`** - Unit tests for your script (we'll cover testing in later tutorials)

## 🛠️ Step 2: Write Your First Script

Open `src/main.py` in VS Code and replace the template code with our first script:

```python title="src/main.py"
"""
My First RevitPy Script
=======================

This script demonstrates basic RevitPy functionality:
- Connecting to the active Revit document
- Querying walls using the ORM layer
- Displaying element information
"""

from revitpy import RevitContext

def main():
    """Main script entry point."""
    print("🚀 Starting My First RevitPy Script...")

    # Create a RevitContext to interact with Revit
    with RevitContext() as context:
        print(f"✅ Connected to document: {context.get_active_document().Title}")

        # Query all walls in the model
        walls = context.elements.of_category('Walls')
        wall_count = len(walls)

        print(f"🧱 Found {wall_count} walls in the model")

        if wall_count == 0:
            print("⚠️  No walls found. Try opening a model with walls.")
            return

        # Display information about the first 5 walls
        print("\n📋 Wall Information:")
        print("=" * 50)

        for i, wall in enumerate(walls.take(5), 1):
            wall_name = wall.Name or f"Wall-{wall.Id}"
            wall_height = wall.get_parameter('Height').AsDouble()
            wall_length = wall.get_parameter('Length').AsDouble()
            wall_area = wall.get_parameter('Area').AsDouble()

            print(f"{i}. {wall_name}")
            print(f"   Height: {wall_height:.1f} ft")
            print(f"   Length: {wall_length:.1f} ft")
            print(f"   Area: {wall_area:.1f} sq ft")
            print(f"   ID: {wall.Id}")
            print()

        if wall_count > 5:
            print(f"... and {wall_count - 5} more walls")

    print("✨ Script completed successfully!")

if __name__ == "__main__":
    main()
```

### 💡 Code Explanation

Let's break down what this script does:

1. **Import RevitContext**: This is the main entry point for all RevitPy operations
2. **Context Manager**: `with RevitContext() as context:` ensures proper resource cleanup
3. **Query Elements**: `context.elements.of_category('Walls')` uses the ORM to find all walls
4. **Access Properties**: `.get_parameter('Height')` retrieves wall parameters
5. **Iterate Results**: Loop through walls and display information

## 🛠️ Step 3: Configure Your Development Environment

Before running the script, let's set up VS Code for the best development experience:

### Install VS Code Extension
If you haven't already, install the RevitPy extension:

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "RevitPy"
4. Click "Install"

### Configure Project Settings
Open `.revitpy/config.yaml` and verify the settings:

```yaml title=".revitpy/config.yaml"
# RevitPy Project Configuration
project:
  name: "My First Script"
  version: "0.1.0"
  description: "My first RevitPy automation script"

# Target Revit versions
revit:
  versions: ["2022", "2023", "2024", "2025"]
  min_version: "2022"

# Development settings
development:
  auto_reload: true
  show_console: true
  debug_mode: true

# Script configuration
script:
  entry_point: "src/main.py"
  timeout: 30
```

## 🛠️ Step 4: Run Your Script

Now for the exciting part - running your first RevitPy script!

### Option 1: Run from VS Code (Recommended)

1. **Open Revit** and load any model with walls (or create a few walls)
2. **Open your project** in VS Code (`File > Open Folder`)
3. **Open main.py** in the editor
4. **Press F5** or use the RevitPy: Run Script command
5. **Watch the magic happen** in the Revit console and VS Code terminal

### Option 2: Run from Command Line

```bash
# Navigate to your project directory
cd my-first-revitpy-script

# Run the script
revitpy run src/main.py

# Or run in development mode with hot reload
revitpy dev --watch
```

### Option 3: Run from Revit Console

1. Open Revit and go to the RevitPy console (Extensions tab > RevitPy Console)
2. Navigate to your script file
3. Click "Run Script" or press Ctrl+Enter

## 📊 Expected Output

When your script runs successfully, you should see output like this:

```
🚀 Starting My First RevitPy Script...
✅ Connected to document: Basic Building Model
🧱 Found 12 walls in the model

📋 Wall Information:
==================================================
1. Basic Wall: Generic - 8"
   Height: 9.0 ft
   Length: 20.0 ft
   Area: 180.0 sq ft
   ID: 12345

2. Basic Wall: Generic - 8"
   Height: 9.0 ft
   Length: 30.0 ft
   Area: 270.0 sq ft
   ID: 12346

3. Basic Wall: Generic - 8"
   Height: 9.0 ft
   Length: 20.0 ft
   Area: 180.0 sq ft
   ID: 12347

4. Basic Wall: Generic - 8"
   Height: 9.0 ft
   Length: 30.0 ft
   Area: 270.0 sq ft
   ID: 12348

5. Basic Wall: Generic - 8"
   Height: 12.0 ft
   Length: 40.0 ft
   Area: 480.0 sq ft
   ID: 12349

... and 7 more walls
✨ Script completed successfully!
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### "No walls found" Message
**Problem**: Script finds 0 walls
**Solutions**:
- Make sure your Revit model contains walls
- Try creating a few walls manually in Revit
- Verify you have the correct model open

#### "RevitContext not found" Error
**Problem**: RevitPy not properly connected to Revit
**Solutions**:
```bash
# Verify installation
revitpy doctor

# Check if Revit add-in is loaded
# Look for RevitPy in Revit's External Tools tab
```

#### "Permission denied" Error
**Problem**: Script can't access Revit API
**Solutions**:
- Run VS Code as Administrator (Windows)
- Make sure Revit is running and has a document open
- Check that RevitPy add-in is enabled in Revit

#### Scripts Runs But No Output
**Problem**: Script executes but no console output appears
**Solutions**:
- Enable console output in RevitPy settings
- Check the VS Code terminal output
- Look for errors in Revit's error log

### Debug Mode
Enable debug mode for more detailed information:

```python title="src/main.py"
import logging
from revitpy import RevitContext

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    logger.debug("Starting script execution")

    with RevitContext() as context:
        logger.debug(f"Context created: {context}")
        # ... rest of your code
```

## 💡 Key Concepts Learned

### 1. RevitContext
The `RevitContext` is your gateway to the Revit API. It:
- Manages connections to the active Revit document
- Provides access to elements through the ORM layer
- Handles resource cleanup automatically
- Enables transaction management

### 2. Element Queries
RevitPy uses LINQ-style syntax for querying elements:
```python
# Get all walls
walls = context.elements.of_category('Walls')

# Filter walls by height
tall_walls = walls.where(lambda w: w.Height > 10.0)

# Take only first 5 results
first_five = walls.take(5)
```

### 3. Parameter Access
Access element parameters using friendly names:
```python
height = wall.get_parameter('Height').AsDouble()
name = wall.Name
area = wall.get_parameter('Area').AsDouble()
```

### 4. Resource Management
Always use `with` statements for proper cleanup:
```python
# Good - automatic cleanup
with RevitContext() as context:
    # Do work here
    pass

# Bad - manual cleanup required
context = RevitContext()
# Do work here
context.dispose()  # Easy to forget!
```

## 🚀 Exercises

Try these additional exercises to reinforce your learning:

### Exercise 1: Count Different Categories
Modify your script to count elements in different categories:

```python
categories = ['Walls', 'Doors', 'Windows', 'Floors', 'Rooms']

for category in categories:
    elements = context.elements.of_category(category)
    count = len(elements)
    print(f"{category}: {count} elements")
```

### Exercise 2: Filter by Properties
Find only walls above a certain height:

```python
tall_walls = (context.elements
              .of_category('Walls')
              .where(lambda w: w.Height > 10.0)
              .to_list())

print(f"Found {len(tall_walls)} walls taller than 10 feet")
```

### Exercise 3: Calculate Totals
Calculate the total wall area in your model:

```python
walls = context.elements.of_category('Walls')
total_area = sum(wall.get_parameter('Area').AsDouble() for wall in walls)
print(f"Total wall area: {total_area:.1f} square feet")
```

## 📚 Next Steps

Congratulations! You've successfully created and run your first RevitPy script. You've learned:

- ✅ How to set up a RevitPy project
- ✅ Basic RevitContext usage
- ✅ Element querying with the ORM layer
- ✅ Parameter access patterns
- ✅ Running scripts in different environments

### Continue Learning
Ready for the next tutorial? Continue with:

- **[Tutorial 2: Working with Elements](working-with-elements.md)** - Learn advanced element manipulation
- **[Getting Started Guide](../getting-started/quickstart.md)** - Review fundamental concepts
- **[VS Code Extension Guide](../getting-started/vscode-setup.md)** - Master the development environment

### Join the Community
- **💬 Discord**: Share your first script in [#beginners](https://discord.gg/revitpy)
- **📸 Social**: Tweet your progress with #RevitPyFirstScript
- **⭐ GitHub**: Star the project if you found this helpful

### What's Coming Next
In the next tutorial, you'll learn:
- Advanced element filtering and querying
- Modifying element properties
- Working with transactions
- Error handling best practices
- Performance optimization tips

Ready to continue? Let's dive deeper into [Working with Elements](working-with-elements.md)!

---

!!! success "Tutorial Complete! 🎉"

    You've successfully completed your first RevitPy tutorial. Take a moment to celebrate - you're now part of the modern Revit automation community!

    **Achievement Unlocked:** RevitPy First Steps 🌟

    Ready for more? The next tutorial builds on what you've learned here and introduces more powerful features.

---

### Tutorial Feedback

How was this tutorial? Help us improve:

<iframe src="https://feedback.revitpy.dev/tutorial-01" width="100%" height="200" frameborder="0"></iframe>

Or send feedback to [tutorials@revitpy.dev](mailto:tutorials@revitpy.dev)

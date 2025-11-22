---
layout: default
title: PyRevit Integration
description: Complete guide to integrating RevitPy with PyRevit. Learn hybrid development patterns, data sharing, and best practices for using both frameworks together.
permalink: /pyrevit-integration/
---

<div class="container" markdown="1">
<div class="main-content" markdown="1">

<div class="page-header">
      <h1 class="page-title">PyRevit Integration</h1>
      <p class="page-description">
        RevitPy complements PyRevit rather than replacing it. Learn how to use both frameworks together for powerful hybrid workflows.
      </p>
    </div>

## Philosophy

RevitPy and PyRevit excel in different areas. Use this guide to understand when to use each:

| Capability | PyRevit | RevitPy | Recommendation |
|------------|---------|---------|----------------|
| UI Panels & Buttons | Excellent | Complex setup | **Use PyRevit** |
| Basic Automation | Perfect | Overkill | **Use PyRevit** |
| Data Science | Not possible | Full support | **Use RevitPy** |
| Machine Learning | No support | All frameworks | **Use RevitPy** |
| Async/Cloud | Limited | Modern async | **Use RevitPy** |
| Quick Scripts | Fast iteration | More setup | **Use PyRevit** |

## Hybrid Architecture

The most powerful approach combines both frameworks:

```
┌─────────────────────────────────────────┐
│          PyRevit Extension              │
│  ┌─────────────────────────────────┐    │
│  │    UI Layer (PyRevit)           │    │
│  │  • Ribbon panels & buttons      │    │
│  │  • Selection dialogs            │    │
│  │  • Progress indicators          │    │
│  └──────────────┬──────────────────┘    │
│                 │                        │
│  ┌──────────────▼──────────────────┐    │
│  │   Analytics Layer (RevitPy)     │    │
│  │  • Data processing              │    │
│  │  • ML models                    │    │
│  │  • Cloud APIs                   │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## Installation

### Install Both Frameworks

```bash
# Install PyRevit (via pyRevit CLI or installer)
# https://pyrevitlabs.io

# Install RevitPy
pip install revitpy
revitpy doctor --install
```

### Configure Shared Path

Add RevitPy to PyRevit's Python path in your extension:

```python
# In your PyRevit script
import sys
sys.path.append(r'C:\Users\{user}\AppData\Local\RevitPy\lib')

# Now you can import RevitPy modules
import revitpy_analytics
```

## Pattern 1: PyRevit UI + RevitPy Analytics

The most common pattern: PyRevit handles the UI, RevitPy does heavy computation.

### PyRevit Button Script

```python
# script.py - PyRevit pushbutton script
from pyrevit import forms, script, revit

# Import RevitPy analytics module
import sys
sys.path.append(r'C:\RevitPy\analytics')
import thermal_analysis

# Get user selection
selection = forms.SelectFromList.show(
    ['Walls', 'Windows', 'All Envelope'],
    title='Select Elements to Analyze',
    button_name='Analyze'
)

if not selection:
    script.exit()

# Get elements based on selection
doc = revit.doc
if selection == 'Walls':
    elements = revit.query.get_elements_by_category('Walls')
elif selection == 'Windows':
    elements = revit.query.get_elements_by_category('Windows')
else:
    elements = revit.query.get_elements_by_categories(['Walls', 'Windows'])

# Run RevitPy analysis
output = script.get_output()
output.print_md("# Thermal Analysis Results")

with forms.ProgressBar(title='Analyzing...') as pb:
    results = thermal_analysis.analyze_envelope(
        elements,
        progress_callback=lambda p: pb.update_progress(p)
    )

# Display results
output.print_md("## Summary")
output.print_md(f"**Total Elements:** {results['count']}")
output.print_md(f"**Average U-value:** {results['avg_u_value']:.3f} W/m²K")
output.print_md(f"**Total Heat Loss:** {results['total_loss']:.0f} W")

# Show chart
output.print_md("## Heat Loss by Element")
chart = output.make_bar_chart()
for item in results['by_element'][:10]:
    chart.data.append(item['heat_loss'])
    chart.labels.append(item['name'][:20])
chart.draw()

# Recommendations
output.print_md("## Recommendations")
for rec in results['recommendations']:
    output.print_md(f"- {rec}")
```

### RevitPy Analytics Module

```python
# thermal_analysis.py - RevitPy module
import numpy as np
from revitpy import RevitContext

def analyze_envelope(element_ids, progress_callback=None):
    """Analyze thermal performance of building envelope."""
    with RevitContext() as context:
        results = {
            'count': len(element_ids),
            'by_element': [],
            'recommendations': []
        }

        total = len(element_ids)
        for i, elem_id in enumerate(element_ids):
            elem = context.get_element(elem_id)

            # Calculate U-value
            u_value = calculate_u_value(elem)
            heat_loss = u_value * elem.Area * 20

            results['by_element'].append({
                'id': elem_id,
                'name': elem.Name,
                'u_value': u_value,
                'heat_loss': heat_loss
            })

            if progress_callback:
                progress_callback(int((i + 1) / total * 100))

        # Calculate statistics
        u_values = [r['u_value'] for r in results['by_element']]
        results['avg_u_value'] = np.mean(u_values)
        results['total_loss'] = sum(r['heat_loss'] for r in results['by_element'])

        # Sort by heat loss
        results['by_element'].sort(key=lambda x: x['heat_loss'], reverse=True)

        # Generate recommendations
        if results['avg_u_value'] > 0.35:
            results['recommendations'].append(
                "Consider upgrading insulation - average U-value exceeds 0.35 W/m²K"
            )

        worst = results['by_element'][0]
        if worst['heat_loss'] > 1000:
            results['recommendations'].append(
                f"Priority upgrade: {worst['name']} contributes {worst['heat_loss']:.0f}W heat loss"
            )

        return results

def calculate_u_value(element):
    """Calculate U-value from element construction."""
    layers = element.get_construction_layers()
    total_r = sum(layer.thickness / layer.conductivity for layer in layers)
    return 1 / total_r if total_r > 0 else 1.0
```

## Pattern 2: Shared Data Bridge

Create a shared data layer that both frameworks can access.

### Data Bridge Module

```python
# revitpy_bridge.py - Shared between PyRevit and RevitPy
import json
import tempfile
from pathlib import Path

class DataBridge:
    """Share data between PyRevit and RevitPy."""

    def __init__(self, session_id=None):
        self.session_id = session_id or self._get_session_id()
        self.data_dir = Path(tempfile.gettempdir()) / 'revitpy_bridge'
        self.data_dir.mkdir(exist_ok=True)

    def _get_session_id(self):
        """Get unique session ID for current Revit instance."""
        import hashlib
        # Use document path as session identifier
        return hashlib.md5(str(Path.cwd()).encode()).hexdigest()[:8]

    def save(self, key, data):
        """Save data to bridge."""
        filepath = self.data_dir / f"{self.session_id}_{key}.json"
        with open(filepath, 'w') as f:
            json.dump(data, f)

    def load(self, key, default=None):
        """Load data from bridge."""
        filepath = self.data_dir / f"{self.session_id}_{key}.json"
        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
        return default

    def clear(self, key=None):
        """Clear bridge data."""
        if key:
            filepath = self.data_dir / f"{self.session_id}_{key}.json"
            filepath.unlink(missing_ok=True)
        else:
            for f in self.data_dir.glob(f"{self.session_id}_*.json"):
                f.unlink()
```

### Usage in PyRevit

```python
# PyRevit script
from revitpy_bridge import DataBridge

bridge = DataBridge()

# Save selection for RevitPy processing
selected_ids = [e.Id.IntegerValue for e in selection]
bridge.save('selected_elements', selected_ids)

# Trigger RevitPy processing
import subprocess
subprocess.run(['revitpy', 'run', 'process_selection.py'])

# Load results
results = bridge.load('analysis_results')
if results:
    # Display in PyRevit output
    for item in results:
        output.print_md(f"- {item['name']}: {item['value']}")
```

### Usage in RevitPy

```python
# process_selection.py - RevitPy script
from revitpy import RevitContext
from revitpy_bridge import DataBridge

bridge = DataBridge()

# Load selection from PyRevit
element_ids = bridge.load('selected_elements', [])

with RevitContext() as context:
    results = []
    for elem_id in element_ids:
        elem = context.get_element(elem_id)
        # Process element...
        results.append({
            'name': elem.Name,
            'value': calculated_value
        })

    # Save results for PyRevit
    bridge.save('analysis_results', results)
```

## Pattern 3: Event Coordination

Coordinate events between both frameworks.

```python
# PyRevit event handler
from pyrevit import HOST_APP
from pyrevit.coreutils import envvars

def on_document_changed(sender, args):
    """Notify RevitPy of document changes."""
    changed_ids = [e.IntegerValue for e in args.GetModifiedElementIds()]

    # Signal RevitPy via environment variable
    envvars.set_pyrevit_env_var(
        'REVITPY_MODIFIED_ELEMENTS',
        ','.join(map(str, changed_ids))
    )

# Register event
HOST_APP.app.DocumentChanged += on_document_changed
```

```python
# RevitPy listener
import os
from revitpy import RevitContext
from revitpy.events import on_external_event

@on_external_event('PYREVIT_MODIFIED')
def handle_pyrevit_changes():
    """Handle changes from PyRevit."""
    modified = os.environ.get('REVITPY_MODIFIED_ELEMENTS', '')
    if not modified:
        return

    element_ids = [int(x) for x in modified.split(',')]

    with RevitContext() as context:
        for elem_id in element_ids:
            elem = context.get_element(elem_id)
            # Update analytics, sync to cloud, etc.
```

## Best Practices

### Do's

- **Use PyRevit for UI**: Leverage PyRevit's excellent UI capabilities
- **Use RevitPy for computation**: Heavy processing, ML, data science
- **Share data carefully**: Use the bridge pattern for data exchange
- **Keep both updated**: Maintain compatibility between versions
- **Document integration points**: Make it clear where each framework is used

### Don'ts

- **Don't duplicate functionality**: Pick the right tool for each task
- **Don't mix transaction styles**: Use one framework's transactions at a time
- **Don't assume imports**: Always check paths and dependencies
- **Don't ignore errors**: Both frameworks have different error handling

## Migration Strategy

If you're transitioning from PyRevit to RevitPy:

### Phase 1: Add RevitPy for Analytics
Keep existing PyRevit UI, add RevitPy for data processing.

### Phase 2: Hybrid Operations
Gradually move complex logic to RevitPy while keeping PyRevit UI.

### Phase 3: Full RevitPy (Optional)
For new projects, consider full RevitPy if you need:
- Complex UI with web technologies
- Full async operations
- Enterprise deployment features

## Example Projects

### Thermal Analysis Extension

Complete example of a PyRevit extension with RevitPy analytics:

[View on GitHub](https://github.com/revitpy/examples/tree/main/pyrevit-thermal-analysis)

### BIM Quality Checker

Quality checking with PyRevit UI and RevitPy ML classification:

[View on GitHub](https://github.com/revitpy/examples/tree/main/pyrevit-quality-checker)

## Troubleshooting

<div class="callout callout-warning">
  <div class="callout-title">Import Errors</div>
  <p>If you get import errors, ensure RevitPy's path is added before importing:</p>
  <pre><code>import sys
sys.path.insert(0, r'C:\Users\{user}\AppData\Local\RevitPy\lib')</code></pre>
</div>

<div class="callout callout-warning">
  <div class="callout-title">Transaction Conflicts</div>
  <p>Don't nest transactions from different frameworks. Complete PyRevit transactions before starting RevitPy transactions.</p>
</div>

<div class="callout callout-info">
  <div class="callout-title">Need Help?</div>
  <p>Join the <a href="https://github.com/revitpy/revitpy/discussions">discussions</a> for integration questions and to share your patterns.</p>
</div>

</div>
</div>

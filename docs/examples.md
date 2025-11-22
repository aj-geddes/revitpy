---
layout: default
title: Examples
description: Real-world RevitPy examples covering energy analysis, machine learning, IoT integration, data export, automated modeling, and more.
permalink: /examples/
---

<div class="container" markdown="1">
<div class="main-content" markdown="1">

<div class="page-header">
      <h1 class="page-title">Examples</h1>
      <p class="page-description">
        Learn from real-world examples that demonstrate RevitPy's capabilities across different use cases and industries.
      </p>
    </div>

<div class="examples-grid">
  <a href="#energy-analysis" class="example-card">
    <div class="example-icon">&#9889;</div>
    <h3 class="example-title">Energy Analysis</h3>
    <p class="example-description">
      Analyze building thermal performance with U-value calculations, heat loss modeling, and energy optimization recommendations.
    </p>
    <div class="example-tags">
      <span class="example-tag">NumPy</span>
      <span class="example-tag">Analytics</span>
      <span class="example-tag">HVAC</span>
    </div>
  </a>

  <a href="#ml-classification" class="example-card">
    <div class="example-icon">&#129302;</div>
    <h3 class="example-title">ML Element Classification</h3>
    <p class="example-description">
      Use machine learning to automatically classify and tag Revit elements based on geometry and parameters.
    </p>
    <div class="example-tags">
      <span class="example-tag">TensorFlow</span>
      <span class="example-tag">scikit-learn</span>
      <span class="example-tag">AI</span>
    </div>
  </a>

  <a href="#iot-monitoring" class="example-card">
    <div class="example-icon">&#128225;</div>
    <h3 class="example-title">IoT Sensor Integration</h3>
    <p class="example-description">
      Connect live sensor data to Revit elements for real-time building performance monitoring and visualization.
    </p>
    <div class="example-tags">
      <span class="example-tag">MQTT</span>
      <span class="example-tag">WebSocket</span>
      <span class="example-tag">Real-time</span>
    </div>
  </a>

  <a href="#data-export" class="example-card">
    <div class="example-icon">&#128202;</div>
    <h3 class="example-title">Advanced Data Export</h3>
    <p class="example-description">
      Export model data to Excel, JSON, databases, or BI tools with custom formatting and transformations.
    </p>
    <div class="example-tags">
      <span class="example-tag">Pandas</span>
      <span class="example-tag">Excel</span>
      <span class="example-tag">SQL</span>
    </div>
  </a>

  <a href="#automated-modeling" class="example-card">
    <div class="example-icon">&#127959;</div>
    <h3 class="example-title">Automated Modeling</h3>
    <p class="example-description">
      Generate Revit elements from external data sources like CSV, databases, or APIs.
    </p>
    <div class="example-tags">
      <span class="example-tag">Automation</span>
      <span class="example-tag">Generation</span>
      <span class="example-tag">API</span>
    </div>
  </a>

  <a href="#clash-detection" class="example-card">
    <div class="example-icon">&#128295;</div>
    <h3 class="example-title">Clash Detection</h3>
    <p class="example-description">
      Identify and report geometry clashes between elements with detailed reports and visualization.
    </p>
    <div class="example-tags">
      <span class="example-tag">BIM</span>
      <span class="example-tag">QA</span>
      <span class="example-tag">Coordination</span>
    </div>
  </a>

  <a href="#cloud-sync" class="example-card">
    <div class="example-icon">&#9729;</div>
    <h3 class="example-title">Cloud Synchronization</h3>
    <p class="example-description">
      Sync model data with cloud services like Azure, AWS, or custom REST APIs for collaboration.
    </p>
    <div class="example-tags">
      <span class="example-tag">Azure</span>
      <span class="example-tag">REST</span>
      <span class="example-tag">Async</span>
    </div>
  </a>

  <a href="#schedule-generation" class="example-card">
    <div class="example-icon">&#128203;</div>
    <h3 class="example-title">Dynamic Schedules</h3>
    <p class="example-description">
      Generate and update schedules programmatically with custom calculations and formatting.
    </p>
    <div class="example-tags">
      <span class="example-tag">Schedules</span>
      <span class="example-tag">Reports</span>
      <span class="example-tag">BOQ</span>
    </div>
  </a>
</div>

---

## Energy Analysis {#energy-analysis}

Analyze building thermal performance and generate optimization recommendations.

```python
import numpy as np
from revitpy import RevitContext

def analyze_thermal_performance():
    """Calculate U-values and identify poorly insulated elements."""
    with RevitContext() as context:
        # Get all walls with thermal properties
        walls = (context.elements
            .of_category('Walls')
            .where(lambda w: w.get_parameter('Thermal Mass'))
            .to_list())

        results = []
        for wall in walls:
            # Calculate U-value from construction layers
            layers = wall.get_construction_layers()
            total_r = sum(layer.thickness / layer.conductivity
                         for layer in layers)
            u_value = 1 / total_r

            # Calculate heat loss
            area = wall.Area
            heat_loss = u_value * area * 20  # Assume 20°C difference

            results.append({
                'name': wall.Name,
                'area': area,
                'u_value': u_value,
                'heat_loss': heat_loss
            })

        # Find worst performers
        results.sort(key=lambda x: x['heat_loss'], reverse=True)

        print("Top 5 Heat Loss Contributors:")
        for r in results[:5]:
            print(f"  {r['name']}: {r['heat_loss']:.1f} W")

        # Calculate building totals
        total_loss = sum(r['heat_loss'] for r in results)
        avg_u = np.mean([r['u_value'] for r in results])

        print(f"\nTotal Heat Loss: {total_loss:.0f} W")
        print(f"Average U-value: {avg_u:.3f} W/m²K")

if __name__ == "__main__":
    analyze_thermal_performance()
```

---

## ML Element Classification {#ml-classification}

Automatically classify elements using machine learning.

```python
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from revitpy import RevitContext

def classify_elements():
    """Use ML to classify elements based on geometry."""
    with RevitContext() as context:
        # Collect training data from tagged elements
        elements = context.elements.where(
            lambda e: e.get_parameter('Classification')
        ).to_list()

        # Extract features
        X = []
        y = []
        for elem in elements:
            features = [
                elem.BoundingBox.Volume,
                elem.BoundingBox.Width,
                elem.BoundingBox.Height,
                elem.BoundingBox.Depth,
            ]
            X.append(features)
            y.append(elem.get_parameter('Classification').value)

        # Train classifier
        clf = RandomForestClassifier(n_estimators=100)
        clf.fit(np.array(X), y)

        # Classify untagged elements
        untagged = context.elements.where(
            lambda e: not e.get_parameter('Classification')
        ).to_list()

        print(f"Classifying {len(untagged)} elements...")

        with context.transaction("Auto-classify elements"):
            for elem in untagged:
                features = [[
                    elem.BoundingBox.Volume,
                    elem.BoundingBox.Width,
                    elem.BoundingBox.Height,
                    elem.BoundingBox.Depth,
                ]]
                prediction = clf.predict(features)[0]
                confidence = clf.predict_proba(features).max()

                if confidence > 0.8:
                    elem.set_parameter('Classification', prediction)
                    print(f"  {elem.Name}: {prediction} ({confidence:.0%})")

if __name__ == "__main__":
    classify_elements()
```

---

## IoT Sensor Integration {#iot-monitoring}

Connect live sensor data to Revit elements.

```python
import asyncio
from revitpy import AsyncRevitContext
from revitpy.integrations import MQTTClient

async def monitor_sensors():
    """Stream sensor data to Revit parameters in real-time."""
    async with AsyncRevitContext() as context:
        # Connect to MQTT broker
        mqtt = MQTTClient("mqtt://sensors.building.com")
        await mqtt.connect()

        # Map sensors to Revit rooms
        room_mapping = {
            "sensor/floor1/room101": "Room 101",
            "sensor/floor1/room102": "Room 102",
            "sensor/floor2/room201": "Room 201",
        }

        async def handle_message(topic, payload):
            room_name = room_mapping.get(topic)
            if not room_name:
                return

            # Find room element
            room = context.elements.of_category('Rooms').first(
                lambda r: r.Name == room_name
            )

            if room:
                # Update parameters with sensor data
                async with context.transaction("Update sensor data"):
                    room.set_parameter('Temperature', payload['temp'])
                    room.set_parameter('Humidity', payload['humidity'])
                    room.set_parameter('CO2', payload['co2'])

                print(f"Updated {room_name}: {payload['temp']}°C")

        # Subscribe to all sensors
        for topic in room_mapping.keys():
            await mqtt.subscribe(topic, handle_message)

        # Keep running
        print("Monitoring sensors... Press Ctrl+C to stop")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(monitor_sensors())
```

---

## Advanced Data Export {#data-export}

Export model data with custom transformations.

```python
import pandas as pd
from revitpy import RevitContext

def export_to_excel():
    """Export room data with calculations to Excel."""
    with RevitContext() as context:
        rooms = context.elements.of_category('Rooms').to_list()

        # Build dataframe
        data = []
        for room in rooms:
            data.append({
                'Name': room.Name,
                'Number': room.Number,
                'Level': room.Level.Name,
                'Area (m²)': room.Area,
                'Volume (m³)': room.Volume,
                'Perimeter (m)': room.Perimeter,
                'Occupancy': room.get_parameter('Occupancy')?.value or 0,
                'Department': room.get_parameter('Department')?.value or '',
            })

        df = pd.DataFrame(data)

        # Add calculated columns
        df['Area per Person'] = df['Area (m²)'] / df['Occupancy'].replace(0, 1)
        df['Volume per Person'] = df['Volume (m³)'] / df['Occupancy'].replace(0, 1)

        # Create summary by department
        summary = df.groupby('Department').agg({
            'Area (m²)': 'sum',
            'Occupancy': 'sum',
            'Name': 'count'
        }).rename(columns={'Name': 'Room Count'})

        # Export to Excel with multiple sheets
        with pd.ExcelWriter('room_report.xlsx') as writer:
            df.to_excel(writer, sheet_name='All Rooms', index=False)
            summary.to_excel(writer, sheet_name='Department Summary')

            # Add pivot table
            pivot = pd.pivot_table(df, values='Area (m²)',
                                   index='Level', columns='Department',
                                   aggfunc='sum', fill_value=0)
            pivot.to_excel(writer, sheet_name='Area by Level')

        print(f"Exported {len(rooms)} rooms to room_report.xlsx")

if __name__ == "__main__":
    export_to_excel()
```

---

## Automated Modeling {#automated-modeling}

Generate elements from external data.

```python
import csv
from revitpy import RevitContext

def generate_from_csv():
    """Create walls from CSV coordinate data."""
    with RevitContext() as context:
        # Read wall definitions from CSV
        with open('walls.csv', 'r') as f:
            reader = csv.DictReader(f)
            walls_data = list(reader)

        # Get wall type and level
        wall_type = context.get_type('Basic Wall', 'Generic - 200mm')
        level = context.get_level('Level 1')

        created = []
        with context.transaction("Create walls from CSV"):
            for row in walls_data:
                # Parse coordinates
                start = context.create_point(
                    float(row['start_x']),
                    float(row['start_y']),
                    0
                )
                end = context.create_point(
                    float(row['end_x']),
                    float(row['end_y']),
                    0
                )

                # Create wall
                wall = context.create_wall(
                    start=start,
                    end=end,
                    wall_type=wall_type,
                    level=level,
                    height=float(row['height'])
                )

                # Set parameters
                wall.set_parameter('Mark', row['mark'])
                wall.set_parameter('Comments', row.get('comments', ''))

                created.append(wall)
                print(f"Created wall: {row['mark']}")

        print(f"\nCreated {len(created)} walls from CSV")

if __name__ == "__main__":
    generate_from_csv()
```

---

## Clash Detection {#clash-detection}

Identify geometry clashes between elements.

```python
from revitpy import RevitContext

def detect_clashes():
    """Find clashes between structural and MEP elements."""
    with RevitContext() as context:
        # Get structural elements
        structural = context.elements.of_categories([
            'Structural Columns',
            'Structural Framing',
            'Structural Foundations'
        ]).to_list()

        # Get MEP elements
        mep = context.elements.of_categories([
            'Ducts',
            'Pipes',
            'Cable Trays',
            'Conduits'
        ]).to_list()

        print(f"Checking {len(structural)} structural vs {len(mep)} MEP elements...")

        clashes = []
        for s_elem in structural:
            s_box = s_elem.BoundingBox

            for m_elem in mep:
                m_box = m_elem.BoundingBox

                # Check for intersection
                if s_box.intersects(m_box):
                    overlap = s_box.intersection_volume(m_box)
                    if overlap > 0.001:  # Min threshold
                        clashes.append({
                            'structural': s_elem,
                            'mep': m_elem,
                            'overlap': overlap,
                            'location': s_box.intersection_center(m_box)
                        })

        # Report results
        print(f"\nFound {len(clashes)} clashes:\n")

        for clash in sorted(clashes, key=lambda x: x['overlap'], reverse=True):
            print(f"Clash: {clash['structural'].Name} x {clash['mep'].Name}")
            print(f"  Overlap: {clash['overlap']:.4f} m³")
            print(f"  Location: {clash['location']}")
            print()

        # Create clash report marks
        with context.transaction("Mark clashes"):
            for i, clash in enumerate(clashes):
                clash['structural'].set_parameter('Clash_ID', f"CL-{i+1}")
                clash['mep'].set_parameter('Clash_ID', f"CL-{i+1}")

if __name__ == "__main__":
    detect_clashes()
```

---

## Cloud Synchronization {#cloud-sync}

Sync model data with cloud services.

```python
import asyncio
import httpx
from revitpy import AsyncRevitContext

async def sync_to_cloud():
    """Sync element changes to cloud API."""
    async with AsyncRevitContext() as context:
        # Configure API client
        api_url = "https://api.building-platform.com/v1"
        headers = {"Authorization": "Bearer YOUR_TOKEN"}

        async with httpx.AsyncClient() as client:
            # Get modified elements since last sync
            last_sync = context.get_setting('last_sync_time')
            modified = context.elements.where(
                lambda e: e.modified_time > last_sync
            ).to_list()

            print(f"Syncing {len(modified)} modified elements...")

            # Upload in batches
            batch_size = 50
            for i in range(0, len(modified), batch_size):
                batch = modified[i:i + batch_size]

                payload = [{
                    'revit_id': elem.Id.value,
                    'category': elem.Category,
                    'name': elem.Name,
                    'parameters': {
                        p.name: p.value
                        for p in elem.parameters
                    },
                    'geometry': elem.export_geometry('json')
                } for elem in batch]

                response = await client.post(
                    f"{api_url}/elements/sync",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()

                print(f"  Uploaded batch {i // batch_size + 1}")

            # Update sync timestamp
            context.set_setting('last_sync_time', context.now)
            print(f"\nSync complete!")

if __name__ == "__main__":
    asyncio.run(sync_to_cloud())
```

---

## Dynamic Schedules {#schedule-generation}

Generate schedules with custom calculations.

```python
from revitpy import RevitContext

def create_door_schedule():
    """Create a door schedule with fire rating summary."""
    with RevitContext() as context:
        # Get all doors
        doors = context.elements.of_category('Doors').to_list()

        with context.transaction("Create door schedule"):
            # Create schedule
            schedule = context.create_schedule(
                name="Door Fire Rating Schedule",
                category="Doors"
            )

            # Add fields
            schedule.add_field('Mark')
            schedule.add_field('Level')
            schedule.add_field('Width')
            schedule.add_field('Height')
            schedule.add_field('Fire Rating')
            schedule.add_field('Frame Type')

            # Add calculated field for area
            schedule.add_calculated_field(
                name='Area',
                formula='Width * Height',
                unit='m²'
            )

            # Group by fire rating
            schedule.group_by('Fire Rating')

            # Add sorting
            schedule.sort_by('Level', then_by='Mark')

            # Add totals
            schedule.add_total('Area', show_count=True)

            # Apply formatting
            schedule.set_column_width('Mark', 25)
            schedule.set_column_width('Fire Rating', 30)
            schedule.format_column('Area', decimals=2)

            print(f"Created schedule with {len(doors)} doors")

            # Summary
            ratings = {}
            for door in doors:
                rating = door.get_parameter('Fire Rating')?.value or 'None'
                ratings[rating] = ratings.get(rating, 0) + 1

            print("\nFire Rating Summary:")
            for rating, count in sorted(ratings.items()):
                print(f"  {rating}: {count} doors")

if __name__ == "__main__":
    create_door_schedule()
```

---

## More Examples

Explore the complete examples repository:

- [GitHub Examples](https://github.com/revitpy/revitpy/tree/main/examples) - Full source code for all examples
- [Community Examples](https://github.com/revitpy/community-examples) - User-contributed examples

<div class="callout callout-info">
  <div class="callout-title">Contribute Your Examples</div>
  <p>Have a useful example? <a href="https://github.com/revitpy/revitpy/blob/main/CONTRIBUTING.md">Contribute it</a> to help the community!</p>
</div>

</div>
</div>

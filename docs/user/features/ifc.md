---
layout: page
title: IFC Interoperability
description: Guide to IFC export, import, and element mapping with RevitPy. Covers IDS validation, BCF issue tracking, model diffing, and IFC 2x3/4/4x3 support.
doc_tier: user
---

# IFC Interoperability

RevitPy provides comprehensive IFC (Industry Foundation Classes) support through the `revitpy.ifc` module. Features include bidirectional element mapping, IFC export and import with configurable schema versions, IDS (Information Delivery Specification) validation, BCF (BIM Collaboration Format) issue management, and model diffing.

IFC functionality requires the optional `ifcopenshell` dependency. Install it with:

```bash
pip install revitpy[ifc]
```

## Checking Availability

Before using IFC features, check whether `ifcopenshell` is installed:

```python
from revitpy.ifc import ifc_available

if ifc_available():
    print("IFC support is available")
else:
    print("Install ifcopenshell: pip install revitpy[ifc]")
```

The `ifc_available()` function returns `True` when `ifcopenshell` is installed and importable.

## IfcElementMapper

`IfcElementMapper` manages bidirectional mappings between RevitPy element type names and IFC entity type names. It ships with default mappings for common building elements and supports custom registration.

### Default Mappings

The following mappings are registered automatically:

| RevitPy Type | IFC Entity Type |
|---|---|
| `WallElement` | `IfcWall` |
| `RoomElement` | `IfcSpace` |
| `DoorElement` | `IfcDoor` |
| `WindowElement` | `IfcWindow` |
| `SlabElement` | `IfcSlab` |
| `RoofElement` | `IfcRoof` |
| `ColumnElement` | `IfcColumn` |
| `BeamElement` | `IfcBeam` |
| `StairElement` | `IfcStairFlight` |
| `RailingElement` | `IfcRailing` |

### Creating a Mapper

```python
from revitpy.ifc import IfcElementMapper

mapper = IfcElementMapper()

# Inspect registered types
print(mapper.registered_types)       # ["WallElement", "RoomElement", ...]
print(mapper.registered_ifc_types)   # ["IfcWall", "IfcSpace", ...]
```

### Looking Up Mappings

```python
# RevitPy type -> IFC entity type
ifc_type = mapper.get_ifc_type("WallElement")       # "IfcWall"

# IFC entity type -> RevitPy type
revitpy_type = mapper.get_revitpy_type("IfcDoor")   # "DoorElement"

# Get the full IfcMapping dataclass
mapping = mapper.get_mapping("WallElement")
# IfcMapping(revitpy_type="WallElement", ifc_entity_type="IfcWall",
#            property_map={}, bidirectional=True)
```

### Registering Custom Mappings

Use `register_mapping` to add new type mappings or override existing ones. Property maps define how RevitPy attribute names translate to IFC property names.

```python
mapper.register_mapping(
    revitpy_type="CurtainWallElement",
    ifc_entity_type="IfcCurtainWall",
    property_map={"panel_count": "NumberOfPanels", "glazing_ratio": "GlazingAreaFraction"},
    bidirectional=True,
)

# The mapping now works in both directions
assert mapper.get_ifc_type("CurtainWallElement") == "IfcCurtainWall"
assert mapper.get_revitpy_type("IfcCurtainWall") == "CurtainWallElement"
```

Set `bidirectional=False` when you only need the RevitPy-to-IFC direction (e.g. for export-only types):

```python
mapper.register_mapping(
    revitpy_type="AnnotationElement",
    ifc_entity_type="IfcAnnotation",
    bidirectional=False,
)
```

### Converting Elements

The mapper can convert elements directly when `ifcopenshell` is available.

**RevitPy to IFC:**

```python
# Convert a RevitPy element to an IFC entity inside an ifcopenshell file
ifc_entity = mapper.to_ifc(wall_element, ifc_file, config=export_config)
```

The `to_ifc` method creates an IFC entity in the given `ifc_file`, assigns a new `GlobalId`, copies the element `name`, and applies any property mappings from the registry.

**IFC to dict:**

```python
# Convert an IFC entity to a dict representation
element_dict = mapper.from_ifc(ifc_entity)
# {"type": "WallElement", "ifc_type": "IfcWall", "global_id": "...", "name": "..."}

# With an explicit target type
element_dict = mapper.from_ifc(ifc_entity, target_type="WallElement")
```

### IfcMapping Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `revitpy_type` | `str` | -- | RevitPy element type name |
| `ifc_entity_type` | `str` | -- | IFC entity type name |
| `property_map` | `dict[str, str]` | `{}` | Maps RevitPy property names to IFC property names |
| `bidirectional` | `bool` | `True` | Whether the mapping works in both directions |

## IfcExporter

`IfcExporter` converts collections of RevitPy elements into standards-compliant IFC files.

### Export Configuration

Exports are configured through the `IfcExportConfig` dataclass:

| Field | Type | Default | Description |
|---|---|---|---|
| `version` | `IfcVersion` | `IfcVersion.IFC4` | IFC schema version |
| `include_quantities` | `bool` | `True` | Include quantity data |
| `include_materials` | `bool` | `True` | Include material data |
| `site_name` | `str` | `"Default Site"` | Name for the IfcSite entity |
| `building_name` | `str` | `"Default Building"` | Name for the IfcBuilding entity |
| `author` | `str` | `""` | Author metadata |

### Basic Export

```python
from revitpy.ifc import IfcExporter, IfcExportConfig, IfcVersion

# With defaults (IFC4)
exporter = IfcExporter()
output = exporter.export(elements, "model.ifc")

# With custom configuration
config = IfcExportConfig(
    version=IfcVersion.IFC4,
    include_quantities=True,
    include_materials=True,
    site_name="Project Site",
    building_name="Main Building",
    author="Design Team",
)
exporter = IfcExporter(config=config)
output = exporter.export(elements, "model.ifc")
```

### Specifying Schema Version

The `version` parameter on the `export` method overrides the config default:

```python
exporter = IfcExporter()

# IFC2X3 for legacy compatibility
exporter.export(elements, "model_2x3.ifc", version=IfcVersion.IFC2X3)

# IFC4 (default)
exporter.export(elements, "model_ifc4.ifc", version=IfcVersion.IFC4)

# IFC4X3 for latest standard
exporter.export(elements, "model_4x3.ifc", version=IfcVersion.IFC4X3)
```

### IfcVersion Enum

| Value | String | Description |
|---|---|---|
| `IFC2X3` | `"IFC2X3"` | Legacy IFC 2x3 schema |
| `IFC4` | `"IFC4"` | IFC 4 schema (recommended) |
| `IFC4X3` | `"IFC4X3"` | IFC 4.3 schema (latest) |

### Using a Custom Mapper

Supply a pre-configured `IfcElementMapper` to the exporter to use custom type mappings:

```python
from revitpy.ifc import IfcExporter, IfcElementMapper

mapper = IfcElementMapper()
mapper.register_mapping("CurtainWallElement", "IfcCurtainWall")

exporter = IfcExporter(mapper=mapper)
exporter.export(elements, "model.ifc")
```

The exporter's mapper is accessible via the `mapper` property:

```python
exporter.mapper.register_mapping("PipeElement", "IfcPipeSegment")
```

### Async Export

For non-blocking export with optional progress reporting:

```python
import asyncio
from revitpy.ifc import IfcExporter

exporter = IfcExporter()

def on_progress(current: int, total: int) -> None:
    print(f"Exporting {current}/{total}")

output = asyncio.run(
    exporter.export_async(elements, "model.ifc", progress=on_progress)
)
```

## IfcImporter

`IfcImporter` reads IFC files and converts their entities into RevitPy element dictionaries.

### Import Configuration

Imports are configured through the `IfcImportConfig` dataclass:

| Field | Type | Default | Description |
|---|---|---|---|
| `merge_strategy` | `str` | `"replace"` | How to handle existing elements |
| `update_existing` | `bool` | `True` | Update elements that already exist |
| `create_new` | `bool` | `True` | Create elements that do not exist |
| `property_mapping` | `dict[str, str]` | `{}` | Rename properties during import |

### Basic Import

```python
from revitpy.ifc import IfcImporter

importer = IfcImporter()
elements = importer.import_file("model.ifc")

for elem in elements:
    print(f"{elem['type']}: {elem['name']} (IFC: {elem['ifc_type']})")
```

Each imported element is a dict with at least these keys:

| Key | Description |
|---|---|
| `type` | RevitPy element type name |
| `ifc_type` | Original IFC entity type |
| `global_id` | IFC GlobalId |
| `name` | Element name |

Additional keys are added based on the mapper's property map for that type.

### Supported IFC Entity Types

The importer processes these entity types by default:

- `IfcWall`, `IfcWallStandardCase`
- `IfcDoor`, `IfcWindow`
- `IfcSlab`, `IfcRoof`
- `IfcColumn`, `IfcBeam`
- `IfcStairFlight`, `IfcRailing`
- `IfcSpace`

Unmapped entity types are skipped with a warning.

### Custom Import Configuration

Use `IfcImportConfig` to rename properties during import:

```python
from revitpy.ifc import IfcImporter, IfcImportConfig

config = IfcImportConfig(
    merge_strategy="replace",
    update_existing=True,
    create_new=True,
    property_mapping={"global_id": "revit_guid", "name": "element_name"},
)

importer = IfcImporter(config=config)
elements = importer.import_file("model.ifc")
# Elements now use "revit_guid" instead of "global_id", etc.
```

### Async Import

```python
import asyncio
from revitpy.ifc import IfcImporter

importer = IfcImporter()
elements = asyncio.run(importer.import_file_async("model.ifc"))
```

### Round-Trip Workflow

Export elements to IFC and re-import them:

```python
from revitpy.ifc import IfcExporter, IfcImporter, IfcElementMapper

# Share a mapper for consistent mappings
mapper = IfcElementMapper()

# Export
exporter = IfcExporter(mapper=mapper)
exporter.export(elements, "roundtrip.ifc")

# Import
importer = IfcImporter(mapper=mapper)
reimported = importer.import_file("roundtrip.ifc")
```

## IDS Validation

`IdsValidator` checks elements against IDS (Information Delivery Specification) requirements. This does not require `ifcopenshell` -- it works with any duck-typed element objects.

### Defining Requirements

Requirements are defined using the `IdsRequirement` dataclass:

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | -- | Requirement name |
| `description` | `str` | `""` | Human-readable description |
| `entity_type` | `str` or `None` | `None` | Apply only to this element type (or all if `None`) |
| `property_name` | `str` or `None` | `None` | Property to check |
| `property_value` | `str` or `None` | `None` | Expected value (string comparison) |
| `required` | `bool` | `True` | Whether the property must exist |

### Validating Elements Programmatically

```python
from revitpy.ifc import IdsValidator, IdsRequirement

validator = IdsValidator()

requirements = [
    IdsRequirement(
        name="Wall fire rating",
        description="All walls must have a fire rating",
        entity_type="Walls",
        property_name="fire_rating",
        required=True,
    ),
    IdsRequirement(
        name="Door width check",
        description="Doors must be at least 900mm wide",
        entity_type="Doors",
        property_name="width",
        property_value="900",
        required=True,
    ),
]

results = validator.validate(elements, requirements)

for result in results:
    status = "PASS" if result.passed else "FAIL"
    print(f"[{status}] {result.requirement.name}: {result.message}")
```

### IdsValidationResult Fields

| Field | Type | Description |
|---|---|---|
| `requirement` | `IdsRequirement` | The requirement that was checked |
| `passed` | `bool` | Whether the check passed |
| `entity_id` | `Any` or `None` | The element's ID |
| `actual_value` | `Any` or `None` | The actual property value found |
| `message` | `str` | Human-readable result message |

### Validating from a File

Requirements can be loaded from a JSON file. The file should contain a list of requirement objects:

```json
[
  {
    "name": "Wall fire rating",
    "description": "All walls must have a fire rating",
    "entity_type": "Walls",
    "property_name": "fire_rating",
    "required": true
  },
  {
    "name": "Room name required",
    "description": "All rooms must have a name",
    "entity_type": "Rooms",
    "property_name": "name",
    "required": true
  }
]
```

```python
from revitpy.ifc import IdsValidator

validator = IdsValidator()
results = validator.validate_from_file(elements, "requirements.json")

passed = sum(1 for r in results if r.passed)
total = len(results)
print(f"IDS validation: {passed}/{total} checks passed")
```

### Validation Logic

The validator applies these rules for each element/requirement pair:

1. If the requirement specifies an `entity_type` that does not match the element's type, the check passes (not applicable).
2. If no `property_name` is specified, the check passes (no property to verify).
3. If `property_name` is set and `required` is `True`, the property must exist on the element.
4. If `property_value` is also set, the actual value must match (string comparison).

## BCF Issue Management

`BcfManager` provides simplified BCF 2.1 compatible issue tracking. It supports creating issues, serializing them to BCF ZIP archives, and reading them back.

### Creating Issues

```python
from revitpy.ifc import BcfManager

bcf = BcfManager()

issue = bcf.create_issue(
    title="Missing fire rating",
    description="Wall on Level 2 is missing its fire rating property",
    author="John Smith",
    status="Open",
    assigned_to="Jane Doe",
    element_ids=["wall-001", "wall-002"],
)

print(f"Created issue: {issue.title} ({issue.guid})")
```

### BcfIssue Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `guid` | `str` | Auto-generated UUID | Unique issue identifier |
| `title` | `str` | `""` | Short issue title |
| `description` | `str` | `""` | Detailed description |
| `author` | `str` | `""` | Author name |
| `creation_date` | `datetime` | `datetime.now()` | When the issue was created |
| `status` | `str` | `"Open"` | Issue status (e.g. `"Open"`, `"Closed"`) |
| `assigned_to` | `str` | `""` | Person assigned to the issue |
| `element_ids` | `list[str]` | `[]` | Referenced element IDs |

### Writing BCF Files

Write issues to a BCF ZIP archive:

```python
# Write all managed issues
bcf.write_bcf(path="issues.bcf")

# Write a specific set of issues
bcf.write_bcf(issues=[issue], path="selected_issues.bcf")
```

The output is a ZIP archive containing an XML `markup.xml` file for each issue, organized by topic GUID.

### Reading BCF Files

Read issues from BCF ZIP archives (`.bcf`, `.bcfzip`, `.zip`) or JSON files:

```python
# Read from a BCF archive
issues = bcf.read_bcf("issues.bcf")

# Read from a JSON file
issues = bcf.read_bcf("issues.json")

for issue in issues:
    print(f"[{issue.status}] {issue.title} (assigned to: {issue.assigned_to})")
```

Read issues are also added to the manager's internal list, accessible via the `issues` property:

```python
all_issues = bcf.issues
```

### Full BCF Workflow

```python
from revitpy.ifc import BcfManager

bcf = BcfManager()

# Create issues based on validation results
bcf.create_issue(
    title="Missing fire rating on Level 2 walls",
    description="3 walls on Level 2 do not have fire_rating set",
    author="QA Script",
    status="Open",
    assigned_to="Structural Team",
    element_ids=["wall-101", "wall-102", "wall-103"],
)

bcf.create_issue(
    title="Door width non-compliant",
    description="Door D-201 is below the minimum 900mm width",
    author="QA Script",
    status="Open",
    assigned_to="Architecture Team",
    element_ids=["door-201"],
)

# Export to BCF archive
bcf.write_bcf(path="qa_issues.bcf")

# Later, read them back
bcf2 = BcfManager()
issues = bcf2.read_bcf("qa_issues.bcf")
print(f"Loaded {len(issues)} issues")
```

## IFC Diff

`IfcDiff` compares two sets of elements (or two IFC files) and produces a structured diff identifying added, modified, and removed entities.

### Comparing Element Lists

Elements are matched by their `id` or `global_id` attribute. Property-level changes are tracked for modified elements.

```python
from revitpy.ifc import IfcDiff

differ = IfcDiff()
result = differ.compare(old_elements, new_elements)

print(f"Added: {result.summary['added']}")
print(f"Modified: {result.summary['modified']}")
print(f"Removed: {result.summary['removed']}")
```

### Comparing IFC Files

Compare two IFC files directly (requires `ifcopenshell`):

```python
result = differ.compare_files("model_v1.ifc", "model_v2.ifc")
```

This imports both files via `IfcImporter` and then compares the resulting element lists.

### IfcDiffResult Structure

| Field | Type | Description |
|---|---|---|
| `added` | `list[IfcDiffEntry]` | Entities present only in the new set |
| `modified` | `list[IfcDiffEntry]` | Entities that changed between old and new |
| `removed` | `list[IfcDiffEntry]` | Entities present only in the old set |
| `summary` | `dict[str, int]` | Counts: `{"added": N, "modified": N, "removed": N}` |

### IfcDiffEntry Structure

| Field | Type | Description |
|---|---|---|
| `global_id` | `str` | Element identifier |
| `entity_type` | `str` | Element type name |
| `change_type` | `IfcChangeType` | `ADDED`, `MODIFIED`, or `REMOVED` |
| `old_properties` | `dict[str, Any]` | Properties from the old state |
| `new_properties` | `dict[str, Any]` | Properties from the new state |
| `changed_fields` | `list[str]` | Names of fields that differ (sorted) |

### IfcChangeType Enum

| Value | String | Description |
|---|---|---|
| `ADDED` | `"added"` | Entity exists only in the new state |
| `MODIFIED` | `"modified"` | Entity exists in both states with property changes |
| `REMOVED` | `"removed"` | Entity exists only in the old state |

### Inspecting Changes

```python
result = differ.compare(old_elements, new_elements)

# New elements
for entry in result.added:
    print(f"+ {entry.entity_type} ({entry.global_id})")

# Removed elements
for entry in result.removed:
    print(f"- {entry.entity_type} ({entry.global_id})")

# Modified elements with field-level detail
for entry in result.modified:
    print(f"~ {entry.entity_type} ({entry.global_id})")
    for field in entry.changed_fields:
        old_val = entry.old_properties.get(field)
        new_val = entry.new_properties.get(field)
        print(f"    {field}: {old_val} -> {new_val}")
```

## Error Handling

The IFC module defines specific exceptions for each subsystem:

| Exception | Raised By | Description |
|---|---|---|
| `IfcError` | Base class | General IFC error |
| `IfcExportError` | `IfcExporter.export`, `IfcElementMapper.to_ifc` | Export or conversion failure |
| `IfcImportError` | `IfcImporter.import_file`, `IfcElementMapper.from_ifc` | Import or reverse-mapping failure |
| `IfcValidationError` | General validation | IFC validation failure |
| `IdsValidationError` | `IdsValidator.validate_from_file` | IDS file parsing or validation failure |
| `BcfError` | `BcfManager.read_bcf`, `BcfManager.write_bcf` | BCF file read/write failure |

All IFC operations that require `ifcopenshell` will raise `ImportError` with a message directing you to install it via `pip install revitpy[ifc]`.

## Combined Workflow Example

A complete workflow using IFC export, validation, diffing, and BCF issue tracking:

```python
from revitpy.ifc import (
    IfcExporter,
    IfcImporter,
    IfcElementMapper,
    IfcExportConfig,
    IfcVersion,
    IdsValidator,
    IdsRequirement,
    BcfManager,
    IfcDiff,
)

# Set up mapper with custom types
mapper = IfcElementMapper()
mapper.register_mapping("CurtainWallElement", "IfcCurtainWall")

# Export current model
config = IfcExportConfig(
    version=IfcVersion.IFC4,
    site_name="Main Campus",
    building_name="Building A",
    author="Design Team",
)
exporter = IfcExporter(mapper=mapper, config=config)
exporter.export(elements, "model_v2.ifc")

# Validate against IDS requirements
validator = IdsValidator()
requirements = [
    IdsRequirement(
        name="Fire rating required",
        entity_type="Walls",
        property_name="fire_rating",
        required=True,
    ),
]
results = validator.validate(elements, requirements)

# Create BCF issues for failures
bcf = BcfManager()
for result in results:
    if not result.passed:
        bcf.create_issue(
            title=f"IDS failure: {result.requirement.name}",
            description=result.message,
            author="Automated QA",
            element_ids=[str(result.entity_id)] if result.entity_id else [],
        )

if bcf.issues:
    bcf.write_bcf(path="validation_issues.bcf")

# Compare against previous version
differ = IfcDiff()
diff_result = differ.compare_files("model_v1.ifc", "model_v2.ifc")
print(f"Changes: +{diff_result.summary['added']} "
      f"~{diff_result.summary['modified']} "
      f"-{diff_result.summary['removed']}")
```

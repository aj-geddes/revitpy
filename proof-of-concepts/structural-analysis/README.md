# Structural analysis

`python -m structural_analysis` · package `structural_analysis`

> Demonstration only. These are simplified elastic screening checks, **not** an
> AISC 360 / Eurocode 3 design check. They leave out lateral-torsional buckling,
> combined axial and bending, load combinations and connection design.

## What it does

1. **Reads the frame.** `poc_common` declares `StructuralColumn` and
   `StructuralFraming` element classes (RevitPy's typed API lets you add
   categories in three lines), and `api.query(StructuralFraming)` returns typed
   wrappers. `QuantityExtractor` converts each member's `Length` from feet to
   metres. `Section` names a W-shape in a small AISC table converted to SI
   (`analysis.SECTIONS`).
2. **Beam checks.** Simply supported, uniformly loaded:
   - load: (dead + live) x `Tributary Width`;
   - bending stress checked against 0.66 fy;
   - live-load deflection checked against L/360.
3. **Column checks.** Axial load is (dead + live) x `Tributary Area` for each
   floor at and above the column. Capacity is the lower of Euler buckling
   (minor axis) and squash load, divided by 1.67.
4. **Frame solve.** Builds the frame on gridline 1 from the model (bay count
   from the columns, bay width from the beam spans) and applies 1% notional
   lateral loads. It is solved with a direct-stiffness 2D frame solver in
   NumPy/SciPy, and the roof drift is compared with h/400.
5. **Modal periods.** A shear-building model uses floor mass from `Floor` areas
   and storey stiffness from the columns (12EI/h³). Periods come from
   `scipy.linalg.eigh`. They are printed next to the ASCE 7 approximate
   period. The model has no bracing or cores, so the periods are long.
6. **Steel and carbon.** Tonnage from length x section weight, and A1-A3 carbon
   from `revitpy.sustainability`.
7. **Write-back.** Each member's utilization and governing check go into
   `Comments` in one transaction.

In the demo model, two level-3 beams are W14x22 on a wider tributary width, so
they fail bending. `test_upsizing_in_a_transaction_fixes_the_failures` changes
their `Section` inside `api.transaction(...)` and re-runs the analysis.

## Model parameters used

| Parameter | Notes |
|---|---|
| `Length`, `Level`, `Comments` | built-in |
| `Section` | project parameter holding the AISC name. In Revit this is normally the family type name. Map it or change `model_data.members`. |
| `Tributary Width` (beams), `Tributary Area` (columns) | project parameters, internal units (ft, ft²) |
| `Elevation` (levels), `Area` (floors) | built-in |

## Tests

The solver is checked against closed-form results:

- cantilever tip deflection and rotation, horizontal and vertical (the vertical
  case catches transformation-matrix errors);
- axial bar extension;
- one- and two-storey shear-building periods;
- beam and column hand calculations.

## Changed from the original concept

The earlier version described FEniCS and seismic time-history analysis. It is
now an honest small direct-stiffness solver plus modal analysis in SciPy, with
no FEM framework dependency.

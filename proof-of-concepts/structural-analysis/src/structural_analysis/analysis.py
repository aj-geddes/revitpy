"""Simplified steel member checks and matrix structural analysis.

For demonstration only: the checks are elastic, allowable-stress style
screening checks, NOT a design-code verification (no AISC 360 / Eurocode 3
lateral-torsional buckling, interaction or load combinations). Section
properties are taken from the AISC shapes table and converted to SI; verify
against the current AISC Manual before relying on them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.linalg import LinAlgError, eigh, solve

# Constants
E_STEEL: float = 200e9  # Pa
FY_STEEL: float = 345e6  # Pa

# Unit conversion factors
IN2_TO_M2: float = 0.00064516
IN4_TO_M4: float = 4.162314256e-7
IN3_TO_M3: float = 1.6387064e-5
IN_TO_M: float = 0.0254
LBF_PER_FT_TO_KG_PER_M: float = 1.48816394


@dataclass(frozen=True)
class Section:
    """Steel section properties."""

    name: str
    area_m2: float
    ix_m4: float
    sx_m3: float
    r_min_m: float
    mass_kg_m: float


# Build SECTIONS from imperial data
SECTIONS: dict[str, Section] = {
    "W8x31": Section(
        name="W8x31",
        area_m2=9.13 * IN2_TO_M2,
        ix_m4=110 * IN4_TO_M4,
        sx_m3=27.5 * IN3_TO_M3,
        r_min_m=2.02 * IN_TO_M,
        mass_kg_m=31 * LBF_PER_FT_TO_KG_PER_M,
    ),
    "W10x49": Section(
        name="W10x49",
        area_m2=14.4 * IN2_TO_M2,
        ix_m4=272 * IN4_TO_M4,
        sx_m3=54.6 * IN3_TO_M3,
        r_min_m=2.54 * IN_TO_M,
        mass_kg_m=49 * LBF_PER_FT_TO_KG_PER_M,
    ),
    "W12x26": Section(
        name="W12x26",
        area_m2=7.65 * IN2_TO_M2,
        ix_m4=204 * IN4_TO_M4,
        sx_m3=33.4 * IN3_TO_M3,
        r_min_m=1.51 * IN_TO_M,
        mass_kg_m=26 * LBF_PER_FT_TO_KG_PER_M,
    ),
    "W14x22": Section(
        name="W14x22",
        area_m2=6.49 * IN2_TO_M2,
        ix_m4=199 * IN4_TO_M4,
        sx_m3=29.0 * IN3_TO_M3,
        r_min_m=1.04 * IN_TO_M,
        mass_kg_m=22 * LBF_PER_FT_TO_KG_PER_M,
    ),
    "W16x26": Section(
        name="W16x26",
        area_m2=7.68 * IN2_TO_M2,
        ix_m4=301 * IN4_TO_M4,
        sx_m3=38.4 * IN3_TO_M3,
        r_min_m=1.12 * IN_TO_M,
        mass_kg_m=26 * LBF_PER_FT_TO_KG_PER_M,
    ),
    "W18x35": Section(
        name="W18x35",
        area_m2=10.3 * IN2_TO_M2,
        ix_m4=510 * IN4_TO_M4,
        sx_m3=57.6 * IN3_TO_M3,
        r_min_m=1.22 * IN_TO_M,
        mass_kg_m=35 * LBF_PER_FT_TO_KG_PER_M,
    ),
    "W21x44": Section(
        name="W21x44",
        area_m2=13.0 * IN2_TO_M2,
        ix_m4=843 * IN4_TO_M4,
        sx_m3=81.6 * IN3_TO_M3,
        r_min_m=1.26 * IN_TO_M,
        mass_kg_m=44 * LBF_PER_FT_TO_KG_PER_M,
    ),
}


@dataclass(frozen=True)
class BeamCheck:
    """Results of beam bending check."""

    moment_knm: float
    stress_mpa: float
    bending_utilization: float
    deflection_mm: float
    deflection_limit_mm: float
    deflection_utilization: float
    utilization: float
    passes: bool


def check_beam(
    span_m: float,
    w_kn_m: float,
    section: Section,
    fy: float = FY_STEEL,
    e: float = E_STEEL,
    deflection_ratio: float = 360.0,
    w_deflection_kn_m: float | None = None,
) -> BeamCheck:
    """
    Check simply supported beam under uniform load.

    Args:
        span_m: Beam span in meters (must be positive)
        w_kn_m: Uniform load in kN/m
        section: Steel section properties
        fy: Yield strength in Pa (default: FY_STEEL)
        e: Modulus of elasticity in Pa (default: E_STEEL)
        deflection_ratio: L/deflection_ratio limit (default: 360)
        w_deflection_kn_m: Load for the deflection check, typically the live
            load alone (L/360 is a live-load limit). Defaults to ``w_kn_m``.

    Returns:
        BeamCheck with results

    Raises:
        ValueError: If span_m <= 0
    """
    if span_m <= 0:
        raise ValueError("span_m must be positive")

    # Internal calculations in SI units (N, m)
    w_n_m = w_kn_m * 1000.0  # kN/m -> N/m
    moment_nm = w_n_m * span_m**2 / 8.0  # Max moment (N·m)
    moment_knm = moment_nm / 1000.0  # Convert to kN·m

    stress_pa = moment_nm / section.sx_m3  # Stress (Pa)
    stress_mpa = stress_pa / 1e6  # Convert to MPa

    allowable_pa = 0.66 * fy  # Allowable stress (Pa)
    bending_utilization = stress_pa / allowable_pa

    # Deflection (m) for simply supported beam with UDL
    w_defl_n_m = (w_kn_m if w_deflection_kn_m is None else w_deflection_kn_m) * 1000.0
    deflection_m = 5 * w_defl_n_m * span_m**4 / (384 * e * section.ix_m4)
    deflection_mm = deflection_m * 1000.0  # Convert to mm

    deflection_limit_m = span_m / deflection_ratio
    deflection_limit_mm = deflection_limit_m * 1000.0

    deflection_utilization = deflection_mm / deflection_limit_mm

    utilization = max(bending_utilization, deflection_utilization)
    passes = utilization <= 1.0

    return BeamCheck(
        moment_knm=moment_knm,
        stress_mpa=stress_mpa,
        bending_utilization=bending_utilization,
        deflection_mm=deflection_mm,
        deflection_limit_mm=deflection_limit_mm,
        deflection_utilization=deflection_utilization,
        utilization=utilization,
        passes=passes,
    )


@dataclass(frozen=True)
class ColumnCheck:
    """Results of column axial check."""

    axial_kn: float
    euler_kn: float
    squash_kn: float
    slenderness: float
    capacity_kn: float
    utilization: float
    passes: bool


def check_column(
    length_m: float,
    axial_kn: float,
    section: Section,
    k: float = 1.0,
    safety_factor: float = 1.67,
    fy: float = FY_STEEL,
    e: float = E_STEEL,
) -> ColumnCheck:
    """
    Check axially loaded column for Euler buckling and crushing.

    Args:
        length_m: Column length in meters
        axial_kn: Axial load in kN (tension or compression)
        section: Steel section properties
        k: Effective length factor (default: 1.0 for pinned-pinned)
        safety_factor: Factor of safety (default: 1.67)
        fy: Yield strength in Pa (default: FY_STEEL)
        e: Modulus of elasticity in Pa (default: E_STEEL)

    Returns:
        ColumnCheck with results
    """
    # Effective length
    leff_m = k * length_m

    # Minimum moment of inertia
    i_min_m4 = section.area_m2 * section.r_min_m**2

    # Euler buckling load (N)
    euler_n = math.pi**2 * e * i_min_m4 / leff_m**2
    euler_kn = euler_n / 1000.0

    # Squash (yield) load (N)
    squash_n = section.area_m2 * fy
    squash_kn = squash_n / 1000.0

    # Capacity (N) with safety factor
    capacity_n = min(euler_n, squash_n) / safety_factor
    capacity_kn = capacity_n / 1000.0

    # Slenderness ratio
    slenderness = leff_m / section.r_min_m

    # Utilization
    utilization = axial_kn / capacity_kn
    passes = utilization <= 1.0

    return ColumnCheck(
        axial_kn=axial_kn,
        euler_kn=euler_kn,
        squash_kn=squash_kn,
        slenderness=slenderness,
        capacity_kn=capacity_kn,
        utilization=utilization,
        passes=passes,
    )


@dataclass
class FrameResult:
    """Results of 2D frame analysis."""

    displacements: np.ndarray  # (n_nodes, 3) [ux, uy, rz]
    reactions: np.ndarray  # (n_nodes, 3) [Fx, Fy, Mz]


def solve_frame_2d(
    nodes: np.ndarray,
    members: list[tuple[int, int]],
    e: float,
    area: float | list[float],
    inertia: float | list[float],
    supports: dict[int, tuple[bool, bool, bool]],
    loads: dict[int, tuple[float, float, float]],
) -> FrameResult:
    """
    Solve 2D frame using direct stiffness method.

    Args:
        nodes: (n_nodes, 2) array of [x, y] coordinates
        members: List of (i, j) node index pairs
        e: Modulus of elasticity (Pa)
        area: Cross-sectional area (m^2) or list per member
        inertia: Moment of inertia (m^4) or list per member
        supports: Dict mapping node index to (fix_x, fix_y, fix_rz)
        loads: Dict mapping node index to (Fx, Fy, Mz) in N, N, N·m

    Returns:
        FrameResult with displacements and reactions

    Raises:
        ValueError: If structure is unstable
    """
    n_nodes = nodes.shape[0]
    n_dof = n_nodes * 3  # 3 DOF per node: ux, uy, rz

    # Handle scalar inputs
    if isinstance(area, int | float):
        area = [float(area)] * len(members)
    if isinstance(inertia, int | float):
        inertia = [float(inertia)] * len(members)

    # Initialize global stiffness matrix and force vector
    k_global = np.zeros((n_dof, n_dof))
    f_global = np.zeros(n_dof)

    # Assemble global stiffness matrix
    for idx, (i, j) in enumerate(members):
        # Get member properties
        a = area[idx]
        i_val = inertia[idx]

        # Node coordinates
        xi, yi = nodes[i]
        xj, yj = nodes[j]

        # Length and direction cosines
        dx = xj - xi
        dy = yj - yi
        l = math.sqrt(dx**2 + dy**2)
        if l == 0:
            raise ValueError("Member length is zero")
        c = dx / l
        s = dy / l

        # Local stiffness matrix (6x6)
        k_local = np.zeros((6, 6))
        ae_l = e * a / l
        ei_l = e * i_val / l
        ei_l2 = ei_l / l
        ei_l3 = ei_l2 / l

        # Axial terms
        k_local[0, 0] = ae_l
        k_local[0, 3] = -ae_l
        k_local[3, 0] = -ae_l
        k_local[3, 3] = ae_l

        # Bending terms
        k_local[1, 1] = 12 * ei_l3
        k_local[1, 2] = 6 * ei_l2
        k_local[1, 4] = -12 * ei_l3
        k_local[1, 5] = 6 * ei_l2
        k_local[2, 1] = 6 * ei_l2
        k_local[2, 2] = 4 * ei_l
        k_local[2, 4] = -6 * ei_l2
        k_local[2, 5] = 2 * ei_l
        k_local[4, 1] = -12 * ei_l3
        k_local[4, 2] = -6 * ei_l2
        k_local[4, 4] = 12 * ei_l3
        k_local[4, 5] = -6 * ei_l2
        k_local[5, 1] = 6 * ei_l2
        k_local[5, 2] = 2 * ei_l
        k_local[5, 4] = -6 * ei_l2
        k_local[5, 5] = 4 * ei_l

        # Transformation matrix (3 DOF per node)
        t = np.array(
            [
                [c, s, 0, 0, 0, 0],
                [-s, c, 0, 0, 0, 0],
                [0, 0, 1, 0, 0, 0],
                [0, 0, 0, c, s, 0],
                [0, 0, 0, -s, c, 0],
                [0, 0, 0, 0, 0, 1],
            ]
        )

        # Global stiffness contribution
        k_global_local = t.T @ k_local @ t

        # Map to global DOFs
        dof_map = [i * 3, i * 3 + 1, i * 3 + 2, j * 3, j * 3 + 1, j * 3 + 2]
        k_global[np.ix_(dof_map, dof_map)] += k_global_local

    # Apply loads
    for node_idx, (fx, fy, mz) in loads.items():
        f_global[node_idx * 3] += fx
        f_global[node_idx * 3 + 1] += fy
        f_global[node_idx * 3 + 2] += mz

    # Identify free and fixed DOFs
    fixed_dofs = []
    free_dofs = []
    for node_idx in range(n_nodes):
        fix_x, fix_y, fix_rz = supports.get(node_idx, (False, False, False))
        if fix_x:
            fixed_dofs.append(node_idx * 3)
        else:
            free_dofs.append(node_idx * 3)
        if fix_y:
            fixed_dofs.append(node_idx * 3 + 1)
        else:
            free_dofs.append(node_idx * 3 + 1)
        if fix_rz:
            fixed_dofs.append(node_idx * 3 + 2)
        else:
            free_dofs.append(node_idx * 3 + 2)

    # Check for stability
    if len(free_dofs) == 0:
        raise ValueError("structure is unstable")

    # Extract submatrices for free DOFs
    k_free = k_global[np.ix_(free_dofs, free_dofs)]
    f_free = f_global[free_dofs]

    try:
        # Solve for free displacements
        u_free = solve(k_free, f_free, assume_a="sym")
    except LinAlgError as exc:
        raise ValueError("structure is unstable") from exc
    if not np.all(np.isfinite(u_free)):
        raise ValueError("structure is unstable")

    # Reconstruct full displacement vector
    u_global = np.zeros(n_dof)
    for i, dof in enumerate(free_dofs):
        u_global[dof] = u_free[i]

    # Reshape to (n_nodes, 3)
    displacements = u_global.reshape((n_nodes, 3))

    # Compute reactions: R = K*u - F
    reactions_global = k_global @ u_global - f_global
    reactions_global[free_dofs] = 0.0

    # Reshape to (n_nodes, 3)
    reactions = reactions_global.reshape((n_nodes, 3))

    return FrameResult(displacements=displacements, reactions=reactions)


def natural_periods(
    story_masses_kg: list[float] | np.ndarray,
    story_stiffness_n_m: list[float] | np.ndarray,
) -> np.ndarray:
    """
    Compute natural periods for shear-building model.

    Args:
        story_masses_kg: Mass at each story (kg), story 0 is lowest
        story_stiffness_n_m: Stiffness of each story (N/m), story 0 to ground

    Returns:
        Periods in seconds, sorted descending (fundamental first)

    Raises:
        ValueError: On length mismatch, empty input, or non-positive values
    """
    masses = np.asarray(story_masses_kg, dtype=float)
    stiffness = np.asarray(story_stiffness_n_m, dtype=float)

    # Validate inputs
    if masses.size == 0 or stiffness.size == 0:
        raise ValueError("Input arrays must not be empty")
    if masses.shape != stiffness.shape:
        raise ValueError(
            "story_masses_kg and story_stiffness_n_m must have same length"
        )
    if np.any(masses <= 0) or np.any(stiffness <= 0):
        raise ValueError("All masses and stiffnesses must be positive")

    n = masses.size

    # Build mass matrix (diagonal)
    m_matrix = np.diag(masses)

    # Build stiffness matrix (tridiagonal)
    k_matrix = np.zeros((n, n))
    for i in range(n):
        if i == 0:
            k_matrix[i, i] = (
                stiffness[i] + stiffness[i + 1] if i + 1 < n else stiffness[i]
            )
        elif i == n - 1:
            k_matrix[i, i] = stiffness[i]
        else:
            k_matrix[i, i] = stiffness[i] + stiffness[i + 1]
        if i < n - 1:
            k_matrix[i, i + 1] = -stiffness[i + 1]
            k_matrix[i + 1, i] = -stiffness[i + 1]

    # Solve generalized eigenvalue problem: K*phi = lambda*M*phi
    eigenvalues, _ = eigh(k_matrix, m_matrix)

    # Compute periods: T = 2*pi/sqrt(lambda)
    angular_freqs = np.sqrt(eigenvalues)
    periods = 2 * math.pi / angular_freqs

    # Sort descending (fundamental period first)
    return np.sort(periods)[::-1]


def column_lateral_stiffness(
    section: Section,
    height_m: float,
    e: float = E_STEEL,
) -> float:
    """
    Compute lateral sway stiffness of fixed-fixed column.

    Args:
        section: Steel section properties
        height_m: Column height in meters
        e: Modulus of elasticity in Pa (default: E_STEEL)

    Returns:
        Lateral stiffness in N/m
    """
    if height_m <= 0:
        return 0.0
    return 12 * e * section.ix_m4 / height_m**3

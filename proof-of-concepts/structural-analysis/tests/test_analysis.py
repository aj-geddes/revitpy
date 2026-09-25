"""structural_analysis.analysis against closed-form results."""

from __future__ import annotations

import math

import numpy as np
import pytest
from structural_analysis.analysis import (
    E_STEEL,
    FY_STEEL,
    SECTIONS,
    check_beam,
    check_column,
    column_lateral_stiffness,
    natural_periods,
    solve_frame_2d,
)

W16 = SECTIONS["W16x26"]
E, I, A = 200e9, 1e-4, 1e-2


def test_section_conversion():
    assert W16.ix_m4 == pytest.approx(301 * 4.162314256e-7, rel=1e-9)
    assert W16.mass_kg_m == pytest.approx(26 * 1.48816394)


def test_beam_hand_calculation():
    c = check_beam(6.0, 10.0, W16)
    assert c.moment_knm == pytest.approx(45.0)
    assert c.stress_mpa == pytest.approx(45e3 / W16.sx_m3 / 1e6)
    assert c.bending_utilization == pytest.approx(45e3 / W16.sx_m3 / (0.66 * FY_STEEL))
    deflection = 5 * 10e3 * 6**4 / (384 * E_STEEL * W16.ix_m4) * 1000
    assert c.deflection_mm == pytest.approx(deflection)
    assert c.deflection_limit_mm == pytest.approx(6000 / 360)
    live_only = check_beam(6.0, 10.0, W16, w_deflection_kn_m=5.0)
    assert live_only.deflection_mm == pytest.approx(deflection / 2)
    assert live_only.bending_utilization == pytest.approx(c.bending_utilization)
    with pytest.raises(ValueError):
        check_beam(0.0, 10.0, W16)


def test_column_euler_and_squash():
    s = SECTIONS["W8x31"]
    c = check_column(4.0, 500.0, s)
    euler = math.pi**2 * E_STEEL * s.area_m2 * s.r_min_m**2 / 4.0**2 / 1000
    assert c.euler_kn == pytest.approx(euler)
    assert c.slenderness == pytest.approx(4.0 / s.r_min_m)
    stub = check_column(0.5, 500.0, s)
    assert stub.capacity_kn == pytest.approx(s.area_m2 * FY_STEEL / 1.67 / 1000)
    assert check_column(4.0, 1000.0, s).utilization == pytest.approx(2 * c.utilization)


def _cantilever(tip: tuple[float, float], load: tuple[float, float, float]):
    nodes = np.array([(0.0, 0.0), tip])
    return solve_frame_2d(nodes, [(0, 1)], E, A, I, {0: (True, True, True)}, {1: load})


def test_horizontal_cantilever():
    p, length = 10e3, 3.0
    result = _cantilever((length, 0.0), (0.0, -p, 0.0))
    assert result.displacements[1, 1] == pytest.approx(
        -p * length**3 / (3 * E * I), rel=1e-6
    )
    assert result.displacements[1, 2] == pytest.approx(
        -p * length**2 / (2 * E * I), rel=1e-6
    )
    assert result.reactions[0] == pytest.approx([0.0, p, p * length], abs=1e-6)
    assert result.reactions[1] == pytest.approx([0.0, 0.0, 0.0])


def test_vertical_cantilever_catches_transformation_errors():
    p, length = 10e3, 3.0
    result = _cantilever((0.0, length), (p, 0.0, 0.0))
    assert result.displacements[1, 0] == pytest.approx(
        p * length**3 / (3 * E * I), rel=1e-6
    )
    assert result.displacements[1, 1] == pytest.approx(0.0, abs=1e-12)


def test_axial_bar():
    result = _cantilever((2.0, 0.0), (5e3, 0.0, 0.0))
    assert result.displacements[1, 0] == pytest.approx(5e3 * 2.0 / (E * A), rel=1e-9)


def test_unsupported_structure_is_unstable():
    with pytest.raises(ValueError, match="unstable"):
        solve_frame_2d(
            np.array([(0.0, 0.0), (1.0, 0.0)]),
            [(0, 1)],
            E,
            A,
            I,
            {},
            {1: (1.0, 0.0, 0.0)},
        )


def test_natural_periods():
    assert natural_periods([1000.0], [1e6]) == pytest.approx(
        [2 * math.pi * math.sqrt(1e-3)]
    )
    m, k = 1000.0, 1e6
    expected = [
        2 * math.pi / math.sqrt(k / m * (3 + s * math.sqrt(5)) / 2) for s in (-1, 1)
    ]
    assert natural_periods([m, m], [k, k]) == pytest.approx(expected)
    with pytest.raises(ValueError):
        natural_periods([m], [k, k])
    with pytest.raises(ValueError):
        natural_periods([m, -m], [k, k])


def test_column_lateral_stiffness():
    assert column_lateral_stiffness(W16, 4.0) == pytest.approx(
        12 * E_STEEL * W16.ix_m4 / 64
    )

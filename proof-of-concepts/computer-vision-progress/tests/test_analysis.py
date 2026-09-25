"""progress_vision.analysis on hand-built images."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from progress_vision.analysis import (
    detect_installed_panels,
    otsu_threshold,
    progress_summary,
)

CELL = 20
EXPECTED = np.array([[False, False, True], [True, False, False]])


def grid_image() -> np.ndarray:
    """2 x 3 grid; installed: row 0 (bottom) col 2, and row 1 (top) col 0."""
    img = np.full((2 * CELL, 3 * CELL), 30, dtype=np.uint8)
    img[CELL:, 2 * CELL :] = 220  # bottom-right
    img[:CELL, :CELL] = 220  # top-left
    return img


def test_otsu_separates_two_levels():
    img = np.zeros((2, 100), dtype=np.uint8)
    img[:, :50], img[:, 50:] = 50, 200
    assert 50 <= otsu_threshold(img) < 200
    with pytest.raises(ValueError):
        otsu_threshold(np.zeros((0, 0), dtype=np.uint8))


def test_detection_uses_bottom_row_as_row_zero():
    detection = detect_installed_panels(grid_image(), 2, 3)
    np.testing.assert_array_equal(detection.installed, EXPECTED)
    assert detection.fill_ratio == pytest.approx(EXPECTED.astype(float))
    assert detection.confidence == pytest.approx(np.ones((2, 3)))
    assert 30 <= detection.threshold < 220


def test_detection_survives_noise():
    noise = np.random.default_rng(0).normal(0, 20, (2 * CELL, 3 * CELL))
    img = np.clip(grid_image() + noise, 0, 255).astype(np.uint8)
    np.testing.assert_array_equal(
        detect_installed_panels(img, 2, 3).installed, EXPECTED
    )


def test_detection_validates_input():
    with pytest.raises(ValueError):
        detect_installed_panels(grid_image(), 0, 3)
    with pytest.raises(ValueError):
        detect_installed_panels(np.zeros((10, 10, 3), dtype=np.uint8), 1, 1)
    with pytest.raises(ValueError):
        detect_installed_panels(np.zeros((2, 2), dtype=np.uint8), 3, 3)


def test_progress_summary():
    panels = pd.DataFrame(
        {
            "row": [0, 0, 1, 1],
            "col": [0, 1, 0, 1],
            "volume_m3": [1.0, 1.0, 2.0, 2.0],
            "installed": [True, False, True, True],
        }
    )
    summary = progress_summary(panels)
    assert (summary.count_total, summary.count_installed) == (4, 3)
    assert summary.percent_by_count == pytest.approx(75.0)
    assert summary.percent_by_volume == pytest.approx(500 / 6)
    assert summary.by_row["percent"].tolist() == pytest.approx([50.0, 100.0])

"""progress_vision against the demo model through the RevitPy API."""

from __future__ import annotations

import numpy as np
import pytest
from poc_common import build_demo_building, connect
from poc_common.timeseries import facade_photo
from progress_vision import demo_installed_grid, run
from progress_vision.model_data import facade_panels


@pytest.fixture
def app():
    return build_demo_building()


def test_panels_are_read_from_marks(app):
    panels = facade_panels(connect(app))
    assert len(panels) == 60
    assert panels["row"].max() == 5 and panels["col"].max() == 9
    assert panels.loc[0, "mark"] == "FP-00-00"
    # 3 m x 2 m x 0.15 m precast panel, converted from ft3.
    assert panels["volume_m3"].to_numpy() == pytest.approx([0.9] * 60)
    assert panels.groupby("level").size().to_dict() == {
        "Level 1": 20,
        "Level 2": 20,
        "Level 3": 20,
    }


def test_clean_photo_is_read_exactly(app):
    truth = demo_installed_grid(6, 10)
    image = facade_photo(6, 10, truth, noise_sd=0.0, occlusion=False)
    report = run(app, image=image, write=False)
    assert report.summary.count_installed == int(truth.sum()) == 36
    assert report.summary.percent_by_count == pytest.approx(60.0)


def test_noisy_synthetic_photo_is_mostly_right(app):
    report = run(app)
    assert report.accuracy is not None and report.accuracy >= 0.9


def test_status_is_written_to_the_panels(app):
    image = facade_photo(6, 10, np.ones((6, 10), dtype=bool), occlusion=False)
    report = run(app, image=image, photo_label="photo 2025-03-14")
    assert report.written == 60
    element_id = int(report.panels.loc[0, "element_id"])
    text = app.ActiveDocument.GetElement(element_id).GetParameterValue("Comments").value
    assert text.startswith("installed per photo 2025-03-14")

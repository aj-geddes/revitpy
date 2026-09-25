"""Facade progress from a site photo, mapped onto the model's panel grid.

Inside Revit (RevitPy add-in or Live Server)::

    import numpy as np
    from progress_vision import run
    image = np.load("rectified_south_facade.npy")  # 2-D uint8 array
    print(run(__revit__, image=image, photo_label="photo 2025-03-14").to_text())

Outside Revit, ``run()`` uses the demo building and a synthetic photo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from poc_common import connect, source_label
from poc_common.timeseries import facade_photo

from .analysis import (
    PanelDetection,
    ProgressSummary,
    detect_installed_panels,
    progress_summary,
)
from .model_data import facade_panels, write_status

__all__ = ["ProgressReport", "demo_installed_grid", "run"]


def demo_installed_grid(rows: int, cols: int) -> np.ndarray:
    """Ground truth for the synthetic photo: erected bottom-up, top row pending."""
    installed = np.zeros((rows, cols), dtype=bool)
    installed[: rows // 2, :] = True
    installed[rows // 2, : cols * 3 // 5] = True
    return installed


@dataclass
class ProgressReport:
    """Results of :func:`run`."""

    source: str
    panels: pd.DataFrame
    detection: PanelDetection
    summary: ProgressSummary
    accuracy: float | None = None
    written: int = 0
    notes: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        s = self.summary
        by_level = (
            self.panels.groupby("level")["installed"].agg(["sum", "size"]).sort_index()
        )
        uncertain = self.panels[self.panels["confidence"] < 0.3]
        lines = [
            f"Facade progress - {self.source}",
            f"{s.count_total} panels on the grid, Otsu threshold "
            f"{self.detection.threshold}",
            "",
            f"Progress: {s.count_installed}/{s.count_total} panels "
            f"({s.percent_by_count:.0f}% by count, {s.percent_by_volume:.0f}% by volume)",
            *(
                f"  {level:<8} {int(r['sum']):3d}/{int(r['size'])} installed"
                for level, r in by_level.iterrows()
            ),
            "Check on site (low confidence): "
            + (", ".join(uncertain["mark"]) if len(uncertain) else "none"),
        ]
        if self.accuracy is not None:
            lines.append(
                f"Detection accuracy vs synthetic ground truth: {self.accuracy:.1%}"
            )
        if self.written:
            lines += [
                "",
                f"Wrote detected status to Comments on {self.written} panels.",
            ]
        lines += [f"Note: {n}" for n in self.notes]
        return "\n".join(lines)


def run(
    app: Any | None = None,
    *,
    image: np.ndarray | None = None,
    photo_label: str = "synthetic photo",
    seed: int = 0,
    write: bool = True,
) -> ProgressReport:
    """Detect installed panels and record them on the model.

    Args:
        app: ``__revit__`` inside Revit; ``None`` uses the demo model.
        image: Rectified grayscale elevation (2-D uint8) covering exactly the
            panel grid. A synthetic photo is generated when omitted.
        photo_label: Text used when writing status to ``Comments``.
        seed: Seed for the synthetic photo.
        write: Write each panel's detected status to ``Comments``.
    """
    api = connect(app)
    source = source_label(api, app)
    notes = []
    panels = facade_panels(api)
    if panels.empty:
        raise ValueError("No facade panels (Generic Models marked FP-<row>-<col>)")
    rows, cols = int(panels["row"].max()) + 1, int(panels["col"].max()) + 1

    truth = None
    if image is None:
        truth = demo_installed_grid(rows, cols)
        image = facade_photo(rows, cols, truth, seed=seed)
        notes.append("the site photo is synthetic (noise plus one occluding object)")

    detection = detect_installed_panels(image, rows, cols)
    r, c = panels["row"].to_numpy(), panels["col"].to_numpy()
    panels = panels.assign(
        installed=detection.installed[r, c], confidence=detection.confidence[r, c]
    )
    summary = progress_summary(panels)
    accuracy = (
        float((detection.installed == truth).mean()) if truth is not None else None
    )

    written = write_status(api, panels, photo_label) if write else 0
    return ProgressReport(
        source=source,
        panels=panels,
        detection=detection,
        summary=summary,
        accuracy=accuracy,
        written=written,
        notes=notes,
    )

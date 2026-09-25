"""Detect installed facade panels in a rectified elevation image; summarise progress.

Classical image processing (Otsu thresholding, per-cell fill ratio, connected
components with scipy.ndimage). It assumes the photo has already been
rectified to the facade elevation (e.g. from four surveyed corner points)
so that the panel grid from the model can be overlaid directly. A production
system would replace the thresholding with a trained detector; the
model-side plumbing stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.ndimage import label


def otsu_threshold(image: np.ndarray) -> int:
    """
    Compute Otsu's threshold for a uint8 image using a 256-bin histogram.

    Parameters
    ----------
    image : np.ndarray
        Input uint8 image.

    Returns
    -------
    int
        Threshold value (0..255) maximising between-class variance.

    Raises
    ------
    ValueError
        If the image is empty.
    """
    if image.size == 0:
        raise ValueError("Image is empty")

    hist, _ = np.histogram(image.ravel(), bins=256, range=(0, 256))
    total = hist.sum()
    if total == 0:
        return 0

    cumsum = np.cumsum(hist)
    cumsum_sq = np.cumsum(hist * np.arange(256))

    # Background and foreground statistics
    weight_bg = cumsum / total
    weight_fg = 1.0 - weight_bg

    mean_total = cumsum_sq[-1] / total
    with np.errstate(divide="ignore", invalid="ignore"):
        mean_bg = np.where(cumsum > 0, cumsum_sq / cumsum, 0.0)
        mean_fg = (mean_total * total - cumsum_sq) / (total - cumsum)
        mean_fg = np.where(weight_fg > 0, mean_fg, 0.0)
        # Between-class variance
        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
    variance[~np.isfinite(variance)] = 0.0

    # Return threshold with maximum variance; if tie, prefer lower threshold
    return int(np.argmax(variance))


@dataclass
class PanelDetection:
    """Detection result for facade panels."""

    installed: np.ndarray  # bool, shape (rows, cols)
    fill_ratio: np.ndarray  # float, shape (rows, cols)
    confidence: np.ndarray  # float, shape (rows, cols)
    threshold: int
    components: int


def detect_installed_panels(
    image: np.ndarray,
    rows: int,
    cols: int,
    fill_threshold: float = 0.5,
    margin_fraction: float = 0.15,
    threshold: int | None = None,
) -> PanelDetection:
    """
    Detect installed facade panels in a rectified grayscale elevation image.

    Parameters
    ----------
    image : np.ndarray
        2D uint8 grayscale image.
    rows : int
        Number of grid rows (ground floor is row 0).
    cols : int
        Number of grid columns.
    fill_threshold : float, optional
        Minimum fill ratio to consider a panel installed (default 0.5).
    margin_fraction : float, optional
        Fraction of cell size to ignore on each side (default 0.15).
    threshold : int | None, optional
        Threshold for binarisation. If None, use Otsu's method.

    Returns
    -------
    PanelDetection
        Detection result containing panel status and metadata.

    Raises
    ------
    ValueError
        If rows/cols < 1, image is not 2D, or image is smaller than grid.
    """
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be >= 1")
    if image.ndim != 2:
        raise ValueError("Image must be 2D")
    height, width = image.shape
    if height < rows or width < cols:
        raise ValueError("Image is smaller than the grid")

    # Compute threshold if not provided
    if threshold is None:
        threshold = otsu_threshold(image)

    # Binarise image
    mask = image > threshold

    # Compute number of connected components
    structure = np.ones((3, 3), dtype=int)
    _labeled, components = label(mask, structure=structure)

    # Create grid edges
    row_edges = np.round(np.linspace(0, height, rows + 1)).astype(int)
    col_edges = np.round(np.linspace(0, width, cols + 1)).astype(int)

    # Ensure edges are within bounds
    row_edges = np.clip(row_edges, 0, height)
    col_edges = np.clip(col_edges, 0, width)

    # Initialize result arrays
    fill_ratio = np.zeros((rows, cols), dtype=np.float64)
    installed = np.zeros((rows, cols), dtype=bool)

    # Process each grid cell
    for r in range(rows):
        # Grid row r corresponds to image rows [height - row_edges[r+1], height - row_edges[r])
        img_row_start = height - row_edges[r + 1]
        img_row_end = height - row_edges[r]
        cell_height = row_edges[r + 1] - row_edges[r]

        for c in range(cols):
            img_col_start = col_edges[c]
            img_col_end = col_edges[c + 1]
            cell_width = col_edges[c + 1] - col_edges[c]

            # Extract cell region
            cell_mask = mask[img_row_start:img_row_end, img_col_start:img_col_end]

            # Compute margin sizes (at least 1 pixel if cell is large enough)
            margin_h = max(1, int(cell_height * margin_fraction))
            margin_w = max(1, int(cell_width * margin_fraction))

            # Compute inner region indices
            inner_row_start = margin_h
            inner_row_end = cell_height - margin_h
            inner_col_start = margin_w
            inner_col_end = cell_width - margin_w

            # Ensure inner region is valid
            if inner_row_start >= inner_row_end or inner_col_start >= inner_col_end:
                # If inner region is too small, use entire cell
                inner_cell_mask = cell_mask
            else:
                inner_cell_mask = cell_mask[
                    inner_row_start:inner_row_end, inner_col_start:inner_col_end
                ]

            # Compute fill ratio
            if inner_cell_mask.size > 0:
                fill_ratio[r, c] = inner_cell_mask.mean()
            else:
                fill_ratio[r, c] = 0.0

            # Determine if installed
            installed[r, c] = fill_ratio[r, c] >= fill_threshold

    # Compute confidence
    denom = max(fill_threshold, 1 - fill_threshold)
    if denom == 0:
        confidence = np.zeros_like(fill_ratio)
    else:
        confidence = np.clip(np.abs(fill_ratio - fill_threshold) / denom, 0.0, 1.0)

    return PanelDetection(
        installed=installed,
        fill_ratio=fill_ratio,
        confidence=confidence,
        threshold=int(threshold),
        components=int(components),
    )


@dataclass
class ProgressSummary:
    """Summary of construction progress."""

    count_total: int
    count_installed: int
    percent_by_count: float
    percent_by_volume: float
    by_row: pd.DataFrame


def progress_summary(panels: pd.DataFrame) -> ProgressSummary:
    """
    Generate a progress summary from panel data.

    Parameters
    ----------
    panels : pd.DataFrame
        DataFrame with columns: row (int), col (int), volume_m3 (float), installed (bool).

    Returns
    -------
    ProgressSummary
        Summary of installation progress.
    """
    count_total = len(panels)
    count_installed = panels["installed"].sum()

    # Percentages (0..100)
    if count_total > 0:
        percent_by_count = (count_installed / count_total) * 100.0
    else:
        percent_by_count = 0.0

    total_volume = panels["volume_m3"].sum()
    installed_volume = panels.loc[panels["installed"], "volume_m3"].sum()
    if total_volume > 0:
        percent_by_volume = (installed_volume / total_volume) * 100.0
    else:
        percent_by_volume = 0.0

    # Group by row
    by_row = (
        panels.groupby("row")
        .agg(installed=("installed", "sum"), total=("installed", "size"))
        .reset_index()
    )
    by_row["percent"] = (
        by_row["installed"] / by_row["total"] * 100.0
        if by_row["total"].max() > 0
        else 0.0
    )
    by_row = by_row.sort_values("row").reset_index(drop=True)

    return ProgressSummary(
        count_total=count_total,
        count_installed=int(count_installed),
        percent_by_count=float(percent_by_count),
        percent_by_volume=float(percent_by_volume),
        by_row=by_row,
    )

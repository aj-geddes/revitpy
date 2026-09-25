# Facade progress from photos

`python -m progress_vision` · package `progress_vision`

## What it does

1. **Reads the panel grid.** Precast facade panels are `Generic Models` whose
   `Mark` is `FP-<row>-<col>`, with row 0 at the bottom. `QuantityExtractor`
   reads each panel's `Volume` (ft³ to m³).
2. **Detects installed panels** in a *rectified* grayscale elevation image. The
   image is thresholded with Otsu's method, split into the model's rows x
   columns grid with the joint margins ignored, and each cell is marked
   installed when enough of it is bright. A confidence score comes from how far
   the fill ratio is from the cut-off.
3. **Summarises progress** by count, by volume and by level, and lists
   low-confidence panels to check on site.
4. **Write-back.** Writes "installed / not installed per <photo>" to each
   panel's `Comments` in one transaction.

## Data

With no `image=` argument, the photo is **synthetic**. The lower half of the
facade is installed and the next row is 60% done. The image has Gaussian noise
and one mid-grey occluding rectangle, standing in for a scaffold or crane. The
tests check exact detection on a clean image and at least 90% accuracy on the
noisy one. An occluded installed panel reads as *not installed with high
confidence*. That is a real limitation of simple thresholding and the reason
for the site-check list.

For a real photo, rectify it to the facade elevation first so the model's grid
can be overlaid directly. A perspective transform from four surveyed corners
does this (OpenCV's `getPerspectiveTransform` / `warpPerspective`, or
`skimage.transform`). Crop it to the panel grid, convert to 8-bit grayscale,
and pass it as a 2-D NumPy array (`--image photo.npy`).

## Changed from the original concept

The earlier version described TensorFlow and Detectron2 object detection, but
its code used stand-in "MockOpenCV" and "MockTensorFlow" classes. Nothing was
detected. This version is classical image processing that runs, with only NumPy
and SciPy (`scipy.ndimage`). A trained detector would replace
`detect_installed_panels`. Reading the grid from the model, mapping detections
to elements and writing status in a transaction would stay the same. No OpenCV
dependency is needed for the demo.

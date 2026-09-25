# Space planning

`python -m space_planning` · package `space_planning`

## What it does

1. **Reads rooms.** Queries `Room`s with `api.query(Room)` and reads `Area`
   (ft², converted to m²), design capacity (`Occupancy`), `Department` and
   `Level`.
2. **Utilization features.** From hourly head counts per room it computes, over
   weekday business hours (08:00-18:00), mean utilization, 95th-percentile
   utilization, the share of hours the room was in use, and m² per seat.
3. **Clustering.** Runs scikit-learn k-means (k = 3) on the standardized
   features and names the clusters `underused`, `typical` and `busy` by their
   mean utilization. The silhouette score is reported.
4. **Forecast.** A gradient-boosted regressor
   (`HistGradientBoostingRegressor`) on hour and weekday predicts the busiest
   room's occupancy for the last week. It is scored against a
   same-hour-last-week baseline. A forecast that can't beat that baseline isn't
   worth deploying.
5. **Team-to-room assignment.** Teams with a headcount are matched to shared
   rooms with `scipy.optimize.linear_sum_assignment`, minimising total spare
   seats. A team never goes into a room that is too small.
6. **Write-back.** Writes each room's utilization class to `Comments` in one
   transaction.

## Data

With no `occupancy=` argument, head counts are **synthetic**. Every room gets an
`underused`, `typical` or `busy` profile (see `ROOM_SCHEDULE` in
`poc_common.demo_model`), and counts are drawn from a binomial distribution. The
tests check that clustering recovers those profiles. For real use, pass
`occupancy=` as a long DataFrame (`timestamp`, `room_id`, `occupants`). Badge
readers, desk sensors or Wi-Fi counts are typical sources. `room_id` is the
Revit element id.

## Model parameters used

| Parameter | Notes |
|---|---|
| `Area`, `Level`, `Comments` | built-in |
| `Occupancy` | read as the room's design capacity (a number of seats). Map whatever capacity parameter your model uses to it. |
| `Department` | built-in room parameter. Only `Shared` rooms are offered to teams. |

## Changed from the original concept

The earlier version described an LSTM in TensorFlow for occupancy prediction.
Hourly room counts have a strong daily and weekly pattern, and a tree model on
calendar features captures it with none of TensorFlow's install weight. The
honest comparison is against the seasonal-naive baseline, which is reported.
Layout "optimisation" with differential evolution was dropped. It had no
geometry to optimise, and the assignment problem above is well posed.

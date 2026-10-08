# Leakage audit checklist
Run before any backtest result is reported.
- [ ] `pytest tests/leakage` passes from a clean checkout at the stated commit
- [ ] Sample ≥50 random (game_id, as_of) feature rows; for each, trace contributing rows and confirm event_time < as_of
- [ ] Market line in every training row has line_class = close from a documented source (never last_pull for a future game)
- [ ] No feature reads a column on docs/LEAKAGE_REGISTER.md
- [ ] Injury features: 2010–2024 filtered by date_modified < as_of; 2025+ only from our snapshots with observed_at < as_of, or absent
- [ ] Depth-chart features use snapshot dt < as_of (2025+) or week ≤ game week − 1 (≤2024) and the handoff states which
- [ ] Opponent adjustment uses only games before as_of (no season-end SOS)
- [ ] Rolling/decay windows do not peek (check the first weeks of each season)
- [ ] Rebuilt pbp: snapshot ids pinned; features not recomputed from a newer snapshot than the run records
- [ ] Target columns (result, total, covers) are never present in the feature frame

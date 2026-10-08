# Backtest audit checklist
Run before a model is promoted or a result enters CHANGELOG.
- [ ] Recompute ATS%, ML%, ROI, Brier, log-loss, MAE/RMSE, CLV from lab.backtest_predictions with your own script; match within rounding
- [ ] Walk-forward boundaries: no training row dated ≥ the predicted game's as_of; refit cadence as stated
- [ ] Sealed seasons (2024–2025) run exactly once for this model version (lab.backtest_runs count)
- [ ] Baselines present and reported: M0, M-market, previous production model
- [ ] Attempts counted (feature sets, thresholds, situations); BH adjustment applied across the family
- [ ] Wilson intervals and Bayesian shrinkage shown beside raw rates; n ≥ 150 for any situational claim
- [ ] Weeks 1–4 reported separately
- [ ] Reproducibility: commit, snapshot ids, feature versions, seeds, package versions, config hash recorded; rerun reproduces artifact hash
- [ ] Odds conversions / EV verified with an independent implementation
- [ ] Claims in the handoff are each backed by a table; unsupported claims listed as findings

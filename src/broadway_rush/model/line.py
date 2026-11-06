"""Line model (SPEC 5.2a step 1): LightGBM predicts how many people are in line at a time before opening.

The line can't shrink as opening approaches (monotone constraint), and each show-day counts once in training. One
negative binomial spread, fitted on the latest 20% of training days using predictions from a model that didn't see
them, turns the prediction into a range.
"""

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import optimize, stats, special

from broadway_rush.model.table import LINE_FEATURES

PARAMS = {
    "objective": "poisson",
    "learning_rate": 0.04,
    "num_leaves": 15,
    "min_data_in_leaf": 25,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 5.0,
    "cat_smooth": 20,
    "min_data_per_group": 15,
    "max_cat_to_onehot": 4,
    "monotone_constraints_method": "advanced",
    "verbose": -1,
    "num_threads": 8,
    "seed": 7,
}
CATEGORICAL = ["show_code", "weekday", "show_type_code"]
MAX_ROUNDS = 800


def _matrix(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    x = df[features].astype(float).copy()
    if "show_code" in x:
        x["show_code"] = x["show_code"].where(x["show_code"] >= 0)  # unseen shows are "missing" to the trees
    return x


def _spread(y, mu, weight) -> float:
    """Maximum likelihood negative binomial spread (bigger = closer to Poisson), weighted so show-days count once."""

    def neg_log_lik(log_phi):
        phi = np.exp(log_phi)
        ll = (
            special.gammaln(y + phi) - special.gammaln(phi) - special.gammaln(y + 1)
            + phi * np.log(phi / (phi + mu)) + y * np.log(mu / (phi + mu))
        )
        return -np.sum(weight * ll)

    return float(np.exp(optimize.minimize_scalar(neg_log_lik, bounds=(-3, 6), method="bounded").x))


@dataclass
class LineModel:
    booster: lgb.Booster
    phi: float
    features: list[str]
    rounds: int

    def mean(self, df: pd.DataFrame) -> np.ndarray:
        return np.maximum(self.booster.predict(_matrix(df, self.features)), 1e-3)

    def contributions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Each feature's push on the log of the line, for "why this prediction"."""
        c = self.booster.predict(_matrix(df, self.features), pred_contrib=True)
        return pd.DataFrame(c[:, :-1], columns=self.features, index=df.index)

    def interval(self, mu, level: float = 0.8):
        p = self.phi / (self.phi + mu)
        tail = (1 - level) / 2
        return stats.nbinom.ppf(tail, self.phi, p), stats.nbinom.ppf(1 - tail, self.phi, p)


def _train(df, features, rounds, valid=None):
    constraints = [-1 if f == "hours_before" else 0 for f in features]
    cats = [f for f in CATEGORICAL if f in features]
    params = {**PARAMS, "monotone_constraints": constraints}
    d = lgb.Dataset(_matrix(df, features), df.people, weight=df.weight, categorical_feature=cats, free_raw_data=False)
    kw = {}
    if valid is not None:
        v = lgb.Dataset(_matrix(valid, features), valid.people, weight=valid.weight, reference=d, free_raw_data=False)
        kw = {"valid_sets": [v], "callbacks": [lgb.early_stopping(60, verbose=False)]}
    return lgb.train(params, d, num_boost_round=rounds, **kw)


def fit(line: pd.DataFrame, features: list[str] | None = None) -> LineModel:
    features = features or LINE_FEATURES
    days = np.sort(line.date.unique())
    split = days[int(len(days) * 0.8)]
    early, later = line[line.date < split], line[line.date >= split]
    first = _train(early, features, MAX_ROUNDS, later)
    rounds = max(first.best_iteration or MAX_ROUNDS, 50)
    mu = np.maximum(first.predict(_matrix(later, features), num_iteration=rounds), 1e-3)
    phi = _spread(later.people.to_numpy(), mu, later.weight.to_numpy())
    booster = _train(line, features, int(rounds * 1.1))
    return LineModel(booster, phi, features, rounds)

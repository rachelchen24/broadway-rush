"""Cutoff model (SPEC 5.2a step 2): Bayesian negative binomial for how many rush tickets a show has that day.

Stated counts go in as exact numbers, "got it at #7" as "at least", "sold out before me at #15" as "at most". Show
effects are pulled toward what's typical across shows, so a show with only lower bounds borrows a ceiling, and a new
show gets a wide range by itself.

JAX can't differentiate the usual negative binomial CDF (betainc) in its parameters, so the CDF is summed from the
probabilities of 0, 1, 2, ... tickets.
"""

import os
import time
from dataclasses import dataclass

os.environ.setdefault("XLA_FLAGS", "--xla_force_host_platform_device_count=4")

import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402
import numpyro  # noqa: E402
import numpyro.distributions as dist  # noqa: E402
import pandas as pd  # noqa: E402
from jax.scipy.special import gammaln  # noqa: E402
from numpyro.diagnostics import summary  # noqa: E402
from numpyro.infer import MCMC, NUTS, init_to_median  # noqa: E402

from broadway_rush.model.table import CUTOFF_FEATURES, tickets_bounds  # noqa: E402

numpyro.set_host_device_count(4)
MAX_ATTEMPTS = 3
GOOD_R_HAT = 1.05


def _model(x, show, n_shows, exact, lower, upper, kmax, phi_prior=(2.0, 0.4)):
    a = numpyro.sample("a", dist.Normal(jnp.log(12.0), 1.0))
    sigma = numpyro.sample("sigma", dist.HalfNormal(1.0))
    beta = numpyro.sample("beta", dist.Normal(0.0, 0.5).expand([x.shape[1]]))
    phi = numpyro.sample("phi", dist.Gamma(*phi_prior))
    z = numpyro.sample("z", dist.Normal(0.0, 1.0).expand([n_shows]))
    mu = jnp.exp(a + sigma * z[show] + x @ beta)

    # P(tickets <= k) for k = 0..kmax, with a leading 0 for k = -1
    j = jnp.arange(kmax + 1)
    m = mu[..., None]
    log_pmf = gammaln(j + phi) - gammaln(phi) - gammaln(j + 1.0) + phi * jnp.log(phi / (phi + m)) + j * jnp.log(m / (phi + m))
    cdf = jnp.concatenate([jnp.zeros_like(mu)[..., None], jnp.cumsum(jnp.exp(log_pmf), axis=-1)], axis=-1)
    cdf = jnp.clip(cdf, 0.0, 1.0)

    is_exact = exact >= 0
    has_low = lower >= 0
    has_up = upper >= 0
    at_upper = jnp.where(has_up, jnp.take_along_axis(cdf, (jnp.clip(upper, 0, kmax) + 1)[:, None], axis=1)[:, 0], 1.0)
    below_low = jnp.where(has_low, jnp.take_along_axis(cdf, jnp.clip(lower, 0, kmax + 1)[:, None], axis=1)[:, 0], 0.0)
    bounded = jnp.log(jnp.clip(at_upper - below_low, 1e-10, 1.0))
    exact_ll = jnp.take_along_axis(log_pmf, jnp.clip(exact, 0, kmax)[:, None], axis=1)[:, 0]
    numpyro.factor("labels", jnp.sum(jnp.where(is_exact, exact_ll, bounded)))


@dataclass
class CutoffModel:
    samples: dict
    show_index: dict
    center: dict
    scale: dict
    per_person: float
    diagnostics: dict
    seconds: float

    def _x(self, rows: pd.DataFrame) -> np.ndarray:
        cols = []
        for f in CUTOFF_FEATURES:
            v = rows[f].astype(float).to_numpy()
            v = (v - self.center[f]) / self.scale[f]
            cols.append(np.nan_to_num(v, nan=0.0))
        return np.column_stack(cols)

    def mean_draws(self, rows: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
        """Expected tickets, rows x draws. Shows the model hasn't seen draw a fresh show effect, so their range widens."""
        x = self._x(rows)
        s = self.samples
        n_draws = len(s["a"])
        z = np.zeros((len(rows), n_draws))
        for i, sid in enumerate(rows.show_id):
            k = self.show_index.get(sid)
            z[i] = s["z"][:, k] if k is not None else rng.standard_normal(n_draws)
        return np.exp(s["a"][None, :] + s["sigma"][None, :] * z + x @ s["beta"].T)

    def draws(self, rows: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
        """Simulated ticket counts, rows x draws."""
        mu = self.mean_draws(rows, rng)
        phi = self.samples["phi"][None, :]
        return rng.negative_binomial(phi, phi / (phi + mu))


def fit(cut: pd.DataFrame, per_person: float, warmup=300, samples=300, chains=4, seed=0, phi_prior=(2.0, 0.4)) -> CutoffModel:
    """The faster fit (SPEC 5.2 stop rule). 500 + 500 steps at target 0.9 with chains on separate devices didn't finish
    a window in 11 minutes on this laptop; running the chains together ("vectorized") is what made it practical."""
    start = time.time()
    x = tickets_bounds(cut, per_person)
    show_index = {s: i for i, s in enumerate(sorted(x.show_id.unique()))}
    center, scale = {}, {}
    cols = []
    for f in CUTOFF_FEATURES:
        v = x[f].astype(float)
        center[f], scale[f] = float(v.mean()), float(v.std() or 1.0)
        cols.append(((v - center[f]) / scale[f]).fillna(0.0).to_numpy())
    design = np.column_stack(cols)
    exact = x.exact.fillna(-1).astype(int).to_numpy()
    lower = x.lower_t.where(x.exact.isna()).fillna(-1).astype(int).to_numpy()
    upper = x.upper_t.where(x.exact.isna()).fillna(-1).astype(int).to_numpy()
    kmax = int(max(exact.max(), lower.max(), upper.max()) + 5)

    # Starting from the priors' middle: a random start can land where every "at least" label looks impossible, the slope
    # goes flat and a chain stays stuck (R-hat 6.16 on one window). If the chains still disagree, try again.
    for attempt in range(MAX_ATTEMPTS):
        kernel = NUTS(_model, target_accept_prob=0.8, max_tree_depth=7, init_strategy=init_to_median(num_samples=15))
        mcmc = MCMC(kernel, num_warmup=warmup, num_samples=samples, num_chains=chains, chain_method="vectorized",
                    progress_bar=False)
        mcmc.run(
            jax.random.PRNGKey(seed + attempt), jnp.array(design), jnp.array(x.show_id.map(show_index).to_numpy()),
            len(show_index), jnp.array(exact), jnp.array(lower), jnp.array(upper), kmax, phi_prior, extra_fields=("diverging",),
        )
        grouped = mcmc.get_samples(group_by_chain=True)
        stats = summary({k: np.asarray(v) for k, v in grouped.items()})
        rhat = max(float(np.nanmax(v["r_hat"])) for v in stats.values())
        ess = min(float(np.nanmin(v["n_eff"])) for v in stats.values())
        div = int(np.asarray(mcmc.get_extra_fields()["diverging"]).sum())
        if rhat <= GOOD_R_HAT:
            break
    flat = {k: np.asarray(v) for k, v in mcmc.get_samples().items()}
    seconds = time.time() - start
    return CutoffModel(flat, show_index, center, scale, per_person,
                       {"max_r_hat": round(rhat, 3), "min_ess": round(ess), "divergences": div, "attempts": attempt + 1,
                        "converged": rhat <= GOOD_R_HAT}, seconds)

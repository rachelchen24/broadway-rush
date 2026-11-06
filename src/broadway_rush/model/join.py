"""The join (SPEC 5.2a step 3): chance of a ticket if you arrive when the line has mean mu, given ticket draws T.

You get a ticket if everyone ahead of you and you can be served: per_person * (line + 1) <= T. Averaged over T draws,
which assumes line and tickets are unrelated once the features are known (first check: 0.09 within a show).
"""

import numpy as np
from scipy import special


def chance(mu: np.ndarray, phi: float, tickets: np.ndarray, per_person: float) -> np.ndarray:
    """mu: n values. tickets: n x draws. Returns the chance for each of the n."""
    ahead = np.floor(tickets / per_person) - 1  # the longest line you can find and still get one
    p = phi / (phi + mu)[:, None]
    # Negative binomial CDF at `ahead`; zero when even first in line wouldn't get one
    cdf = np.where(ahead >= 0, special.betainc(phi, np.maximum(ahead, 0) + 1, p), 0.0)
    return cdf.mean(axis=1)

"""
Min-max normalization utility.

Pure Python — no external dependencies.  Used by the Route Optimizer and
Fleet Matcher for candidate scoring.
"""


def min_max_normalize(values: list[float]) -> list[float]:
    """
    Normalize a list of floats to [0.0, 1.0] using min-max scaling.

    Edge cases
    ----------
    - If ``max == min`` (all values identical, or single-element list):
      returns a list of ``0.0`` of the same length.  This means every
      candidate gets the maximum possible contribution ``(1 - 0.0) = 1.0``
      for that factor, which is the correct behaviour when there is no
      variation to compare.
    - If ``values`` is empty: raises ``ValueError``.  Callers must check
      for empty candidate sets before calling this function.

    Parameters
    ----------
    values : list[float]
        Raw factor values across a set of candidates.

    Returns
    -------
    list[float]
        Normalized values in [0.0, 1.0], same length as *values*.

    Raises
    ------
    ValueError
        If *values* is empty.
    """
    if not values:
        raise ValueError(
            "min_max_normalize() received an empty list — "
            "callers must guard against empty candidate sets."
        )

    lo = min(values)
    hi = max(values)

    if hi == lo:
        return [0.0] * len(values)

    span = hi - lo
    return [(v - lo) / span for v in values]

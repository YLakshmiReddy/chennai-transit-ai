"""
rule_evaluator.py
-----------------
Orchestrates all hard and soft constraints to validate and rank candidate
routes for the Chennai public transit recommendation system.

The :class:`RuleEvaluator` wires together every constraint defined in
:mod:`knowledge_base.constraints` and exposes two public methods:

* :meth:`RuleEvaluator.validate` – run all constraints against a single
  route and return a structured verdict dict.
* :meth:`RuleEvaluator.rank_routes` – validate a list of routes, filter
  out infeasible ones, and sort the rest by a composite score that varies
  with the requested ``priority_mode``.

Composite scoring
~~~~~~~~~~~~~~~~~
The composite score for a route is::

    score = w_time  * normalised_time
          + w_fare  * normalised_fare
          + w_xfer  * num_transfers
          + w_mode  * mode_rank
          + penalty_score (from soft constraints)

Lower is better.  Weights vary with *priority_mode*:

============= ======= ======= ======= =======
priority_mode w_time  w_fare  w_xfer  w_mode
============= ======= ======= ======= =======
fastest       0.60    0.10    0.20    0.10
cheapest      0.10    0.60    0.20    0.10
comfortable   0.20    0.10    0.30    0.40
balanced      0.30    0.30    0.20    0.20
============= ======= ======= ======= =======
"""

from __future__ import annotations

from typing import List

from knowledge_base.constraints import (
    # Hard
    BudgetConstraint,
    MaxTransfersConstraint,
    TransferBufferConstraint,
    WheelchairConstraint,
    # Soft
    ModePreferenceSoftConstraint,
    PeakHourSoftConstraint,
    TransferCountSoftConstraint,
)
from knowledge_base.domain_knowledge import MODE_PRIORITY


# ---------------------------------------------------------------------------
# Weight presets
# ---------------------------------------------------------------------------

_WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    "fastest": {
        "time": 0.60,
        "fare": 0.10,
        "transfers": 0.20,
        "mode": 0.10,
    },
    "cheapest": {
        "time": 0.10,
        "fare": 0.60,
        "transfers": 0.20,
        "mode": 0.10,
    },
    "comfortable": {
        "time": 0.20,
        "fare": 0.10,
        "transfers": 0.30,
        "mode": 0.40,
    },
    "balanced": {
        "time": 0.30,
        "fare": 0.30,
        "transfers": 0.20,
        "mode": 0.20,
    },
}

_DEFAULT_MODE_RANK = max(MODE_PRIORITY.values()) + 1  # Fallback for unknown modes


# ---------------------------------------------------------------------------
# RuleEvaluator
# ---------------------------------------------------------------------------

class RuleEvaluator:
    """Evaluates and ranks transit routes using the constraint engine.

    All constraint instances are created once at construction time and
    reused across calls, making the evaluator cheap to call in tight loops.

    Parameters
    ----------
    extra_hard_constraints:
        Optional list of additional :class:`~knowledge_base.constraints.HardConstraint`
        instances to include beyond the built-in set.  Useful for injecting
        custom domain rules during testing or future extension.
    extra_soft_constraints:
        Optional list of additional :class:`~knowledge_base.constraints.SoftConstraint`
        instances to include beyond the built-in set.

    Examples
    --------
    >>> evaluator = RuleEvaluator()
    >>> verdict = evaluator.validate(route, user_prefs)
    >>> if verdict["valid"]:
    ...     print("Route is feasible, penalty =", verdict["penalty_score"])
    """

    def __init__(
        self,
        extra_hard_constraints=None,
        extra_soft_constraints=None,
    ):
        self._hard = [
            WheelchairConstraint(),
            BudgetConstraint(),
            MaxTransfersConstraint(),
            TransferBufferConstraint(),
        ] + (extra_hard_constraints or [])

        self._soft = [
            PeakHourSoftConstraint(),
            ModePreferenceSoftConstraint(),
            TransferCountSoftConstraint(),
        ] + (extra_soft_constraints or [])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, route: dict, user_prefs: dict) -> dict:
        """Run all constraints against a single route.

        Hard constraints are evaluated first; the first failure short-circuits
        the remaining hard checks (but all soft constraints are still scored
        for the reasoning trace).

        Parameters
        ----------
        route:
            Route dictionary (see :mod:`knowledge_base.constraints` for the
            full schema).
        user_prefs:
            User preference dictionary.

        Returns
        -------
        dict
            A structured verdict with the following keys:

            ``valid`` *(bool)*
                ``True`` if **all** hard constraints passed.
            ``violations`` *(list[str])*
                Human-readable messages for every hard constraint that failed.
            ``penalty_score`` *(float)*
                Sum of all soft-constraint penalties.  Meaningful only when
                ``valid`` is ``True``.
            ``reasoning_trace`` *(list[str])*
                Step-by-step log of every constraint check, suitable for
                display in an explainability panel.

        Examples
        --------
        >>> verdict = evaluator.validate(route, user_prefs)
        >>> verdict["valid"]
        True
        >>> verdict["violations"]
        []
        >>> verdict["penalty_score"]
        20.0
        """
        violations: List[str] = []
        reasoning_trace: List[str] = []

        # --- Hard constraints -------------------------------------------
        for constraint in self._hard:
            name = type(constraint).__name__
            passed, message = constraint.check(route, user_prefs)
            if passed:
                reasoning_trace.append(f"[PASS] {name}")
            else:
                violations.append(message)
                reasoning_trace.append(f"[FAIL] {name}: {message}")

        valid = len(violations) == 0

        # --- Soft constraints -------------------------------------------
        penalty_score = 0.0
        for constraint in self._soft:
            name = type(constraint).__name__
            pen = constraint.score(route, user_prefs)
            penalty_score += pen
            if pen > 0:
                reasoning_trace.append(
                    f"[PENALTY] {name}: +{pen:.1f}"
                )
            else:
                reasoning_trace.append(f"[OK] {name}: no penalty")

        reasoning_trace.append(
            f"[SUMMARY] valid={valid}, violations={len(violations)}, "
            f"penalty={penalty_score:.1f}"
        )

        return {
            "valid": valid,
            "violations": violations,
            "penalty_score": penalty_score,
            "reasoning_trace": reasoning_trace,
        }

    def rank_routes(
        self,
        routes: list,
        user_prefs: dict,
        priority_mode: str = "balanced",
    ) -> list:
        """Validate, score, and rank a list of candidate routes.

        Infeasible routes (those that fail at least one hard constraint) are
        excluded from the result entirely.  Feasible routes are assigned a
        composite score and returned in ascending order (lowest score first).

        The composite score combines normalised time, fare, transfer count,
        preferred-mode rank, and soft-constraint penalties, weighted according
        to *priority_mode*.

        Parameters
        ----------
        routes:
            List of route dicts to evaluate.
        user_prefs:
            User preference dictionary.
        priority_mode:
            One of ``"fastest"``, ``"cheapest"``, ``"comfortable"``,
            ``"balanced"``.  Controls the weight given to each scoring
            dimension.  Defaults to ``"balanced"``.  Unknown values also
            fall back to ``"balanced"``.

        Returns
        -------
        list
            Feasible routes sorted by composite score (ascending).  Each
            element is the original route dict augmented with two extra keys:

            ``_score`` *(float)*
                The final composite score (lower is better).
            ``_verdict`` *(dict)*
                The full verdict dict returned by :meth:`validate`.

        Examples
        --------
        >>> ranked = evaluator.rank_routes(candidates, user_prefs, "fastest")
        >>> best = ranked[0]
        >>> print(best["total_time_mins"], best["_score"])
        """
        weights = _WEIGHT_PRESETS.get(priority_mode, _WEIGHT_PRESETS["balanced"])

        # --- Validate all routes ----------------------------------------
        feasible = []
        for route in routes:
            verdict = self.validate(route, user_prefs)
            if verdict["valid"]:
                feasible.append((route, verdict))

        if not feasible:
            return []

        # --- Gather raw values for normalisation ------------------------
        times = [r.get("total_time_mins", 0) for r, _ in feasible]
        fares = [r.get("total_fare", 0.0) for r, _ in feasible]

        min_time, max_time = min(times), max(times)
        min_fare, max_fare = min(fares), max(fares)
        time_range = max_time - min_time or 1
        fare_range = max_fare - min_fare or 1

        # --- Score and annotate -----------------------------------------
        scored = []
        for route, verdict in feasible:
            norm_time = (route.get("total_time_mins", 0) - min_time) / time_range
            norm_fare = (route.get("total_fare", 0.0) - min_fare) / fare_range

            # Mode rank: best mode rank among all legs (lower = better)
            legs = route.get("legs", [])
            if legs:
                mode_rank = min(
                    MODE_PRIORITY.get(leg.get("mode", ""), _DEFAULT_MODE_RANK)
                    for leg in legs
                )
            else:
                mode_rank = _DEFAULT_MODE_RANK

            # Normalise mode rank to [0, 1]
            norm_mode = (mode_rank - 1) / (max(MODE_PRIORITY.values()))

            composite = (
                weights["time"] * norm_time
                + weights["fare"] * norm_fare
                + weights["transfers"] * route.get("num_transfers", 0) / 5  # cap at 5
                + weights["mode"] * norm_mode
                + verdict["penalty_score"] / 100  # scale penalties to same magnitude
            )

            annotated = dict(route)
            annotated["_score"] = composite
            annotated["_verdict"] = verdict
            scored.append(annotated)

        scored.sort(key=lambda r: r["_score"])
        return scored

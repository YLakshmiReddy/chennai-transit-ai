"""
constraints.py
--------------
Hard and soft constraint classes for the Chennai public transit route
recommendation system.

Design
~~~~~~
* **HardConstraint** – binary feasibility checks.  A route that violates any
  hard constraint is completely rejected and never shown to the user.
* **SoftConstraint** – penalty-based quality checks.  Violations add a numeric
  penalty to the route's composite score; the route is still eligible but
  ranked lower.

Route dict schema
~~~~~~~~~~~~~~~~~
::

    {
        "stops": [
            {"stop_id": str, "wheelchair_accessible": bool, "lat": float, "lon": float},
            ...
        ],
        "legs": [
            {
                "mode": str,            # "Metro" | "LocalBus" | "ExpressBus" | "SuburbanRail"
                "fare": float,          # INR
                "departure_time": str,  # "HH:MM" (24-h)
                "arrival_time": str,    # "HH:MM" (24-h)
                "distance_km": float,
            },
            ...
        ],
        "num_transfers": int,
        "total_fare": float,       # sum of leg fares
        "total_time_mins": int,    # end-to-end journey time
    }

User preferences dict schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

    {
        "wheelchair_required": bool,
        "max_budget": float,      # INR
        "max_transfers": int,
        "priority_mode": str,     # "Metro" | "LocalBus" | "ExpressBus" | "SuburbanRail" | ""
    }
"""

from __future__ import annotations

import abc
from typing import Tuple

from knowledge_base.domain_knowledge import PEAK_HOURS, TRANSFER_BUFFER_MINS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_time_to_minutes(time_str: str) -> int:
    """Convert a "HH:MM" string to minutes since midnight.

    Parameters
    ----------
    time_str:
        A 24-hour clock string such as ``"08:30"`` or ``"17:05"``.

    Returns
    -------
    int
        Total minutes elapsed since midnight.

    Raises
    ------
    ValueError
        If *time_str* is not in ``HH:MM`` format.
    """
    parts = time_str.strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse time string: {time_str!r}")
    return int(parts[0]) * 60 + int(parts[1])


def _is_peak_hour(time_str: str) -> bool:
    """Return *True* if the given ``HH:MM`` time falls within any peak window.

    Peak windows are defined in :data:`~knowledge_base.domain_knowledge.PEAK_HOURS`.

    Parameters
    ----------
    time_str:
        Departure or arrival time in ``"HH:MM"`` format.
    """
    try:
        total_mins = _parse_time_to_minutes(time_str)
    except ValueError:
        return False
    hour = total_mins // 60
    for start_h, end_h in PEAK_HOURS:
        if start_h <= hour < end_h:
            return True
    return False


# ---------------------------------------------------------------------------
# Abstract base classes
# ---------------------------------------------------------------------------

class HardConstraint(abc.ABC):
    """Abstract base for binary feasibility constraints.

    Sub-classes must implement :meth:`check`.  A route is considered
    *infeasible* if **any** hard constraint returns ``False``.
    """

    @abc.abstractmethod
    def check(self, route: dict, user_prefs: dict) -> Tuple[bool, str]:
        """Evaluate whether *route* satisfies this constraint.

        Parameters
        ----------
        route:
            Route dictionary (see module docstring for schema).
        user_prefs:
            User preference dictionary (see module docstring for schema).

        Returns
        -------
        (passed, message):
            * *passed* – ``True`` if the constraint is satisfied.
            * *message* – Human-readable explanation; empty string when
              ``passed`` is ``True``.
        """


class SoftConstraint(abc.ABC):
    """Abstract base for penalty-based quality constraints.

    Sub-classes must implement :meth:`score`.  The penalty returned is added
    to the route's composite score; higher scores are *worse*.
    """

    @abc.abstractmethod
    def score(self, route: dict, user_prefs: dict) -> float:
        """Calculate the penalty for *route* under this constraint.

        Parameters
        ----------
        route:
            Route dictionary (see module docstring for schema).
        user_prefs:
            User preference dictionary (see module docstring for schema).

        Returns
        -------
        float
            Non-negative penalty value.  ``0.0`` means no penalty.
        """


# ---------------------------------------------------------------------------
# Hard constraints
# ---------------------------------------------------------------------------

class WheelchairConstraint(HardConstraint):
    """Ensure every stop in the route is wheelchair-accessible.

    This constraint is only active when *user_prefs["wheelchair_required"]*
    is ``True``.  When active, every stop dict in ``route["stops"]`` must
    have ``wheelchair_accessible == True``; the first non-accessible stop
    causes a failure.
    """

    def check(self, route: dict, user_prefs: dict) -> Tuple[bool, str]:
        """Check wheelchair accessibility of all stops.

        Parameters
        ----------
        route:
            Route dictionary.
        user_prefs:
            Must contain ``wheelchair_required`` (bool).

        Returns
        -------
        (passed, message)
        """
        if not user_prefs.get("wheelchair_required", False):
            return True, ""

        for stop in route.get("stops", []):
            if not stop.get("wheelchair_accessible", False):
                sid = stop.get("stop_id", "unknown")
                return False, f"Stop {sid!r} is not wheelchair-accessible."

        return True, ""


class BudgetConstraint(HardConstraint):
    """Ensure the total fare does not exceed the user's budget.

    Compares ``route["total_fare"]`` against ``user_prefs["max_budget"]``.
    If ``max_budget`` is not set or is ``None``, the constraint passes
    unconditionally.
    """

    def check(self, route: dict, user_prefs: dict) -> Tuple[bool, str]:
        """Check that total fare is within budget.

        Parameters
        ----------
        route:
            Route dictionary; must contain ``total_fare`` (float).
        user_prefs:
            Must contain ``max_budget`` (float | None).

        Returns
        -------
        (passed, message)
        """
        max_budget = user_prefs.get("max_budget")
        if max_budget is None:
            return True, ""

        total_fare = route.get("total_fare", 0.0)
        if total_fare <= max_budget:
            return True, ""

        return (
            False,
            f"Total fare ₹{total_fare:.2f} exceeds budget ₹{max_budget:.2f}.",
        )


class MaxTransfersConstraint(HardConstraint):
    """Ensure the number of transfers does not exceed the user's limit.

    Compares ``route["num_transfers"]`` against ``user_prefs["max_transfers"]``.
    If ``max_transfers`` is not set or is ``None``, the constraint passes.
    """

    def check(self, route: dict, user_prefs: dict) -> Tuple[bool, str]:
        """Check that the transfer count is within the allowed maximum.

        Parameters
        ----------
        route:
            Route dictionary; must contain ``num_transfers`` (int).
        user_prefs:
            Must contain ``max_transfers`` (int | None).

        Returns
        -------
        (passed, message)
        """
        max_transfers = user_prefs.get("max_transfers")
        if max_transfers is None:
            return True, ""

        num_transfers = route.get("num_transfers", 0)
        if num_transfers <= max_transfers:
            return True, ""

        return (
            False,
            f"Route has {num_transfers} transfer(s), exceeding limit of {max_transfers}.",
        )


class TransferBufferConstraint(HardConstraint):
    """Ensure adequate connection time between consecutive legs.

    For each pair of adjacent legs the gap between the first leg's
    ``arrival_time`` and the second leg's ``departure_time`` must be at
    least :data:`~knowledge_base.domain_knowledge.TRANSFER_BUFFER_MINS`
    minutes (default 5 min).

    Legs whose times cannot be parsed are skipped (fail-open).
    """

    def check(self, route: dict, user_prefs: dict) -> Tuple[bool, str]:
        """Validate that all inter-leg gaps meet the minimum buffer.

        Parameters
        ----------
        route:
            Route dictionary; legs must contain ``departure_time`` and
            ``arrival_time`` strings in ``"HH:MM"`` format.
        user_prefs:
            Not used by this constraint; kept for interface consistency.

        Returns
        -------
        (passed, message)
        """
        legs = route.get("legs", [])
        for i in range(len(legs) - 1):
            arrival_str = legs[i].get("arrival_time", "")
            departure_str = legs[i + 1].get("departure_time", "")
            try:
                arrival_mins = _parse_time_to_minutes(arrival_str)
                departure_mins = _parse_time_to_minutes(departure_str)
            except (ValueError, AttributeError):
                continue  # Cannot validate; skip

            gap = departure_mins - arrival_mins
            if gap < TRANSFER_BUFFER_MINS:
                return (
                    False,
                    f"Transfer at leg {i + 1}→{i + 2} has only {gap} min gap "
                    f"(minimum {TRANSFER_BUFFER_MINS} min required).",
                )

        return True, ""


# ---------------------------------------------------------------------------
# Soft constraints
# ---------------------------------------------------------------------------

class PeakHourSoftConstraint(SoftConstraint):
    """Apply a penalty when any leg departs or arrives during peak hours.

    Adds **+20** to the penalty score for each leg that departs or arrives
    during the morning (8–10 AM) or evening (5–8 PM) rush.

    This encourages the ranker to prefer off-peak journeys when alternatives
    exist, without completely ruling out peak-hour routes.
    """

    PENALTY_PER_LEG: float = 20.0

    def score(self, route: dict, user_prefs: dict) -> float:
        """Calculate peak-hour penalty across all legs.

        Parameters
        ----------
        route:
            Route dictionary; legs must contain ``departure_time`` and/or
            ``arrival_time`` strings in ``"HH:MM"`` format.
        user_prefs:
            Not used; kept for interface consistency.

        Returns
        -------
        float
            Total penalty (multiples of 20).
        """
        penalty = 0.0
        for leg in route.get("legs", []):
            if _is_peak_hour(leg.get("departure_time", "")):
                penalty += self.PENALTY_PER_LEG
            elif _is_peak_hour(leg.get("arrival_time", "")):
                penalty += self.PENALTY_PER_LEG
        return penalty


class ModePreferenceSoftConstraint(SoftConstraint):
    """Penalise LocalBus legs on long-distance segments (> 10 km).

    Adds **+10** per such leg.  Local buses are suitable for short hops but
    are slow and uncomfortable over longer distances; a Metro or Express Bus
    would be preferred.
    """

    PENALTY_PER_LEG: float = 10.0
    DISTANCE_THRESHOLD_KM: float = 10.0

    def score(self, route: dict, user_prefs: dict) -> float:
        """Calculate mode-preference penalty.

        Parameters
        ----------
        route:
            Route dictionary; legs must contain ``mode`` (str) and
            ``distance_km`` (float).
        user_prefs:
            Not used; kept for interface consistency.

        Returns
        -------
        float
            Total penalty.
        """
        penalty = 0.0
        for leg in route.get("legs", []):
            if (
                leg.get("mode") == "LocalBus"
                and leg.get("distance_km", 0.0) > self.DISTANCE_THRESHOLD_KM
            ):
                penalty += self.PENALTY_PER_LEG
        return penalty


class TransferCountSoftConstraint(SoftConstraint):
    """Apply an incremental penalty for each transfer beyond the first.

    One transfer is considered acceptable; each additional transfer adds
    **+5** to the penalty score, discouraging unnecessarily complex routes.
    """

    PENALTY_PER_EXTRA_TRANSFER: float = 5.0

    def score(self, route: dict, user_prefs: dict) -> float:
        """Calculate transfer-count penalty.

        Parameters
        ----------
        route:
            Route dictionary; must contain ``num_transfers`` (int).
        user_prefs:
            Not used; kept for interface consistency.

        Returns
        -------
        float
            Total penalty (0 for 0–1 transfers, +5 per transfer above 1).
        """
        num_transfers = route.get("num_transfers", 0)
        extra = max(0, num_transfers - 1)
        return extra * self.PENALTY_PER_EXTRA_TRANSFER

from dataclasses import dataclass
from math import ceil, isfinite, sqrt
from typing import Protocol


class _ProfileLike(Protocol):
    """Structural type for backward-compatible conversion from old profiles."""
    runway_half_length: int
    packet_length: int
    evolution_time: float


@dataclass(frozen=True, slots=True)
class WalkParameters:
    runway_half_length: int
    packet_length: int
    evolution_time: float

    def __post_init__(self) -> None:
        if isinstance(self.runway_half_length, bool) or not isinstance(
            self.runway_half_length, int
        ):
            raise TypeError("runway_half_length must be an integer")
        if isinstance(self.packet_length, bool) or not isinstance(self.packet_length, int):
            raise TypeError("packet_length must be an integer")

        if self.runway_half_length < 1:
            raise ValueError("runway_half_length must be positive")
        if self.packet_length < 1:
            raise ValueError("packet_length must be positive")

        # A packet occupying positions -L+1, ..., 0 needs L sites. Under the
        # project's finite-runway convention, the attachment site contributes
        # the +1 here.
        if self.packet_length > self.runway_half_length + 1:
            raise ValueError(
                "packet_length cannot exceed runway_half_length + 1"
            )

        if not isfinite(float(self.evolution_time)):
            raise ValueError("evolution_time must be finite")
        if self.evolution_time < 0:
            raise ValueError("evolution_time cannot be negative")

    @classmethod
    def from_profile(cls, profile: _ProfileLike) -> "WalkParameters":
        """Extract walk-defining values from the project's legacy profile.

        This is the compatibility bridge: the old profile can continue to own
        calibrated fields such as ``threshold`` and ``query_steps`` while the
        walk itself consumes only the three values defined here.
        """

        return cls(
            runway_half_length=profile.runway_half_length,
            packet_length=profile.packet_length,
            evolution_time=profile.evolution_time,
        )


def _validate_leaf_count(leaf_count: int) -> None:
    if isinstance(leaf_count, bool) or not isinstance(leaf_count, int):
        raise TypeError("leaf_count must be an integer")
    if leaf_count < 1 or leaf_count & (leaf_count - 1):
        raise ValueError("leaf_count must be a positive power of two")


def theoretical_parameters(
    leaf_count: int,
    *,
    gamma: float = 8.0,
    runway_factor: float = 1.0,
) -> WalkParameters:
    """Derive one finite parameter family from a fixed asymptotic rule.

    The construction uses

        L = ceil(gamma * sqrt(N))
        M = ceil(runway_factor * L**2)
        t = L / 2

    where ``N`` is the number of leaves.  ``gamma`` and ``runway_factor`` are
    explicit finite-size experiment constants; callers should keep them fixed
    when studying scaling with N rather than re-fitting them independently for
    every tree size.

    This helper does not replace the project's calibrated profiles. It supplies
    an opt-in, paper-oriented parameter family for new experiments.
    """

    _validate_leaf_count(leaf_count)

    gamma = float(gamma)
    runway_factor = float(runway_factor)

    if not isfinite(gamma) or gamma <= 0:
        raise ValueError("gamma must be finite and positive")
    if not isfinite(runway_factor) or runway_factor <= 0:
        raise ValueError("runway_factor must be finite and positive")

    packet_length = ceil(gamma * sqrt(leaf_count))
    runway_half_length = ceil(runway_factor * packet_length**2)

    return WalkParameters(
        runway_half_length=runway_half_length,
        packet_length=packet_length,
        evolution_time=packet_length / 2,
    )

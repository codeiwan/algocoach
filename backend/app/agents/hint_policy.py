from dataclasses import dataclass
from enum import StrEnum

from app.schemas.hint import HintLevel, HintSource


class HintDecisionReason(StrEnum):
    """Reason for allowing or rejecting a hint request."""

    ALLOWED = "ALLOWED"
    AUTOMATIC_DISABLED = "AUTOMATIC_DISABLED"
    MAX_LEVEL_REACHED = "MAX_LEVEL_REACHED"


@dataclass(frozen=True, slots=True)
class HintDecision:
    """Result of evaluating the hint progression policy."""

    allowed: bool
    reason: HintDecisionReason
    next_level: HintLevel | None


# A user must progress through hint levels in order.
NEXT_HINT_LEVEL: dict[HintLevel | None, HintLevel | None] = {
    None: HintLevel.DIRECTION,
    HintLevel.DIRECTION: HintLevel.ALGORITHM,
    HintLevel.ALGORITHM: HintLevel.IMPLEMENTATION,
    HintLevel.IMPLEMENTATION: None,
}


def evaluate_hint_policy(
    previous_level: HintLevel | None,
    source: HintSource,
) -> HintDecision:
    """
    Decide whether to issue the next progressive hint.

    This policy does not generate hints or call an LLM.
    It does not modify session state.

    Automatic hints remain disabled until reliable
    stuck detection and intervention rules are available.
    """

    # Do not provide unsolicited hints at this stage.
    if source == HintSource.AUTOMATIC:
        return HintDecision(
            allowed=False,
            reason=HintDecisionReason.AUTOMATIC_DISABLED,
            next_level=None,
        )

    next_level = NEXT_HINT_LEVEL[previous_level]

    # No further hint escalation beyond implementation guidance.
    if next_level is None:
        return HintDecision(
            allowed=False,
            reason=HintDecisionReason.MAX_LEVEL_REACHED,
            next_level=None,
        )

    return HintDecision(
        allowed=True,
        reason=HintDecisionReason.ALLOWED,
        next_level=next_level,
    )

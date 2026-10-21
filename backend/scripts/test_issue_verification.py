"""Offline tests for tri-state issue verification."""

from pathlib import Path
import sys

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from app.llm.issue_verification import (
    CandidateVerdict,
    VerificationOutput,
    apply_verification,
    resolve_verdicts,
)

from app.schemas.agent import CodeIssue, IssueSeverity

from app.schemas.submission_review import (
    ReviewCategory,
    ReviewFinding,
    ReviewSeverity,
)


def verdict(
    index: int,
    status: str,
    reason: str = "판단 근거 확인",
) -> CandidateVerdict:
    return CandidateVerdict(
        index=index,
        status=status,
        justification=reason,
    )


resolution = resolve_verdicts(
    VerificationOutput(
        verdicts=[
            verdict(0, "REFUTED"),
            verdict(1, "SUPPORTED"),
            verdict(2, "UNRESOLVED"),
        ]
    ),
    3,
)

assert resolution.refuted == {0}
assert resolution.supported == {1}
assert resolution.unresolved == {2}


issues = [
    CodeIssue(
        category="logic",
        severity=IssueSeverity.CRITICAL,
        description=f"후보 {index}",
        evidence="AI 정적 분석",
    )
    for index in range(3)
]

filtered = apply_verification(
    issues,
    resolution,
    IssueSeverity.INFO,
)

assert len(filtered) == 2
assert filtered[0].description == "후보 1"
assert filtered[0].severity == IssueSeverity.CRITICAL
assert filtered[1].severity == IssueSeverity.INFO
assert filtered[1].description.startswith(
    "추가 검증이 필요한 가능성"
)


review = ReviewFinding(
    category=ReviewCategory.LOGIC,
    severity=ReviewSeverity.HIGH,
    description="검토 내용",
    evidence="검토 근거",
)

unresolved = resolve_verdicts(
    VerificationOutput(
        verdicts=[verdict(0, "UNRESOLVED")]
    ),
    1,
)

assert apply_verification(
    [review],
    unresolved,
    ReviewSeverity.LOW,
)[0].severity == ReviewSeverity.LOW


# Malformed or duplicate indexes must never silently
# eliminate a legitimate issue.

for data, count in (
    (
        [
            verdict(0, "REFUTED"),
            verdict(0, "SUPPORTED"),
        ],
        2,
    ),
    (
        [verdict(4, "REFUTED")],
        2,
    ),
):
    result = resolve_verdicts(
        VerificationOutput(verdicts=data),
        count,
    )

    assert result.unresolved == set(range(count))


assert resolve_verdicts(
    VerificationOutput(
        verdicts=[verdict(0, "SUPPORTED")]
    ),
    2,
).unresolved == {1}


assert resolve_verdicts(
    VerificationOutput(
        verdicts=[verdict(0, "REFUTED", "  ")]
    ),
    1,
).unresolved == {0}


print("PASS: tri-state issue verification (7 groups)")

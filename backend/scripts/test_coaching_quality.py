"""Offline correctness regression + optional real model comparison.

From the backend directory:
    python scripts/test_coaching_quality.py
    python scripts/test_coaching_quality.py --live --confirm-live

The offline checks run NO LLM calls.
Live mode makes exactly two analysis requests to a running
OpenAI-configured AlgoCoach backend (billing applies).
"""

from __future__ import annotations

import argparse
from collections import deque
from itertools import permutations
import json
from pathlib import Path
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from app.llm.coaching_quality import COACHING_QUALITY_INSTRUCTIONS


PROBLEM = """3551. Minimum Swaps to Sort by Digit Sum
Given distinct positive integers nums, sort by increasing digit sum.
When digit sums tie, the smaller integer comes first.
Return the minimum number of arbitrary swaps to reach this order.
Constraints: 1 <= len(nums) <= 100000; 1 <= nums[i] <= 1000000000.
Example: nums=[18,43,34,16] -> 2.
The platform calls Solution.minSwaps(nums) and provides typing.List.
"""

CORRECT_CODE = """class Solution:
    def minSwaps(self, nums: List[int]) -> int:
        def digit_sum(num: int) -> int:
            total = 0
            while num > 0:
                total += num % 10
                num //= 10
            return total

        length = len(nums)
        sorted_order = sorted(
            range(length),
            key=lambda idx: (digit_sum(nums[idx]), nums[idx])
        )

        visited = [False] * length
        cycle_count = 0

        for start in range(length):
            if visited[start]:
                continue
            cycle_count += 1
            current = start
            while not visited[current]:
                visited[current] = True
                current = sorted_order[current]

        return length - cycle_count
"""

# Deliberately incorrect: loses the required numeric tie breaker.
INCORRECT_CODE = CORRECT_CODE.replace(
    "key=lambda idx: (digit_sum(nums[idx]), nums[idx])",
    "key=lambda idx: digit_sum(nums[idx])",
)


def cycle_count(mapping: tuple[int, ...]) -> int:
    visited = [False] * len(mapping)
    count = 0

    for start in range(len(mapping)):
        if visited[start]:
            continue

        count += 1
        current = start

        while not visited[current]:
            visited[current] = True
            current = mapping[current]

    return count


def inverse(mapping: tuple[int, ...]) -> tuple[int, ...]:
    result = [0] * len(mapping)

    for source, target in enumerate(mapping):
        result[target] = source

    return tuple(result)


def min_swaps_bfs(target: tuple[int, ...]) -> int:
    """Independent minimal-swap reference for short permutations."""

    start = tuple(range(len(target)))

    if start == target:
        return 0

    queue = deque([(start, 0)])
    visited = {start}

    while queue:
        state, distance = queue.popleft()

        for i in range(len(state)):
            for j in range(i + 1, len(state)):
                swapped = list(state)
                swapped[i], swapped[j] = swapped[j], swapped[i]
                neighbor = tuple(swapped)

                if neighbor == target:
                    return distance + 1

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))

    raise AssertionError("Unreachable target permutation")


def offline_regression() -> None:
    assert "admissible concrete input" in COACHING_QUALITY_INSTRUCTIONS
    assert "inverse" in COACHING_QUALITY_INSTRUCTIONS

    total = 0

    for length in range(1, 7):
        for order in permutations(range(length)):
            original_to_sorted = inverse(order)

            assert (
                cycle_count(order)
                == cycle_count(original_to_sorted)
            )

            expected = len(order) - cycle_count(order)

            if length <= 5:
                assert expected == min_swaps_bfs(order)

            total += 1

    # Execute only trusted hardcoded fixtures in this test.
    # The AlgoCoach backend must not execute submitted user code.
    correct_scope = {"List": list}
    incorrect_scope = {"List": list}

    exec(CORRECT_CODE, correct_scope)
    exec(INCORRECT_CODE, incorrect_scope)

    solution = correct_scope["Solution"]()
    broken = incorrect_scope["Solution"]()

    assert solution.minSwaps([37, 100]) == 1
    assert solution.minSwaps([22, 14, 33, 7]) == 0
    assert solution.minSwaps([18, 43, 34, 16]) == 2
    assert broken.minSwaps([18, 43, 34, 16]) == 3

    print(
        f"PASS: 순열·역순열 사이클 불변성 "
        f"({total}개 순열)"
    )
    print("PASS: 최소 교환 BFS 독립 검산 (길이 1~5)")
    print("PASS: 정답 코드 예제 3개")
    print("PASS: 잘못된 tie-break 코드의 반례 검출")
    print("PASS: 코칭 근거 기준 모듈 로드")
    print("오프라인 회귀 검증 완료: LLM 호출 0회")


def live_case(
    name: str,
    code: str,
    revision: int,
    base_url: str,
) -> int:
    payload = {
        "session_id": f"quality-{uuid.uuid4().hex}",
        "code_revision": revision,
        "problem_text": PROBLEM,
        "current_code": code,
        "language": "python",
    }

    request = Request(
        base_url.rstrip("/") + "/api/v1/dev/analyze",
        data=json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=75) as response:
            result = json.load(response)

    except HTTPError as error:
        raise RuntimeError(
            f"{name}: HTTP {error.code}: "
            f"{error.read()[:500]!r}"
        ) from error

    except URLError as error:
        raise RuntimeError(
            f"{name}: 백엔드 연결 실패: {error}"
        ) from error

    if result.get("analyzed_revision") != revision:
        raise AssertionError(
            f"{name}: 분석 Revision 불일치"
        )

    issues = result.get("issues")

    if not isinstance(issues, list):
        raise AssertionError(
            f"{name}: issues 타입이 list가 아닙니다"
        )

    print(
        f"\n[{name}] "
        f"{result.get('progress_status')} "
        f"/ issues={len(issues)}"
    )
    print(
        "요약:",
        result.get("summary", "")[:900],
    )

    for index, issue in enumerate(issues, 1):
        print(
            f"  {index}. {issue.get('severity')}: "
            f"{issue.get('description')}"
        )
        print(
            "     근거:",
            issue.get("evidence", "")[:600],
        )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    args = parser.parse_args()

    offline_regression()

    if not args.live:
        return 0

    if not args.confirm_live:
        parser.error(
            "라이브 호출은 --live --confirm-live가 "
            "모두 필요합니다"
        )

    print(
        "\n실제 OpenAI 백엔드 분석 2회 요청 "
        "(과금 가능)."
    )

    correct_issues = live_case(
        "올바른 순열 코드",
        CORRECT_CODE,
        101,
        args.base_url,
    )

    incorrect_issues = live_case(
        "tie-break 누락 코드",
        INCORRECT_CODE,
        102,
        args.base_url,
    )

    good = not correct_issues
    bad = any(
        issue.get("severity") in {"CRITICAL", "WARNING"}
        for issue in incorrect_issues
    )

    print(
        "\n라이브 회귀 결과:",
        "PASS" if good and bad else "REVIEW NEEDED",
    )
    print(
        "- 정답 코드 불필요한 경고 없음:",
        "PASS" if good else "FAIL",
    )
    print(
        "- 오류 코드 위험 탐지:",
        "PASS" if bad else "FAIL",
    )

    return 0 if good and bad else 1


if __name__ == "__main__":
    sys.exit(main())

"""
AlgoCoach AI coaching integration smoke test.

Usage:
    python scripts/coaching_smoke.py --mode mock

    python scripts/coaching_smoke.py --mode live --confirm-live

Mock mode:
    Requires the backend to be running with LLM_PROVIDER=mock.
    Checks API contracts and progressive hint state.

Live mode:
    Requires the backend to be running with LLM_PROVIDER=openai.
    Makes exactly ONE code-analysis API request.
    Prints the model output for manual quality evaluation.

No SQLite records are created by this script.
"""

import argparse
import json
import sys
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROBLEM = """\
정수 N이 주어진다.
1부터 N까지의 합을 출력하시오.

입력:
첫째 줄에 정수 N이 주어진다.

제약:
1 <= N <= 10000

출력:
1부터 N까지의 합을 출력한다.
"""

# Deliberately incorrect but syntactically valid.
INCORRECT_CODE = """\
n = int(input())
print(n)
"""

# A deliberately unfinished piece of code.
INCOMPLETE_CODE = """\
numbers = [int(x) for x in input().split(
"""

EXPECTED_HINT_LEVELS = (
    "DIRECTION",
    "ALGORITHM",
    "IMPLEMENTATION",
)


class ApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        data = None

        headers = {
            "Accept": "application/json",
        }

        if payload is not None:
            data = json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8")

            headers["Content-Type"] = "application/json"

        request = Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                return (
                    response.status,
                    json.load(response),
                )

        except HTTPError as error:
            raw = error.read().decode(
                "utf-8",
                errors="replace",
            )

            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"detail": raw}

            return error.code, body

        except URLError as error:
            raise RuntimeError(
                "백엔드에 연결할 수 없습니다. "
                "127.0.0.1:8000 서버 실행 여부를 확인하세요."
            ) from error


def require(
    condition: bool,
    message: str,
    detail: Any = None,
) -> None:
    if not condition:
        raise AssertionError(
            f"{message}\n실제 결과: {detail}"
        )

    print(f"PASS: {message}")


def analysis_payload(
    session_id: str,
    revision: int,
    code: str,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "code_revision": revision,
        "problem_text": PROBLEM,
        "current_code": code,
        "language": "python",
    }


def check_health(client: ApiClient) -> None:
    status, body = client.request(
        "GET",
        "/api/v1/health",
    )

    require(
        status == 200 and body.get("status") == "ok",
        "Backend health check",
        (status, body),
    )


def run_mock_suite(client: ApiClient) -> None:
    print("\n=== AlgoCoach Mock 통합 검증 ===")
    print("백엔드가 반드시 LLM_PROVIDER=mock이어야 합니다.\n")

    check_health(client)

    session_id = "smoke-" + uuid.uuid4().hex

    # --------------------------------------------
    # 1. Analyze a stable code snapshot.
    # --------------------------------------------

    status, analysis = client.request(
        "POST",
        "/api/v1/dev/analyze",
        analysis_payload(
            session_id,
            revision=10,
            code=INCORRECT_CODE,
        ),
    )

    require(
        status == 200,
        "코드 분석 API HTTP 200",
        (status, analysis),
    )

    require(
        analysis.get("analyzed_revision") == 10,
        "분석 결과 Revision 일치",
        analysis,
    )

    require(
        isinstance(analysis.get("summary"), str),
        "분석 결과 summary 존재",
        analysis,
    )

    # --------------------------------------------
    # 2. Unfinished code must not crash the API.
    #
    # The mock cannot evaluate coaching quality.
    # This only validates the request/response path.
    # --------------------------------------------

    status, partial_analysis = client.request(
        "POST",
        "/api/v1/dev/analyze",
        analysis_payload(
            session_id,
            revision=11,
            code=INCOMPLETE_CODE,
        ),
    )

    require(
        status == 200,
        "미완성 코드에 대한 분석 API 안정성",
        (status, partial_analysis),
    )

    require(
        partial_analysis.get("analyzed_revision") == 11,
        "미완성 코드 Revision 일치",
        partial_analysis,
    )

    # --------------------------------------------
    # 3. Progressive hints.
    # --------------------------------------------

    hint_session_id = "hints-" + uuid.uuid4().hex

    hint_payload = analysis_payload(
        hint_session_id,
        revision=12,
        code=INCORRECT_CODE,
    )

    for expected_level in EXPECTED_HINT_LEVELS:
        status, hint = client.request(
            "POST",
            "/api/v1/dev/hints/next",
            hint_payload,
        )

        require(
            status == 200,
            f"{expected_level} 힌트 HTTP 200",
            (status, hint),
        )

        require(
            hint.get("level") == expected_level,
            f"{expected_level} 힌트 순서 유지",
            hint,
        )

    # Fourth hint request should be blocked.
    status, body = client.request(
        "POST",
        "/api/v1/dev/hints/next",
        hint_payload,
    )

    require(
        status == 409,
        "3단계 이후 추가 힌트 요청 차단",
        (status, body),
    )

    # --------------------------------------------
    # 4. Pre-submission review.
    # --------------------------------------------

    review_payload = analysis_payload(
        "review-" + uuid.uuid4().hex,
        revision=20,
        code=INCORRECT_CODE,
    )

    status, review = client.request(
        "POST",
        "/api/v1/dev/submission/review",
        review_payload,
    )

    require(
        status == 200,
        "제출 전 점검 API HTTP 200",
        (status, review),
    )

    require(
        review.get("reviewed_revision") == 20,
        "제출 전 점검 Revision 일치",
        review,
    )

    require(
        review.get("status") == "UNCERTAIN",
        "Mock 점검 결과가 실제 채점처럼 표시되지 않음",
        review,
    )

    require(
        isinstance(review.get("findings"), list),
        "제출 전 점검 findings 구조 확인",
        review,
    )

    print("\nAll Mock integration tests passed.")
    print(
        "주의: Mock 통과는 실제 AI 코칭 정확도를 "
        "보장하지 않습니다."
    )


def run_live_suite(client: ApiClient) -> None:
    print("\n=== AlgoCoach 실제 OpenAI 코칭 검증 ===")
    print("코드 분석 요청을 정확히 1회 전송합니다.\n")

    check_health(client)

    session_id = "live-smoke-" + uuid.uuid4().hex

    payload = analysis_payload(
        session_id,
        revision=100,
        code=INCORRECT_CODE,
    )

    print("검증할 문제:")
    print(PROBLEM)

    print("검증할 코드:")
    print(INCORRECT_CODE)

    status, result = client.request(
        "POST",
        "/api/v1/dev/analyze",
        payload,
    )

    require(
        status == 200,
        "실제 AI 분석 API HTTP 200",
        (status, result),
    )

    require(
        result.get("analyzed_revision") == 100,
        "실제 AI 분석 Revision 일치",
        result,
    )

    require(
        isinstance(result.get("summary"), str)
        and bool(result["summary"].strip()),
        "실제 AI 분석 summary 생성",
        result,
    )

    require(
        isinstance(result.get("issues"), list),
        "실제 AI 분석 issues 구조 확인",
        result,
    )

    print("\n=== 실제 AI 분석 결과 ===")

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n=== 사람이 확인할 코칭 품질 기준 ===")
    print(
        "1. 코드는 N을 출력할 뿐 1부터 N까지의 합을 "
        "계산하지 않는다는 점을 이해했는가?"
    )
    print(
        "2. 실제 코드에 없는 로직이나 실행 결과를 "
        "지어내지 않았는가?"
    )
    print(
        "3. 문제 해결에 필요한 방향을 제시하면서 "
        "불필요하게 정답 코드를 노출하지 않았는가?"
    )
    print(
        "4. 분석 근거와 코드 Revision이 "
        "실제 요청 내용과 일치하는가?"
    )

    print(
        "\nLive API contract tests passed. "
        "코칭 품질의 최종 판정은 출력 결과를 "
        "직접 검토해야 합니다."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AlgoCoach coaching integration smoke test"
    )

    parser.add_argument(
        "--mode",
        choices=("mock", "live"),
        default="mock",
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Confirm a paid OpenAI analysis request.",
    )

    args = parser.parse_args()

    if args.mode == "live" and not args.confirm_live:
        print(
            "실제 OpenAI 요청에는 --confirm-live 옵션이 필요합니다.",
            file=sys.stderr,
        )
        return 2

    client = ApiClient(
        base_url=args.base_url,
        timeout=90.0 if args.mode == "live" else 20.0,
    )

    try:
        if args.mode == "mock":
            run_mock_suite(client)
        else:
            run_live_suite(client)

    except (AssertionError, RuntimeError) as error:
        print(
            f"\nFAIL: {error}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Workers AI decision-model adapter: answer parsing against recorded responses,
the request it sends, retries, errors, cost and concurrency. No network: every
request goes to an httpx.MockTransport.
"""

import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import httpx
import pytest

from adapters.decision.common import ConcurrencyLimit
from adapters.decision.parsing import choice_of, score_of, yes_no_of
from adapters.decision.workers_ai import (
    WorkersAIDecisionModel,
    WorkersAIOptions,
    _retry_after,
    wire_question,
)
from domain.decision.exceptions import (
    DecisionModelError,
    DecisionModelNotConfiguredError,
    DecisionModelRequestError,
    DecisionModelUnavailableError,
)
from domain.decision.value_objects import (
    ChoiceAnswer,
    ChoiceQuestion,
    ScoreAnswer,
    ScoreQuestion,
    YesNoAnswer,
    YesNoQuestion,
)

FIXTURES = Path(__file__).parents[3] / "fixtures" / "decision_models" / "workers_ai_responses.json"
RECORDED = json.loads(FIXTURES.read_text())["calls"]

HOUSE_QUESTIONS = {
    "kind": ChoiceQuestion(
        instructions=(
            "What kind of house record does this text describe? Choose 'none' if no"
            " listed kind fits."
        ),
        criteria={
            "activity": "Something a person did at the house",
            "asset": "A physical thing the house contains",
            "issue": "A problem with the house",
        },
    ),
    "significance": ScoreQuestion(
        instructions="How significant is this event for the upkeep of the house?",
        levels=["trivial", "minor", "moderate", "major"],
    ),
    "is_maintenance": YesNoQuestion(instructions="This text describes routine maintenance."),
}


def make_model(handler, **kwargs) -> WorkersAIDecisionModel:
    option_values = {"account_id": "acct-123", "api_token": "token-abc"}
    for key in ("account_id", "api_token", "request_model", "base_url"):
        if key in kwargs:
            option_values[key] = kwargs.pop(key)
    defaults = dict(
        model="@cf/vendor/some-model",
        options=WorkersAIOptions(**option_values),
        price_per_mtok_in=0.09,
        backoff_seconds=0.0,
        transport=httpx.MockTransport(handler),
        async_transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )
    defaults.update(kwargs)
    return WorkersAIDecisionModel("instance-a", **defaults)


def respond_with(call: str, sent: list | None = None):
    recorded = RECORDED[call]

    def handler(request: httpx.Request) -> httpx.Response:
        if sent is not None:
            sent.append(request)
        return httpx.Response(recorded["status"], json=recorded["response"])

    return handler


# ---- parsing helpers, against recorded answers ----


def test_choice_of_reads_recorded_choice_answer():
    wire = RECORDED["house_activity"]["response"]["result"]["answers"]["kind"]
    choice, probabilities, confidence = choice_of(wire)
    assert choice == "activity"
    assert probabilities["activity"] == pytest.approx(0.8677)
    assert set(probabilities) == {"activity", "asset", "issue", "none"}
    assert confidence == pytest.approx(0.68)


def test_choice_of_falls_back_to_arg_max_and_alternative_keys():
    assert choice_of({"probabilities": {"a": 0.2, "b": 0.7}})[0] == "b"
    assert choice_of({"answer": "a", "probabilities": {"a": 0.2, "b": 0.7}})[0] == "a"
    assert choice_of({}) == (None, {}, None)


def test_score_of_reads_index_keyed_distribution_from_recorded_answer():
    # Recorded responses key score probabilities by level index, not as a list
    wire = RECORDED["house_activity"]["response"]["result"]["answers"]["significance"]
    score, distribution = score_of(wire, 4)
    assert score == pytest.approx(1.3449)
    assert distribution == pytest.approx([0.1233, 0.4598, 0.3656, 0.0513])


def test_score_of_list_distribution_and_expected_value():
    score, distribution = score_of({"distribution": [0.0, 0.5, 0.5]}, 3)
    assert distribution == [0.0, 0.5, 0.5]
    assert score == pytest.approx(1.5)


def test_choice_of_empty_choice_falls_back_to_arg_max():
    assert choice_of({"choice": "", "probabilities": {"a": 0.2, "b": 0.7}})[0] == "b"


def test_choice_of_rejects_options_not_offered():
    assert choice_of({"choice": "none"}, offered={"a", "b"})[0] is None


def test_score_of_ignores_list_of_the_wrong_length():
    assert score_of({"probabilities": [0.5, 0.5]}, 3) == (None, [])


def test_score_of_clamps_out_of_range_score_without_distribution():
    assert score_of({"score": 4}, 4) == (3.0, [])


def test_yes_no_of_reads_noul_and_alternatives():
    wire = RECORDED["house_activity"]["response"]["result"]["answers"]["is_maintenance"]
    assert yes_no_of(wire) == pytest.approx(0.9293)
    assert yes_no_of({"probability": 0.4}) == 0.4
    assert yes_no_of({"noul": "high"}) is None


# ---- the request ----


def test_wire_questions_map_yes_no_to_noul_and_add_none():
    assert wire_question(YesNoQuestion(instructions="x")) == {"type": "noul", "instructions": "x"}
    choice = wire_question(ChoiceQuestion(instructions="x", criteria={"a": "A"}))
    assert choice["type"] == "choice"
    assert list(choice["criteria"]) == ["a", "none"]
    score = wire_question(ScoreQuestion(instructions="x", levels=["lo", "hi"]))
    assert score == {"type": "score", "instructions": "x", "criteria": ["lo", "hi"]}


def test_request_url_auth_and_body_come_from_config():
    sent: list[httpx.Request] = []
    model = make_model(respond_with("house_activity", sent))

    model.decide("Austin replaced the furnace filter.", HOUSE_QUESTIONS)

    (request,) = sent
    assert str(request.url) == (
        "https://api.cloudflare.com/client/v4/accounts/acct-123/ai/run/@cf/vendor/some-model"
    )
    assert request.headers["Authorization"] == "Bearer token-abc"
    body = json.loads(request.content)
    # The body names the model by the last segment of the configured id
    assert body["model"] == "some-model"
    assert body["state"] == "Austin replaced the furnace filter."
    assert body["questions"]["is_maintenance"]["type"] == "noul"
    assert body["questions"]["kind"]["criteria"]["none"]


def test_request_model_override():
    sent: list[httpx.Request] = []
    model = make_model(respond_with("house_activity", sent), request_model="short-name")
    model.decide("x", HOUSE_QUESTIONS)
    assert json.loads(sent[0].content)["model"] == "short-name"


def test_recorded_request_matches_what_the_adapter_sends():
    sent: list[httpx.Request] = []
    model = make_model(respond_with("house_activity", sent), model="@cf/vendor/clef-flash")
    recorded_request = RECORDED["house_activity"]["request"]
    model.decide(recorded_request["state"], HOUSE_QUESTIONS)
    assert json.loads(sent[0].content) == recorded_request


# ---- answers ----


def test_decide_parses_recorded_response_into_typed_answers():
    answers = make_model(respond_with("house_activity")).decide("x", HOUSE_QUESTIONS)

    kind = answers["kind"]
    assert isinstance(kind, ChoiceAnswer)
    assert kind.choice == "activity"
    assert kind.confidence == pytest.approx(0.68)
    significance = answers["significance"]
    assert isinstance(significance, ScoreAnswer)
    assert significance.score == pytest.approx(1.3449)
    assert len(significance.probabilities) == 4
    maintenance = answers["is_maintenance"]
    assert isinstance(maintenance, YesNoAnswer)
    assert maintenance.p_yes == pytest.approx(0.9293)
    for answer in answers.values():
        assert answer.model == "instance-a"
        assert answer.calibrated is True
        assert answer.latency_ms >= 0


def test_cost_is_input_tokens_times_price_split_across_answers():
    answers = make_model(respond_with("house_activity")).decide("x", HOUSE_QUESTIONS)
    # 390 input tokens at $0.09 per million
    total = sum(a.cost_usd for a in answers.values())
    assert total == pytest.approx(390 * 0.09 / 1e6)


def test_cost_is_none_without_a_price():
    answers = make_model(respond_with("house_activity"), price_per_mtok_in=None).decide(
        "x", HOUSE_QUESTIONS
    )
    assert all(a.cost_usd is None for a in answers.values())


def test_unwrapped_result_is_accepted():
    unwrapped = RECORDED["dr_element"]["response"]["result"]
    model = make_model(lambda _r: httpx.Response(200, json=unwrapped))
    questions = {
        "layer": ChoiceQuestion(instructions="?", criteria={"application": "A"}),
        "is_persistence": YesNoQuestion(instructions="?"),
    }
    answers = model.decide("x", questions)
    assert answers["layer"].choice == "application"
    assert answers["is_persistence"].p_yes == pytest.approx(0.7726)


def test_no_usable_answer_at_all_raises():
    model = make_model(respond_with("dr_element"))
    with pytest.raises(DecisionModelError, match="no usable answer"):
        model.decide("x", {"kind": HOUSE_QUESTIONS["kind"]})


def test_one_missing_answer_keeps_the_others():
    # The dr_element response answers 'layer' only; 'kind' comes back empty
    model = make_model(respond_with("dr_element"))
    questions = {
        "layer": ChoiceQuestion(instructions="?", criteria={"application": "A"}),
        "kind": HOUSE_QUESTIONS["kind"],
    }
    answers = model.decide("x", questions)
    assert answers["layer"].choice == "application"
    assert isinstance(answers["kind"], ChoiceAnswer)
    assert answers["kind"].choice is None
    assert answers["kind"].model == "instance-a"


def test_choice_not_offered_is_treated_as_unanswered():
    # 'none' was not offered, so a 'none' choice is not a usable answer
    payload = {
        "result": {
            "answers": {
                "pick": {"choice": "none", "probabilities": {"a": 0.1, "none": 0.9}},
                "ok": {"noul": 0.4},
            }
        }
    }
    model = make_model(lambda _r: httpx.Response(200, json=payload))
    questions = {
        "pick": ChoiceQuestion(instructions="?", criteria={"a": "A"}, offer_none=False),
        "ok": YesNoQuestion(instructions="?"),
    }
    answers = model.decide("x", questions)
    assert answers["pick"].choice is None
    assert answers["ok"].p_yes == 0.4


def test_non_numeric_usage_does_not_break_parsing():
    payload = {"result": {"answers": {"ok": {"noul": 0.4}}, "usage": {"input_tokens": "lots"}}}
    model = make_model(lambda _r: httpx.Response(200, json=payload))
    answers = model.decide("x", {"ok": YesNoQuestion(instructions="?")})
    assert answers["ok"].cost_usd == 0.0


def test_unexpected_httpx_errors_become_decision_model_errors():
    def handler(_request):
        raise httpx.DecodingError("garbled")

    with pytest.raises(DecisionModelError, match="DecodingError"):
        make_model(handler).decide("x", HOUSE_QUESTIONS)


# ---- errors and retries ----


def test_recorded_400_error_raises_without_retry():
    sent: list[httpx.Request] = []
    model = make_model(respond_with("bad_question_type", sent))
    with pytest.raises(DecisionModelRequestError, match="Bad input"):
        model.decide("x", HOUSE_QUESTIONS)
    assert len(sent) == 1


def test_retries_429_and_5xx_with_backoff_then_succeeds():
    statuses = iter([429, 503])
    delays: list[float] = []
    recorded = RECORDED["house_activity"]["response"]

    def handler(_request):
        status = next(statuses, 200)
        return httpx.Response(status, json=recorded if status == 200 else {"errors": []})

    model = make_model(handler, backoff_seconds=1.0, sleep=delays.append)
    answers = model.decide("x", HOUSE_QUESTIONS)

    assert answers["kind"].choice == "activity"
    assert delays == [1.0, 2.0]


def test_gives_up_after_max_attempts():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, text="upstream broke")

    with pytest.raises(DecisionModelUnavailableError, match="HTTP 500"):
        make_model(handler, max_attempts=3).decide("x", HOUSE_QUESTIONS)
    assert len(calls) == 3


def test_auth_failure_is_a_request_error_and_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"success": False, "errors": [{"message": "bad token"}]})

    with pytest.raises(DecisionModelRequestError, match="HTTP 401"):
        make_model(handler).decide("x", HOUSE_QUESTIONS)
    assert len(calls) == 1


def test_retry_after_reads_seconds_and_http_dates():
    def with_header(value):
        return httpx.Response(429, headers={"Retry-After": value})

    assert _retry_after(with_header("3")) == 3.0
    later = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
    assert 25 <= _retry_after(with_header(later)) <= 30
    past = format_datetime(datetime.now(timezone.utc) - timedelta(seconds=30), usegmt=True)
    assert _retry_after(with_header(past)) == 0.0
    assert _retry_after(with_header("whenever")) is None
    assert _retry_after(httpx.Response(429)) is None
    assert _retry_after(with_header("3600")) == 60.0


def test_concurrency_limit_drops_semaphores_of_closed_loops():
    limit = ConcurrencyLimit(1)

    async def contend():
        # Two waiters on one slot, so the semaphore records its loop
        async def hold():
            async with limit.async_slot():
                await asyncio.sleep(0)

        await asyncio.gather(hold(), hold())

    asyncio.run(contend())
    asyncio.run(contend())
    # The first loop's semaphore was dropped when the second loop asked for a slot
    assert len(limit._loops) == 1


def test_429_waits_at_least_retry_after():
    statuses = iter([429])
    delays: list[float] = []
    recorded = RECORDED["house_activity"]["response"]

    def handler(_request):
        if next(statuses, None):
            return httpx.Response(429, headers={"Retry-After": "7"}, json={})
        return httpx.Response(200, json=recorded)

    make_model(handler, backoff_seconds=1.0, sleep=delays.append).decide("x", HOUSE_QUESTIONS)
    assert delays == [7.0]


def test_base_url_comes_from_options():
    sent: list[httpx.Request] = []
    model = make_model(respond_with("house_activity", sent), base_url="https://gateway.test/v4/")
    model.decide("x", HOUSE_QUESTIONS)
    assert str(sent[0].url).startswith("https://gateway.test/v4/accounts/acct-123/ai/run/")


def test_retries_connection_errors():
    attempts = iter([True])
    recorded = RECORDED["house_activity"]["response"]

    def handler(request):
        if next(attempts, False):
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json=recorded)

    assert make_model(handler).decide("x", HOUSE_QUESTIONS)["kind"].choice == "activity"


def test_unconfigured_instance_makes_no_call():
    sent: list[httpx.Request] = []
    model = make_model(respond_with("house_activity", sent), api_token="")
    assert model.is_configured is False
    with pytest.raises(DecisionModelNotConfiguredError):
        model.decide("x", HOUSE_QUESTIONS)
    assert sent == []


# ---- async and concurrency ----


def test_decide_async_parses_the_same_answers():
    model = make_model(respond_with("house_activity"))
    answers = asyncio.run(model.decide_async("x", HOUSE_QUESTIONS))
    assert answers["kind"].choice == "activity"
    assert answers["significance"].score == pytest.approx(1.3449)


def test_async_retries_use_async_sleep():
    statuses = iter([429])
    delays: list[float] = []
    recorded = RECORDED["house_activity"]["response"]

    async def record_sleep(seconds):
        delays.append(seconds)

    def handler(_request):
        status = next(statuses, 200)
        return httpx.Response(status, json=recorded if status == 200 else {})

    model = make_model(handler, backoff_seconds=0.5, async_sleep=record_sleep)
    asyncio.run(model.decide_async("x", HOUSE_QUESTIONS))
    assert delays == [0.5]


def test_async_calls_are_limited_to_the_configured_concurrency():
    in_flight = 0
    peak = 0
    recorded = RECORDED["house_activity"]["response"]

    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return httpx.Response(200, json=recorded)

    model = make_model(lambda r: None, concurrency=2, async_transport=SlowTransport())

    async def run():
        await asyncio.gather(*(model.decide_async("x", HOUSE_QUESTIONS) for _ in range(6)))

    asyncio.run(run())
    assert peak == 2


def test_sync_calls_are_limited_to_the_configured_concurrency():
    lock = threading.Lock()
    in_flight = 0
    peak = 0
    recorded = RECORDED["house_activity"]["response"]

    def handler(_request):
        nonlocal in_flight, peak
        with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        time.sleep(0.02)
        with lock:
            in_flight -= 1
        return httpx.Response(200, json=recorded)

    model = make_model(handler, concurrency=2)
    threads = [threading.Thread(target=model.decide, args=("x", HOUSE_QUESTIONS)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak <= 2

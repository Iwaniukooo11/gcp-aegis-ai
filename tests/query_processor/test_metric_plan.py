"""Unit tests for Query Processor metric plan helpers."""

from datetime import datetime, timezone

from app.integrations import metric_plan, monitoring


def test_supplement_plan_adds_cpu_and_memory_metrics_from_question(sample_session):
    plan = {"window_minutes": 30, "metrics": [], "rationale": "test"}

    body = metric_plan.supplement_metric_plan_for_question(
        plan,
        "what were cpu and memory during the incident?",
        sample_session,
    )

    types = {metric["type"] for metric in body["metrics"]}
    assert {
        "cpu_utilization",
        "cpu_core_usage",
        "cpu_request_utilization",
        "memory_utilization",
        "memory_limit_utilization",
    }.issubset(types)


def test_parse_session_anchor_prefers_log_timestamp(sample_session):
    session = {
        **sample_session,
        "created_at": "2026-05-21T00:10:00Z",
        "log_timestamp": "2026-05-21T00:00:00Z",
    }

    assert metric_plan.parse_session_anchor(session) == datetime(
        2026, 5, 21, 0, 0, tzinfo=timezone.utc
    )


def test_format_metric_facts_uses_available_cpu_fallback():
    summary = {
        "cpu_utilization": {"status": "no_data"},
        "cpu_core_usage": {"status": "ok", "display": "~0.12 cores (avg over last sample interval)"},
    }

    line = metric_plan.format_metric_facts_line("cpu?", summary)

    assert line == "CPU at incident time: *~0.12 cores (avg over last sample interval)*"


def test_monitoring_point_value_preserves_zero_int64():
    class FakePb:
        def WhichOneof(self, _name):
            return "int64_value"

    class FakeValue:
        _pb = FakePb()
        int64_value = 0

    class FakePoint:
        value = FakeValue()

    assert monitoring._point_value(FakePoint()) == 0

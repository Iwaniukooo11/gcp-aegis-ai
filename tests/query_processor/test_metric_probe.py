"""Unit tests for hardcoded metric catalog plan constraints."""
from app.integrations import metric_plan


class TestConstrainPlanToCatalog:
    def test_keeps_only_allowlisted_types(self):
        session = {"service_name": "java-api", "namespace": "aegis-demo"}
        plan = {
            "window_minutes": 30,
            "metrics": [
                {"type": "cpu_utilization"},
                {"type": "memory_utilization"},
                {"type": "not_a_real_metric"},
            ],
            "rationale": "test",
        }
        body = metric_plan.constrain_plan_to_catalog(plan, session)
        types = {m["type"] for m in body["metrics"]}
        assert types == {"cpu_utilization", "memory_utilization"}
        assert body["metrics"][0]["metric_type"].startswith("kubernetes.io/container/")

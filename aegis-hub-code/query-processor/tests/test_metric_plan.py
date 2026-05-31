from datetime import datetime, timezone
import unittest

from app.integrations.metric_plan import format_metric_facts_line, summarize_metric_results


class MetricSummaryTests(unittest.TestCase):
    def test_cumulative_cpu_is_rendered_as_average_cores_with_units(self) -> None:
        metric_results = {
            "kubernetes.io/container/cpu/core_usage_time": [
                {
                    "points": [
                        {"end_time": "2026-05-31T16:26:00Z", "value": 16.0},
                        {"end_time": "2026-05-31T16:25:00Z", "value": 10.0},
                    ]
                }
            ]
        }

        summary = summarize_metric_results(
            metric_results,
            datetime(2026, 5, 31, 16, 25, 45, tzinfo=timezone.utc),
        )
        facts = format_metric_facts_line("was cpu high?", summary)

        self.assertIn("CPU near incident time", facts)
        self.assertIn("~0.1 cores", facts)
        self.assertNotIn("16.0", facts)

    def test_memory_zero_sample_uses_nearest_nonzero_sample(self) -> None:
        metric_results = {
            "kubernetes.io/container/memory/used_bytes": [
                {
                    "points": [
                        {"end_time": "2026-05-31T16:25:00Z", "value": 0},
                        {"end_time": "2026-05-31T16:26:00Z", "value": 7340032},
                    ]
                }
            ]
        }

        summary = summarize_metric_results(
            metric_results,
            datetime(2026, 5, 31, 16, 25, 15, tzinfo=timezone.utc),
        )
        facts = format_metric_facts_line("was memory high?", summary)

        self.assertIn("Memory near incident time", facts)
        self.assertIn("7.0 MiB", facts)
        self.assertNotIn("0.0 MiB", facts)


if __name__ == "__main__":
    unittest.main()

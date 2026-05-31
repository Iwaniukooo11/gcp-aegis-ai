import unittest

from app.integrations.vertex import classify_incident


class CheckoutDependencyClassificationTests(unittest.TestCase):
    def test_checkout_timeout_uses_business_dependency_summary(self) -> None:
        result = classify_incident(
            {"error_type": "DownstreamTimeoutError"},
            {
                "jsonPayload": {
                    "path": "/api/checkout",
                    "upstream_service": "java-api",
                    "error_type": "DownstreamTimeoutError",
                    "message": "Checkout failed because java-api pricing request exceeded configured timeout",
                }
            },
        )

        self.assertIn("Customer checkout failed", result["ai_summary"])
        self.assertIn("java-api pricing dependency", result["ai_summary"])
        self.assertNotIn("chaos", result["ai_summary"].lower())
        self.assertNotIn("chaos", result["ai_recommendation"].lower())


if __name__ == "__main__":
    unittest.main()

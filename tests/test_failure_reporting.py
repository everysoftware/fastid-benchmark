import unittest

from fastid_benchmark.comparison import summarize, trial_metrics


class FailureReportingTests(unittest.TestCase):
    def test_all_timeouts_are_zero_successful_throughput(self):
        trial = {"system": "authentik", "cpu": 1, "mode": "paced", "split": 0.75, "repeat": 1}
        total = {"Request Count": "100", "Failure Count": "100", "Requests/s": "10", "95%": "10000"}
        row = trial_metrics(total, trial)
        self.assertEqual(row["successful_rps"], 0)
        self.assertEqual(row["successful_request_count"], 0)
        self.assertEqual(row["outcome"], "no_successful_requests")
        summary = summarize([row])[0]
        self.assertEqual(summary["successful_rps_median"], 0)
        self.assertEqual(summary["trials_with_no_success"], 1)
        self.assertEqual(summary["rps_median"], 10)

    def test_partial_failure_does_not_count_failed_requests_as_goodput(self):
        trial = {"system": "authentik", "cpu": 1, "mode": "paced", "split": 0.75, "repeat": 1}
        row = trial_metrics({"Request Count": "100", "Failure Count": "25", "Requests/s": "20", "95%": "10000"}, trial)
        self.assertEqual(row["successful_rps"], 15)
        self.assertEqual(row["successful_request_count"], 75)
        self.assertEqual(row["outcome"], "partial_failures")

"""Offline provider checks: no API key, network access, or billable requests."""

import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from scripts import openai_provider_smoke as smoke


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ProviderSmokeTests(unittest.TestCase):
    def test_missing_key_never_calls_network(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": ""}),
            patch.object(smoke.urllib.request, "urlopen") as request,
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            self.assertEqual(smoke.main(), 2)
            request.assert_not_called()

    def test_exact_marker_required(self):
        for output, expected in [
            ("PROVIDER_CONNECTED", 0),
            ("NOT_PROVIDER_CONNECTED", 1),
            ("PROVIDER_CONNECTED but failed", 1),
        ]:
            with self.subTest(output=output):
                with (
                    patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"}),
                    patch.object(
                        smoke.urllib.request,
                        "urlopen",
                        return_value=FakeResponse({"output": [{"content": [{"text": output}]}]}),
                    ) as request,
                    patch("sys.stdout", new_callable=io.StringIO),
                ):
                    self.assertEqual(smoke.main(), expected)
                    self.assertEqual(request.call_count, 1)
                    sent = json.loads(request.call_args.args[0].data)
                    self.assertFalse(sent["store"])
                    self.assertEqual(sent["max_output_tokens"], 32)

    def test_http_error_does_not_leak_response_body(self):
        error = urllib.error.HTTPError(
            smoke.API_URL,
            401,
            "Unauthorized",
            {},
            io.BytesIO(b"secret response content"),
        )
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"}),
            patch.object(smoke.urllib.request, "urlopen", side_effect=error),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            self.assertEqual(smoke.main(), 1)
            self.assertNotIn("secret response content", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

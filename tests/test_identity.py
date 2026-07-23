import os
import unittest
from unittest.mock import patch

from starlette.requests import Request

from app.api.routers.query_router import _request_user_id


def _request(headers=None):
    return Request({
        "type": "http",
        "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
    })


class IdentityTests(unittest.TestCase):
    def test_client_identity_is_ignored_without_trusted_proxy(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_request_user_id(_request(), "admin"), "anonymous")

    def test_proxy_identity_is_used_only_when_explicitly_enabled(self):
        with patch.dict(os.environ, {"DATA_AGENT_TRUSTED_PROXY": "true"}, clear=False):
            self.assertEqual(
                _request_user_id(_request({"X-Authenticated-User": "alice"}), "admin"),
                "alice",
            )


if __name__ == "__main__":
    unittest.main()

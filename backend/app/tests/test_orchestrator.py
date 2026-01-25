from __future__ import annotations

import unittest

from app.models import OrchestrateRequest
from app.orchestrator.service import handle_orchestrate
from app.store import SessionStore


class OrchestratorFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SessionStore(ttl_seconds=3600)

    def test_out_of_scope_refuse(self) -> None:
        res = handle_orchestrate(store=self.store, body=OrchestrateRequest(message="给我推荐一只股票"))
        self.assertEqual(res.action, "chat")
        self.assertTrue(res.trace and res.trace.get("planner"))
        self.assertEqual(res.trace["planner"]["decision"], "refuse")

    def test_discovery_then_compare(self) -> None:
        res = handle_orchestrate(store=self.store, body=OrchestrateRequest(message="我在上海想找能一起聊创业产品的人"))
        self.assertEqual(res.action, "results")
        self.assertIn("people", res.results or {})
        sid = res.sessionId

        res2 = handle_orchestrate(store=self.store, body=OrchestrateRequest(sessionId=sid, message="对比一下第一个和第二个"))
        self.assertEqual(res2.action, "chat")
        self.assertIn("comparison", (res2.assistantMessage or "").lower())


if __name__ == "__main__":
    unittest.main()

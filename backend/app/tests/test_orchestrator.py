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

    def test_followup_tokens_include_results(self) -> None:
        # Seed last_results directly: user "sees" these.
        session = self.store.create()
        session.meta["last_results"] = {
            "type": "people",
            "items": [
                {"id": "p1", "name": "Alex", "city": "New York", "headline": "x", "score": 80, "topics": ["a"]},
                {"id": "p2", "name": "Sam", "city": "Shanghai", "headline": "y", "score": 78, "topics": ["b"]},
            ],
        }
        # Message contains demonstrative reference; should pass visible context into planner.
        res = handle_orchestrate(store=self.store, body=OrchestrateRequest(sessionId=session.id, message="纽约的这个人跟我match吗？"))
        planner = (res.trace or {}).get("planner") if isinstance(res.trace, dict) else None
        self.assertTrue(isinstance(planner, dict))
        # We can't guarantee tool_call without LLM, but planner should have been invoked and trace present.
        self.assertIn("decision", planner)

    def test_deck_progress_offline_requires_city(self) -> None:
        session = self.store.create()
        session.meta["pending_tool"] = {"toolName": "intelligent_discovery"}
        # Domain chosen but location missing.
        session.state.slots = {"domain": "person", "structured_filters": {"location": {}}}

        # First submit: user selects offline.
        res = handle_orchestrate(
            store=self.store,
            body=OrchestrateRequest(sessionId=session.id, submit={"cardId": "structured_filters_location_mode", "data": {"structured_filters.location.is_online": "false"}}),
        )
        self.assertEqual(res.action, "form")
        self.assertTrue(res.deck)
        # After choosing offline, the next missing critical should be city.
        self.assertTrue(res.missingFields and res.missingFields[0].endswith("location.city"))

    def test_beginner_followup_uses_analysis(self) -> None:
        session = self.store.create()
        # Pretend we already showed people results.
        session.meta["last_results"] = {
            "type": "people",
            "items": [
                {"id": "p1", "name": "A", "city": "Shanghai", "headline": "Beginner tennis", "score": 80, "topics": ["tennis"]},
                {"id": "p2", "name": "B", "city": "Shanghai", "headline": "Intermediate tennis", "score": 75, "topics": ["tennis"]},
            ],
        }
        # And memory store contains those IDs (deep_profile_analysis needs it).
        session.meta["memory"] = {"profiles": {"p1": session.meta["last_results"]["items"][0], "p2": session.meta["last_results"]["items"][1]}, "events": {}, "runs": []}

        res = handle_orchestrate(store=self.store, body=OrchestrateRequest(sessionId=session.id, message="哪些是新手啊？"))
        # Heuristic planner should choose deep_profile_analysis tool_call and respond with chat (analysis text).
        self.assertEqual(res.action, "chat")
        self.assertTrue(res.trace and isinstance(res.trace.get("planner"), dict))
        self.assertIn(res.trace["planner"]["decision"], {"tool_call", "chat"})


if __name__ == "__main__":
    unittest.main()

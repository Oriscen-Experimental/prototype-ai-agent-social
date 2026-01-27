from __future__ import annotations

import unittest
from unittest.mock import patch

from app.focus import visible_candidates
from app.llm import LLMPlannerDecision
from app.models import OrchestrateRequest
from app.orchestrator.service import handle_orchestrate
from app.store import SessionStore


class OrchestratorFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SessionStore(ttl_seconds=3600)

    def test_out_of_scope_refuse(self) -> None:
        with patch(
            "app.planner.service.call_gemini_json",
            return_value=LLMPlannerDecision(
                decision="refuse",
                intent="unknown",
                assistantMessage="I can’t help with finance/stock picking.",
                code="OUT_OF_SCOPE",
            ),
        ):
            res = handle_orchestrate(store=self.store, body=OrchestrateRequest(message="给我推荐一只股票"))
        self.assertEqual(res.action, "chat")
        self.assertTrue(res.trace and res.trace.get("plannerOutput"))
        self.assertEqual(res.trace["plannerOutput"]["decision"], "refuse")

    def test_discovery_then_compare(self) -> None:
        discovery_plan = LLMPlannerDecision(
            decision="tool_call",
            intent="find_people",
            assistantMessage="OK",
            toolName="intelligent_discovery",
            toolArgs={
                "domain": "person",
                "semantic_query": "我在上海想找能一起聊创业产品的人",
                "structured_filters": {"location": {"city": "Shanghai", "region": None, "is_online": False}},
                "sort_strategy": "relevance",
                "limit": 2,
            },
            phase="search",
        )

        class _DiscoveryPeopleStub:
            def __init__(self):
                self.people = [
                    {
                        "id": "p1",
                        "kind": "human",
                        "presence": "offline",
                        "name": "Alex",
                        "city": "Shanghai",
                        "headline": "Startup chats",
                        "score": 90,
                        "badges": [],
                        "about": ["a", "b"],
                        "matchReasons": ["x", "y"],
                        "topics": ["startup", "product", "chat"],
                    },
                    {
                        "id": "p2",
                        "kind": "human",
                        "presence": "online",
                        "name": "Sam",
                        "city": "Shanghai",
                        "headline": "Product thinking",
                        "score": 85,
                        "badges": [],
                        "about": ["a", "b"],
                        "matchReasons": ["x", "y"],
                        "topics": ["product", "founder", "coffee"],
                    },
                ]
                self.assistantMessage = "Here are two people."

        with patch("app.planner.service.call_gemini_json", return_value=discovery_plan), patch(
            "app.tool_library.intelligent_discovery.call_gemini_json",
            return_value=_DiscoveryPeopleStub(),
        ):
            res = handle_orchestrate(store=self.store, body=OrchestrateRequest(message="我在上海想找能一起聊创业产品的人"))
        self.assertEqual(res.action, "results")
        self.assertIn("people", res.results or {})
        sid = res.sessionId

        compare_plan = LLMPlannerDecision(
            decision="tool_call",
            intent="analyze_people",
            assistantMessage="OK",
            toolName="deep_profile_analysis",
            toolArgs={"target_ids": ["p1", "p2"], "analysis_mode": "compare", "focus_aspects": []},
            phase="answer",
        )

        class _AnalysisStub:
            def __init__(self):
                self.assistantMessage = "Comparison: p1 vs p2."
                self.data = {"comparison": {"summary": "stub"}}

        with patch("app.planner.service.call_gemini_json", return_value=compare_plan), patch(
            "app.tool_library.deep_profile_analysis.call_gemini_json",
            return_value=_AnalysisStub(),
        ):
            res2 = handle_orchestrate(store=self.store, body=OrchestrateRequest(sessionId=sid, message="对比一下第一个和第二个"))
        self.assertEqual(res2.action, "chat")
        self.assertIn("comparison", (res2.assistantMessage or "").lower())

    def test_followup_tokens_include_results(self) -> None:
        # Seed a prior assistant turn that included UI-visible results.
        session = self.store.create()
        last_results = {
            "type": "people",
            "items": [
                {"id": "p1", "name": "Alex", "city": "New York", "headline": "x", "score": 80, "topics": ["a"]},
                {"id": "p2", "name": "Sam", "city": "Shanghai", "headline": "y", "score": 78, "topics": ["b"]},
            ],
        }
        session.meta["last_results"] = last_results
        self.store.append(session, "assistant", "I've found 2 people you might like.")
        session.meta["ui_results_history"] = [{"at_ms": session.history[-1].at_ms, "ui_results": visible_candidates(last_results)}]

        # Message contains demonstrative reference; planner context should include the UI snapshot.
        with patch(
            "app.planner.service.call_gemini_json",
            return_value=LLMPlannerDecision(decision="chat", intent="unknown", assistantMessage="OK"),
        ):
            res = handle_orchestrate(store=self.store, body=OrchestrateRequest(sessionId=session.id, message="纽约的这个人跟我match吗？"))
        ctx = (res.trace or {}).get("plannerInput") if isinstance(res.trace, dict) else None
        self.assertTrue(isinstance(ctx, dict))
        hist = ctx.get("history")
        self.assertTrue(isinstance(hist, list))
        self.assertTrue(any(isinstance(t, dict) and ("ui results" in t) for t in hist))

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
        last_results = {
            "type": "people",
            "items": [
                {"id": "p1", "name": "A", "city": "Shanghai", "headline": "Beginner tennis", "score": 80, "topics": ["tennis"]},
                {"id": "p2", "name": "B", "city": "Shanghai", "headline": "Intermediate tennis", "score": 75, "topics": ["tennis"]},
            ],
        }
        session.meta["last_results"] = last_results
        self.store.append(session, "assistant", "Here are 2 options.")
        session.meta["ui_results_history"] = [{"at_ms": session.history[-1].at_ms, "ui_results": visible_candidates(last_results)}]
        # And memory store contains those IDs (deep_profile_analysis needs it).
        session.meta["memory"] = {"profiles": {"p1": last_results["items"][0], "p2": last_results["items"][1]}, "events": {}, "runs": []}

        plan = LLMPlannerDecision(
            decision="tool_call",
            intent="analyze_people",
            assistantMessage="OK",
            toolName="deep_profile_analysis",
            toolArgs={"target_ids": ["p1", "p2"], "analysis_mode": "compare", "focus_aspects": ["skill_level"]},
            phase="answer",
        )

        class _AnalysisStub:
            def __init__(self):
                self.assistantMessage = "Here’s a comparison of which options look beginner-friendly."
                self.data = {"comparison": {"summary": "stub"}}

        with patch("app.planner.service.call_gemini_json", return_value=plan), patch(
            "app.tool_library.deep_profile_analysis.call_gemini_json",
            return_value=_AnalysisStub(),
        ):
            res = handle_orchestrate(store=self.store, body=OrchestrateRequest(sessionId=session.id, message="哪些是新手啊？"))
        # Heuristic planner should choose deep_profile_analysis tool_call and respond with chat (analysis text).
        self.assertEqual(res.action, "chat")
        self.assertTrue(res.trace and isinstance(res.trace.get("plannerOutput"), dict))
        self.assertIn(res.trace["plannerOutput"]["decision"], {"tool_call", "chat"})

    def test_refine_filters_across_visible_history(self) -> None:
        session = self.store.create()
        people_ny = {
            "type": "people",
            "items": [
                {
                    "id": "p_ny_1",
                    "kind": "human",
                    "presence": "offline",
                    "name": "NY One",
                    "city": "New York",
                    "headline": "Tennis · (mock)",
                    "score": 80,
                    "badges": [],
                    "about": ["a", "b"],
                    "matchReasons": ["x", "y"],
                    "topics": ["tennis"],
                },
                {
                    "id": "p_ny_2",
                    "kind": "human",
                    "presence": "online",
                    "name": "NY Two",
                    "city": "New York",
                    "headline": "Tennis · (mock)",
                    "score": 70,
                    "badges": [],
                    "about": ["a", "b"],
                    "matchReasons": ["x", "y"],
                    "topics": ["tennis"],
                },
            ],
        }
        people_ca = {
            "type": "people",
            "items": [
                {
                    "id": "p_ca_1",
                    "kind": "human",
                    "presence": "offline",
                    "name": "CA One",
                    "city": "San Francisco",
                    "headline": "Tennis · (mock)",
                    "score": 85,
                    "badges": [],
                    "about": ["a", "b"],
                    "matchReasons": ["x", "y"],
                    "topics": ["tennis"],
                },
                {
                    "id": "p_ca_2",
                    "kind": "human",
                    "presence": "online",
                    "name": "CA Two",
                    "city": "San Diego",
                    "headline": "Tennis · (mock)",
                    "score": 75,
                    "badges": [],
                    "about": ["a", "b"],
                    "matchReasons": ["x", "y"],
                    "topics": ["tennis"],
                },
            ],
        }
        session.meta["memory"] = {"profiles": {it["id"]: it for it in (people_ny["items"] + people_ca["items"])}, "events": {}, "runs": []}

        self.store.append(session, "assistant", "NY results.")
        at1 = session.history[-1].at_ms
        self.store.append(session, "assistant", "CA results.")
        at2 = session.history[-1].at_ms
        session.meta["ui_results_history"] = [
            {"at_ms": at1, "ui_results": visible_candidates(people_ny)},
            {"at_ms": at2, "ui_results": visible_candidates(people_ca)},
        ]
        session.meta["last_results"] = people_ca

        plan = LLMPlannerDecision(
            decision="tool_call",
            intent="refine_people",
            assistantMessage="OK",
            toolName="results_refine",
            toolArgs={"domain": "person", "instruction": "把加州的筛出来", "limit": 5},
            phase="answer",
        )

        class _RefineStub:
            def __init__(self):
                self.assistantMessage = "Filtered to California."
                self.selected_ids = ["p_ca_1", "p_ca_2"]

        with patch("app.planner.service.call_gemini_json", return_value=plan), patch(
            "app.tool_library.results_refine.call_gemini_json",
            return_value=_RefineStub(),
        ):
            res = handle_orchestrate(store=self.store, body=OrchestrateRequest(sessionId=session.id, message="把加州的筛出来"))

        self.assertEqual(res.action, "results")
        self.assertTrue(res.trace and isinstance(res.trace.get("plannerOutput"), dict))
        self.assertEqual(res.trace["plannerOutput"].get("toolName"), "results_refine")
        people = (res.results or {}).get("people") or []
        self.assertTrue(isinstance(people, list))
        cities: list[str] = []
        for p in people:
            if isinstance(p, dict):
                cities.append(str(p.get("city") or ""))
            else:
                cities.append(str(getattr(p, "city", "") or ""))
        self.assertTrue(all(c.lower() in {"san francisco", "san diego"} for c in cities))


if __name__ == "__main__":
    unittest.main()

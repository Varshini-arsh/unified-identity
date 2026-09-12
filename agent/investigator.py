"""
agent/investigator.py - LangGraph Fraud Investigation Agent.

Flow: flag -> gather_evidence -> assess -> recommend  (STOP: human approves)
The agent NEVER revokes autonomously; /govern/decide records the human
decision, which the ledger client anchors on-chain (accountability).

Run standalone:  python -m agent.investigator
Requires GEMINI_API_KEY (free from Google AI Studio) in the environment.
"""
from __future__ import annotations

import os
from typing import TypedDict

import requests

from agent.config import get_gemini_key

API = "http://127.0.0.1:8000"

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    raise SystemExit("pip install langgraph langchain-google-genai")


class CaseState(TypedDict):
    case_id: str
    did_id: str
    features: list[float]
    risk_score: float
    flagged: bool
    evidence: list
    recommendation: str
    human_approved: bool | None


# ---------- nodes ----------

def flag(state: CaseState) -> CaseState:
    r = requests.post(f"{API}/risk/score", json={"features": state["features"]}, timeout=10)
    out = r.json()
    return {**state, "risk_score": out["risk_score"], "flagged": out["flagged"]}


def gather_evidence(state: CaseState) -> CaseState:
    ev = [{"source": "risk_api", "detail": f"score={state['risk_score']}"}]
    if state.get("did_id"):
        ev.append({"source": "registry", "detail": f"did={state['did_id']} lookup pending ledger wiring"})
    return {**state, "evidence": ev}


def assess(state: CaseState) -> CaseState:
    """LLM reasoning step over the gathered evidence (Gemini free tier)."""
    if not state["flagged"]:
        return {**state, "recommendation": "clear: risk below threshold"}
    key = get_gemini_key()
    prompt = (
        f"You are an identity-fraud analyst. Risk score {state['risk_score']}. "
        f"Evidence: {state['evidence']}. Recommend one of revoke|watch|clear "
        "with a one-line justification. Be conservative."
    )
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        last_err = None
        for model in ("gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest"):
            try:
                llm = ChatGoogleGenerativeAI(model=model, google_api_key=key)
                content = llm.invoke(prompt).content
                # new client versions return a list of typed blocks
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                rec = str(content).strip()
                rec = f"[{model}] {rec}"
                break
            except Exception as e:
                last_err = e
                rec = None
        if rec is None:
            rec = f"watch (all Gemini models failed: {last_err})"
    except ImportError:
        rec = "watch (langchain-google-genai not installed)"
    return {**state, "recommendation": rec}


def human_gate(state: CaseState) -> CaseState:
    """Interrupt point: in the API/UI this pauses for a human decision."""
    return state  # human_approved set externally via /govern/decide


def build_graph():
    g = StateGraph(CaseState)
    g.add_node("flag", flag)
    g.add_node("gather_evidence", gather_evidence)
    g.add_node("assess", assess)
    g.add_node("human_gate", human_gate)
    g.set_entry_point("flag")
    g.add_edge("flag", "gather_evidence")
    g.add_edge("gather_evidence", "assess")
    g.add_edge("assess", "human_gate")
    g.add_edge("human_gate", END)
    return g.compile()


if __name__ == "__main__":
    graph = build_graph()
    demo_case: CaseState = {
        "case_id": "CASE-001",
        "did_id": "did:ethr:unified:demo123",
        "features": [0.5] * 8,
        "risk_score": 0.0,
        "flagged": False,
        "evidence": [],
        "recommendation": "",
        "human_approved": None,
    }
    print(graph.invoke(demo_case))

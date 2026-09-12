"""
agent/run_demo.py - end-to-end demo: boots nothing external; expects the API
on :8000 (started by the harness) and runs one flagged investigation case
through the full LangGraph loop, including the Gemini assessment step.
"""
from agent.investigator import build_graph

graph = build_graph()

flagged_case = {
    "case_id": "CASE-2026-001",
    "did_id": "did:ethr:unified:9f2c44deadbeef",
    "features": [9.0, -8.0, 7.0, -6.0, 5.0, -4.0, 3.0, -2.0],  # outlier -> flagged
    "risk_score": 0.0,
    "flagged": False,
    "evidence": [],
    "recommendation": "",
    "human_approved": None,
}

result = graph.invoke(flagged_case)

print("=" * 60)
print("CASE        :", result["case_id"])
print("DID         :", result["did_id"])
print("RISK SCORE  :", result["risk_score"])
print("FLAGGED     :", result["flagged"])
print("EVIDENCE    :", result["evidence"])
print("RECOMMEND   :", result["recommendation"])
print("HUMAN GATE  :", result["human_approved"], "(pending — human decides next)")
print("=" * 60)

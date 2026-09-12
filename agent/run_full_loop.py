"""
agent/run_full_loop.py - the complete accountability loop, end to end:

  1. create identity (DID)          -> API
  2. anchor DID document on-chain   -> DIDRegistry.createDID
  3. resolve it back from the chain -> DIDRegistry.resolveDID
  4. issue a verifiable credential  -> SSI layer
  5. agent investigates a flagged case (Gemini assessment)
  6. human approves revocation      -> /govern/decide
  7. verify the revocation on-chain -> /ledger/verify

Run (with hardhat node + API already up):
  LEDGER_CONTRACT_ADDRESS=0x... .venv/Scripts/python -m agent.run_full_loop
"""
from __future__ import annotations

import requests

from agent.investigator import build_graph

API = "http://127.0.0.1:8000"


def main() -> None:
    graph = build_graph()

    print("[1/7] creating identity...")
    did = requests.post(f"{API}/identity/create",
                        json={"label": "suspect-wallet-77"}, timeout=15).json()["did"]
    print("      DID:", did[:50])

    print("[2/7] anchoring DID document on-chain...")
    doc = {"did": did, "verification_method": f"{did}#keys-1", "status": "active"}
    r = requests.post(f"{API}/identity/anchor",
                      json={"did_id": did, "document": doc}, timeout=30).json()
    print("      tx:", r.get("tx", "?")[:34], "block:", r.get("block"))

    print("[3/7] resolving from the ledger...")
    res = requests.get(f"{API}/ledger/resolve/{did}", timeout=15).json()
    print("      owner:", res["owner"][:18], "revoked:", res["revoked"])

    print("[4/7] issuing verifiable credential...")
    vc = requests.post(f"{API}/credentials/issue",
                       json={"issuer_did": "did:ethr:unified:issuer1",
                             "subject_did": did,
                             "claims": {"wallet_age_days": 3, "kyc": "none"}},
                       timeout=15).json()
    print("      cred hash:", vc["cred_hash"][:34])

    print("[5/7] agent investigating flagged case (Gemini)...")
    case = graph.invoke({
        "case_id": "CASE-2026-002",
        "did_id": did,
        "features": [9.0, -8.0, 7.0, -6.0, 5.0, -4.0, 3.0, -2.0],
        "risk_score": 0.0, "flagged": False, "evidence": [],
        "recommendation": "", "human_approved": None,
    })
    print("      risk:", case["risk_score"], "| recommendation:", case["recommendation"][:90])

    print("[6/7] human gate: approving REVOCATION...")
    g = requests.post(f"{API}/govern/decide",
                      json={"case_id": "CASE-2026-002", "did_id": did,
                            "action": "revoke", "approved_by": "gov-officer-01"},
                      timeout=30).json()
    print("      recorded:", g["recorded"], "| tx:", (g["onchain_tx"] or "n/a")[:34])

    print("[7/7] auditor verification on-chain...")
    v = requests.get(f"{API}/ledger/verify/CASE-2026-002", timeout=15).json()
    print("      on-chain revoked:", v["onchain_revoked"], "| approved by:", v["approved_by"])
    print()
    print("ACCOUNTABILITY LOOP COMPLETE"
          if v["onchain_revoked"] else "LOOP INCOMPLETE - check ledger")


if __name__ == "__main__":
    main()

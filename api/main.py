"""
api/main.py - FastAPI exposing every capability as a tool endpoint.

The LangGraph Fraud Investigation Agent (agent/investigator.py) consumes
these endpoints; a human approves revocations via /govern/decide.
Run:  uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ssi.did_manager import DIDManager, CredentialIssuer
from ml.sybil_detector import IsolationForestDetector, shap_explain
from agent.config import get_ledger_config

app = FastAPI(title="Unified Identity API", version="0.1.0")

did_manager = DIDManager()
issuer = CredentialIssuer()

# ---------- ledger (lazy singleton) ----------

_ledger = None

def get_ledger():
    global _ledger
    if _ledger is None:
        from api.ledger_client import LedgerClient
        cfg = get_ledger_config()
        if not cfg["contract_address"]:
            raise HTTPException(503, "LEDGER_CONTRACT_ADDRESS not set (deploy first)")
        _ledger = LedgerClient(
            rpc_url=cfg["rpc_url"],
            contract_address=cfg["contract_address"],
            private_key=cfg["private_key"],
        )
    return _ledger

# ---------- in-memory case store (demo; swap for a DB later) ----------

CASES: dict[str, dict] = {}
# Risk model is fitted lazily on real features once the dataset lands;
# a tiny demo model is bootstrapped for the agent loop.
_demo = IsolationForestDetector(contamination=0.1).fit(
    np.random.default_rng(0).normal(size=(200, 8))
)


# ---------- schemas ----------

class CreateIdentityRequest(BaseModel):
    label: str = Field(..., description="human-readable alias for the new identity")

class IssueCredentialRequest(BaseModel):
    issuer_did: str
    subject_did: str
    claims: dict

class RiskRequest(BaseModel):
    features: list[float] = Field(..., min_length=8, max_length=8)

class GovernRequest(BaseModel):
    case_id: str
    did_id: str
    action: str = Field(..., pattern="^(revoke|clear|watch)$")
    approved_by: str


class AnchorRequest(BaseModel):
    did_id: str
    document: dict


# ---------- identity endpoints ----------

@app.post("/identity/create")
def create_identity(req: CreateIdentityRequest):
    doc, keys = did_manager.create_did()
    return {"did": doc.did_id, "document": doc.to_json(), "label": req.label,
            "private_key": keys["private_key"]}  # demo only: never return secrets in prod


@app.post("/credentials/issue")
def issue_credential(req: IssueCredentialRequest):
    vc = issuer.issue(req.issuer_did, req.subject_did, req.claims)
    return {"credential": vc.to_json(), "cred_hash": vc.hash().hex()}


# ---------- AI risk endpoints (agent tools) ----------

@app.post("/risk/score")
def risk_score(req: RiskRequest):
    X = np.array(req.features, dtype=float).reshape(1, -1)
    score = float(_demo.risk_scores(X)[0])
    return {"risk_score": round(score, 4),
            "flagged": bool(score >= 0.8),
            "explanation": "isolation-forest anomaly score (demo features)"}


@app.post("/risk/explain")
def risk_explain(req: RiskRequest):
    X = np.array(req.features, dtype=float).reshape(1, -1)
    shap_vals = shap_explain(_demo, X, 0)
    return {"shap_values": None if shap_vals is None else np.asarray(shap_vals).tolist(),
            "note": "install shap for real attributions"}


# ---------- ledger-backed identity anchoring ----------

@app.post("/identity/anchor")
def anchor_identity(req: AnchorRequest):
    """Anchor a DID document hash on-chain (owner registration)."""
    import hashlib, json as _json
    doc_hash = hashlib.sha256(_json.dumps(req.document, sort_keys=True).encode()).digest()
    try:
        receipt = get_ledger().create_did(req.did_id, doc_hash)
    except ValueError as e:
        raise HTTPException(409, str(e))  # e.g. DID already exists
    return {"did": req.did_id, "anchored": True, "tx": receipt["transactionHash"].hex(),
            "block": receipt["blockNumber"]}


@app.get("/ledger/resolve/{did_id}")
def ledger_resolve(did_id: str):
    try:
        return get_ledger().resolve(did_id)
    except Exception as e:
        raise HTTPException(404, f"resolution failed: {e}")


# ---------- governance: the human gate ----------

@app.post("/govern/decide")
def govern_decide(req: GovernRequest):
    """Record the human decision on a case. 'revoke' anchors a credential
    revocation on-chain (accountability trail); 'clear'/'watch' stay off-chain."""
    case = CASES.get(req.case_id)
    if case is None:
        case = CASES[req.case_id] = {"case_id": req.case_id, "did_id": req.did_id}
    case.update({"action": req.action, "approved_by": req.approved_by,
                 "human_approved": True})

    tx_hash = None
    if req.action == "revoke":
        import hashlib
        cred_hash = hashlib.sha256(f"{req.case_id}:{req.did_id}".encode()).digest()
        receipt = get_ledger().revoke_credential(cred_hash)
        tx_hash = receipt["transactionHash"].hex()
        case["revoked_cred_hash"] = cred_hash.hex()

    case["onchain_tx"] = tx_hash
    return {"case_id": req.case_id, "action": req.action,
            "recorded": True, "onchain_tx": tx_hash,
            "message": "revocation anchored on-chain" if tx_hash
                       else "decision recorded (off-chain)"}


@app.get("/ledger/verify/{case_id}")
def ledger_verify(case_id: str):
    """Auditor view: confirm the on-chain revocation status for a case."""
    case = CASES.get(case_id)
    if case is None or "revoked_cred_hash" not in case:
        raise HTTPException(404, "no on-chain revocation recorded for this case")
    revoked = get_ledger().is_credential_revoked(bytes.fromhex(case["revoked_cred_hash"]))
    return {"case_id": case_id, "onchain_revoked": revoked,
            "tx": case["onchain_tx"], "approved_by": case.get("approved_by")}


@app.get("/health")
def health():
    return {"status": "ok", "components": ["ssi", "ml", "agent", "ledger"]}

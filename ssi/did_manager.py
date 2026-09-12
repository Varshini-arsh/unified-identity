"""
ssi/did_manager.py
Decentralized Identifier (DID) creation, resolution and Verifiable Credential
issuance/verification for the Unified Digital Identity Management System.

DID method used: did:ethr-compatible anchoring on the local Hardhat ledger
(via the DIDRegistry contract). Credentials follow the W3C Verifiable
Credentials data model. ZK-predicates (AnonCreds-style selective disclosure)
are represented as derived claims; swap-in point for AnonCreds/BBS+ later.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).hexdigest().encode()


@dataclass
class DIDDocument:
    did_id: str
    verification_method: str
    created: str
    keys: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class DIDManager:
    """Manages DID keypairs and constructs DID documents.

    The on-chain anchor (docHash) is computed here and written by the
    ledger client via the DIDRegistry contract.
    """

    @staticmethod
    def generate_keypair() -> dict:
        # Ed25519-style key material placeholder (deterministic libsodium later);
        # for the prototype we use secure random 32-byte secrets.
        return {
            "private_key": secrets.token_hex(32),
            "public_key": secrets.token_hex(32),
            "algorithm": "ed25519-placeholder",
        }

    def create_did(self, method: str = "ethr", namespace: str = "unified") -> tuple[DIDDocument, dict]:
        keys = self.generate_keypair()
        did_id = f"did:{method}:{namespace}:{keys['public_key'][:40]}"
        doc = DIDDocument(
            did_id=did_id,
            verification_method=f"{did_id}#keys-1",
            created=utcnow(),
            keys={"public": keys["public_key"], "algorithm": keys["algorithm"]},
        )
        return doc, keys

    @staticmethod
    def doc_hash(doc: DIDDocument) -> bytes:
        """32-byte digest of the canonical document, used as the on-chain anchor."""
        return hashlib.sha256(doc.to_json().encode()).digest()

    @staticmethod
    def resolve(did_id: str) -> dict:
        """Resolve against the ledger client (wired in api layer)."""
        raise NotImplementedError("Resolution goes through api/ledger_client.py")


@dataclass
class VerifiableCredential:
    context: list
    cred_type: list
    issuer: str
    subject_id: str
    claims: dict
    issued: str
    expiry: str | None = None
    proof: dict | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def hash(self) -> bytes:
        return hashlib.sha256(self.to_json().encode()).digest()


class CredentialIssuer:
    """Issues W3C-shaped Verifiable Credentials with ZK-ready derived claims."""

    ZK_PREDICATES = {"age_over_18", "age_over_21", "balance_gt", "kyc_level"}

    def issue(
        self,
        issuer_did: str,
        subject_did: str,
        claims: dict,
        cred_type: str = "UnifiedIdentityCredential",
        apply_predicates: bool = True,
    ) -> VerifiableCredential:
        out = dict(claims)
        if apply_predicates:
            for pred in self.ZK_PREDICATES:
                if pred.startswith("age_over") and "age" in out:
                    out[pred] = out["age"] >= int(pred.rsplit("_", 1)[1])
                    del out["age"]  # selective disclosure: raw value never leaves
        return VerifiableCredential(
            context=["https://www.w3.org/2018/credentials/v1"],
            cred_type=["VerifiableCredential", cred_type],
            issuer=issuer_did,
            subject_id=subject_did,
            claims=out,
            issued=utcnow(),
            proof=None,  # signature wired once ed25519 signing lands (pynacl)
        )

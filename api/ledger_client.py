"""
api/ledger_client.py - Python bridge to the DIDRegistry contract.

Uses web3.py against a local Hardhat node (docker-free path).
"""
from __future__ import annotations

import json
from pathlib import Path

from web3 import Web3

ABI_PATH = Path(__file__).parent.parent / "ledger" / "artifacts" / "contracts" / "DIDRegistry.sol" / "DIDRegistry.json"


class LedgerClient:
    def __init__(self, rpc_url: str = "http://127.0.0.1:8545", contract_address: str | None = None,
                 private_key: str | None = None):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"No ledger at {rpc_url} - run `npx hardhat node` in ledger/")
        abi = json.loads(ABI_PATH.read_text())["abi"] if ABI_PATH.exists() else []
        if contract_address is None:
            raise ValueError("contract_address required (deploy first: `npx hardhat run scripts/deploy.js`)")
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=abi
        )
        self.account = self.w3.eth.account.from_key(private_key) if private_key else self.w3.eth.accounts[0]

    def _send(self, fn):
        tx = fn.build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": 500_000,
            "gasPrice": self.w3.eth.gas_price,
        })
        signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self.w3.eth.wait_for_transaction_receipt(h)

    def create_did(self, did_id: str, doc_hash: bytes):
        return self._send(self.contract.functions.createDID(did_id, doc_hash))

    def revoke_credential(self, cred_hash: bytes):
        return self._send(self.contract.functions.revokeCredential(cred_hash))

    def resolve(self, did_id: str) -> dict:
        owner, doc_hash, updated, revoked = self.contract.functions.resolveDID(did_id).call()
        return {"owner": owner, "doc_hash": doc_hash.hex(), "updated_at": updated, "revoked": revoked}

    def is_credential_revoked(self, cred_hash: bytes) -> bool:
        return self.contract.functions.isCredentialRevoked(cred_hash).call()

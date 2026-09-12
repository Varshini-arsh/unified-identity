"""
agent/config.py - loads GEMINI_API_KEY from a .env file at project root.

Never paste API keys into chat or commit them to git (.env is gitignored).
Get a free key: https://aistudio.google.com/apikey
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_gemini_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print(
            "[config] GEMINI_API_KEY not set.\n"
            "         Create .env at project root with one line:\n"
            '         GEMINI_API_KEY=your_key_here\n'
            "         Free key: https://aistudio.google.com/apikey"
        )
    return key


# ---------- ledger settings (local Hardhat defaults) ----------

# Hardhat's well-known account #0 private key (public test key, zero real value).
# It is the DIDRegistry deployer, hence the trusted issuer for revocations.
HARDHAT_ACCOUNT0_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def get_ledger_config() -> dict:
    return {
        "rpc_url": os.getenv("LEDGER_RPC_URL", "http://127.0.0.1:8545"),
        "contract_address": os.getenv("LEDGER_CONTRACT_ADDRESS", ""),
        "private_key": os.getenv("LEDGER_PRIVATE_KEY", HARDHAT_ACCOUNT0_KEY),
    }

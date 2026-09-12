# AI-Enabled Blockchain-Based Unified Digital Identity Management System

Docker-free prototype stack: Hardhat (EVM ledger) + Python SSI (DIDs/VCs)
+ ML trust engine (Isolation Forest + GraphSAGE + SHAP) + LangGraph agent
with human-in-the-loop governance.

## Layout
- `ledger/`   Solidity DIDRegistry + revocation (Hardhat, Node 24)
- `ssi/`      DID creation, W3C Verifiable Credentials, ZK-predicate claims
- `ml/`       Elliptic dataset loader, anomaly detection trust engine
- `api/`      FastAPI tools (identity, credentials, risk) + web3 ledger client
- `agent/`    LangGraph Fraud Investigation Agent (Gemini, human gate)
- `web/`      React dashboard (Phase 2)

## Setup (one-time, from this folder)
```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt --cache-dir D:/pip-cache
cd ledger && npm install && cd ..
```

## Run order (3 terminals)
```bash
# 1. Local blockchain
cd ledger && npx hardhat node

# 2. Deploy contract (new terminal, note the printed address)
cd ledger && npx hardhat run scripts/deploy.js --network localhost

# 3. API
.venv/Scripts/uvicorn api.main:app --port 8000

# 4. Agent demo
set GEMINI_API_KEY=your_key
.venv/Scripts/python -m agent.investigator
```

## Free resources needed
- Gemini API key: https://aistudio.google.com/apikey
- Elliptic dataset (free): https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
  → unzip the 3 CSVs into `ml/data/elliptic/`

## Paper mapping
- Novelty: agentic orchestration of identity lifecycle + GNN Sybil detection + on-chain accountability
- Benchmarks: Hyperledger Caliper (optional) / Hardhat gas reports; AUC/precision on Elliptic

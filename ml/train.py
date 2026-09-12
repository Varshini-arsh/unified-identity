"""
ml/train.py - trains the trust engine on the real Elliptic dataset.

Outputs (ml/artifacts/):
    graphsage_model.pt   trained GNN weights
    metrics.json         AUC / precision / recall / F1 for both models
Paper-ready: these are the first benchmark numbers for the journal draft.
Run:  .venv/Scripts/python -m ml.train
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

from ml.dataset import load_elliptic, split_masks
from ml.sybil_detector import GraphSAGEDetector, IsolationForestDetector

ART = Path(__file__).parent / "artifacts"
ART.mkdir(exist_ok=True)


def main() -> None:
    print("[1/5] loading Elliptic dataset (~203k nodes, 690MB CSV)...")
    data = load_elliptic()
    data = split_masks(data)
    print(f"      nodes={data.num_nodes}, edges={data.edge_index.shape[1]}, "
          f"known labels={int(data.known_mask.sum())}")

    y_true = data.y[data.test_mask].numpy()

    # ---------- baseline: Isolation Forest on raw features ----------
    print("[2/5] training Isolation Forest baseline...")
    X_train = data.x[data.train_mask].numpy()
    iso = IsolationForestDetector(contamination=0.10).fit(X_train)
    iso_scores = iso.risk_scores(data.x[data.test_mask].numpy())
    iso_pred = (iso_scores >= 0.8).astype(int)

    # ---------- GraphSAGE ----------
    print("[3/5] training GraphSAGE (100 epochs, CPU)...")
    torch.manual_seed(42)
    gnn = GraphSAGEDetector(in_dim=data.x.size(1), hidden=64)
    gnn.train_model(data, epochs=100, lr=0.01)

    print("[4/5] evaluating on held-out test set...")
    gnn_scores = gnn.risk_scores(data)[data.test_mask]
    gnn_pred = (gnn_scores >= 0.5).astype(int)

    metrics = {
        "graphsage": {
            "auc": round(float(roc_auc_score(y_true, gnn_scores)), 4),
            "precision": round(float(precision_score(y_true, gnn_pred)), 4),
            "recall": round(float(recall_score(y_true, gnn_pred)), 4),
            "f1": round(float(f1_score(y_true, gnn_pred)), 4),
        },
        "isolation_forest": {
            "auc": round(float(roc_auc_score(y_true, iso_scores)), 4),
            "precision": round(float(precision_score(y_true, iso_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_true, iso_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_true, iso_pred, zero_division=0)), 4),
        },
        "dataset": {
            "nodes": int(data.num_nodes),
            "edges": int(data.edge_index.shape[1]),
            "labeled": int(data.known_mask.sum()),
            "test_size": int(data.test_mask.sum()),
        },
    }

    print("[5/5] saving artifacts...")
    torch.save(gnn.state_dict(), ART / "graphsage_model.pt")
    (ART / "metrics.json").write_text(json.dumps(metrics, indent=2))

    print(json.dumps(metrics, indent=2))
    print("DONE - metrics in ml/artifacts/metrics.json")


if __name__ == "__main__":
    main()

"""
ml/sybil_detector.py - identity-graph anomaly detection for the trust engine.

Stack: Isolation Forest (fast, interpretable baseline) + GraphSAGE GNN
(PyTorch Geometric) on the transaction/interaction graph, with SHAP
explanations for the tabular branch. This module is what the Fraud
Investigation Agent calls as a tool.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.ensemble import IsolationForest
from torch_geometric.nn import SAGEConv


class IsolationForestDetector:
    """Fast baseline risk scorer over tabular identity/transaction features."""

    def __init__(self, contamination: float = 0.05, seed: int = 42):
        self.model = IsolationForest(
            n_estimators=200, contamination=contamination, random_state=seed
        )

    def fit(self, X: np.ndarray) -> "IsolationForestDetector":
        self.model.fit(X)
        train_raw = -self.model.score_samples(X)
        self._train_min, self._train_max = float(train_raw.min()), float(train_raw.max())
        return self

    def risk_scores(self, X: np.ndarray, bounded: bool = True) -> np.ndarray:
        """Return scores where higher = more anomalous.

        bounded=True  -> clipped to [0,1] vs training range (for API display).
        bounded=False -> rank-preserving logistic squash (for metrics/AUC;
                         clipping is NOT monotonic at the boundaries and
                         destroys ranking of out-of-range extreme anomalies).
        """
        raw = -self.model.score_samples(X)  # higher = more anomalous
        if bounded:
            span = (self._train_max - self._train_min) + 1e-9
            return np.clip((raw - self._train_min) / span, 0.0, 1.0)
        mid = (self._train_max + self._train_min) / 2.0
        scale = ((self._train_max - self._train_min) / 6.0) + 1e-9
        return 1.0 / (1.0 + np.exp(-(raw - mid) / scale))

    def flag(self, X: np.ndarray, threshold: float = 0.8) -> np.ndarray:
        return self.risk_scores(X) >= threshold


class GraphSAGEDetector(torch.nn.Module):
    """2-layer GraphSAGE for node-level illicit/fraud classification."""

    def __init__(self, in_dim: int, hidden: int = 64):
        super().__init__()
        self.conv1 = SAGEConv(in_dim, hidden)
        self.conv2 = SAGEConv(hidden, 2)

    def forward(self, x, edge_index):
        h = F.relu(self.conv1(x, edge_index))
        return self.conv2(h, edge_index)

    def train_model(self, data, epochs: int = 100, lr: float = 0.01, device="cpu"):
        self.to(device)
        data = data.to(device)
        opt = torch.optim.Adam(self.parameters(), lr=lr, weight_decay=5e-4)
        for epoch in range(epochs):
            self.train()
            opt.zero_grad()
            out = self(data.x, data.edge_index)
            loss = F.cross_entropy(out[data.train_mask], data.y[data.train_mask])
            loss.backward()
            opt.step()
            if epoch % 10 == 0:
                acc = self.evaluate(data)
                print(f"epoch {epoch:3d} loss {loss.item():.4f} val-acc {acc:.4f}")

    @torch.no_grad()
    def evaluate(self, data) -> float:
        self.eval()
        out = self(data.x, data.edge_index)
        pred = out[data.val_mask].argmax(dim=1)
        return (pred == data.y[data.val_mask]).float().mean().item()

    @torch.no_grad()
    def risk_scores(self, data) -> np.ndarray:
        self.eval()
        prob = F.softmax(self(data.x, data.edge_index), dim=1)[:, 1]
        return prob.cpu().numpy()


def shap_explain(detector: IsolationForestDetector, X: np.ndarray, sample_idx: int):
    """Placeholder SHAP hook: swap in shap.TreeExplainer(detector.model)."""
    try:
        import shap
        explainer = shap.TreeExplainer(detector.model)
        return explainer.shap_values(X[sample_idx : sample_idx + 1])
    except ImportError:
        return None

"""Pathways Structural Analysis workbench.

Read-only structural profiling of the NHS Pathways dataset, producing reproducible
evidence for an Architecture Decision Record comparing monolithic, federated and
specialised Bayesian Network designs.

Phase 1 (this package) measures structure only. It produces no Bayesian-network sizing
and no architectural recommendation.

Data handling: this package reads the source database read-only, writes derived
analytical outputs to ``data/processed/`` and ``outputs/``, and sends nothing to any
external service.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"

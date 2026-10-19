"""Run configuration and identifiers for inspectable local backtests."""

from datetime import datetime, timezone
import hashlib
import json
import math
from uuid import uuid4


_SECRET_PARTS = ("secret", "password", "token", "api_key", "credential")


def _safe_parameters(values):
    result = {}
    for key, value in sorted(values.items()):
        if any(part in key.lower() for part in _SECRET_PARTS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, float) and not math.isfinite(value):
                continue
            result[key] = value
    return result


def _sanitize_config(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_config(item)
            for key, item in value.items()
            if not any(part in key.lower() for part in _SECRET_PARTS)
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_config(item) for item in value]
    return value


def build_run_metadata(engine, result, dataset_provenance=None, config=None):
    """Build a unique run ID and deterministic input fingerprint."""
    strategy = engine.strategy
    cost_model = getattr(engine.execution_engine, "cost_model", None)
    generated = {
        "dataset_fingerprint": getattr(dataset_provenance, "fingerprint", None),
        "symbol": engine.symbol,
        "strategy": f"{strategy.__class__.__module__}.{strategy.__class__.__qualname__}",
        "strategy_id": getattr(strategy, "strategy_id", None),
        "strategy_version": getattr(strategy, "version", None),
        "strategy_parameters_declared": _safe_parameters(getattr(strategy, "parameters", {})),
        "strategy_parameters": _safe_parameters(vars(strategy)),
        "initial_capital": float(engine.portfolio.initial_capital),
        "position_sizer_type": f"{engine.position_sizer.__class__.__module__}.{engine.position_sizer.__class__.__qualname__}",
        "position_sizer": _safe_parameters(vars(engine.position_sizer)),
        "volatility_model": f"{engine.volatility_model.__class__.__module__}.{engine.volatility_model.__class__.__qualname__}",
        "volatility_parameters": _safe_parameters(vars(engine.volatility_model)),
        "execution_engine": f"{engine.execution_engine.__class__.__module__}.{engine.execution_engine.__class__.__qualname__}",
        "transaction_costs": _safe_parameters(vars(cost_model)) if cost_model else {},
        "execution_assumptions": {
            "signal_timing": "previous completed bar executed at current bar open",
            "valuation": "current bar close",
        },
        "requested_start": getattr(dataset_provenance, "requested_start", None),
        "requested_end": getattr(dataset_provenance, "requested_end", None),
    }
    if config:
        generated.update(_sanitize_config(config))
    canonical = json.dumps(generated, sort_keys=True, separators=(",", ":"), allow_nan=False)
    dataset_fp = generated.get("dataset_fingerprint")
    reproducibility_payload = json.dumps(
        {"configuration": generated, "dataset_fingerprint": dataset_fp},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return {
        "schema_version": "quantforge-backtest-run-v1",
        "run_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reproducibility_fingerprint": hashlib.sha256(reproducibility_payload).hexdigest(),
        "configuration": json.loads(canonical),
        "dataset_provenance": dataset_provenance.to_dict() if dataset_provenance else None,
        "metrics": {
            "final_value": float(result["final_value"]),
            "total_return": float(result["final_value"]) / float(engine.portfolio.initial_capital) - 1.0,
            "cash": float(result["cash"]),
            "position": int(result["position"]),
            "trade_count": len(result["trade_history"]),
        },
        "status": "completed",
    }

"""Distribution, correlation and WACC robustness using the same workbook-backed DCF."""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import alphabet_model as am
import monte_carlo as mc


def normal_cdf(x):
    return np.array([0.5 * (1 + math.erf(v / math.sqrt(2))) for v in x.flat]).reshape(x.shape)


def triangular(u):
    return np.where(u < 0.5, np.sqrt(2*u)-1, 1-np.sqrt(2*(1-u)))


def run(n=10000, seed=7, output_dir=Path("results")):
    if n < 1:
        raise ValueError("Trial count must be positive.")
    target = mc.MARKET_CAP + mc.CLAIMS_EX_NCI + mc.NCI_PLACEHOLDER - mc.NON_OP
    k = len(mc.DRIVERS)
    c = mc.corr_matrix()
    draws = np.random.default_rng(seed).standard_normal((n, k))
    correlated_u = normal_cdf(draws @ np.linalg.cholesky(c).T)
    main_positions = triangular(correlated_u)
    if not np.allclose(main_positions, mc.sample(n, seed)):
        raise AssertionError("Robustness and main sampler disagree.")
    result = {"trials": n, "seed": seed, "workbook_sha256": am.WORKBOOK.sha256,
              "units": "USD millions", "market_operating_ev": target,
              "note": "Conditional frequencies among valid trials. WACC stress draws an independent 18th latent variable.",
              "runs": {}}

    def record(name, positions, wacc_draws=None):
        w0 = am.WACC
        ev = []
        try:
            for i, row in enumerate(positions):
                am.WACC = w0 if wacc_draws is None else wacc_draws[i]
                ev.append(am.value(dict(zip(mc.DRIVERS, row)))["ev"])
        finally:
            am.WACC = w0
        ev = np.asarray(ev)
        valid = np.isfinite(ev)
        values = ev[valid]
        if not len(values):
            raise ValueError(f"No valid trials in {name}.")
        stats = {"p10_p50_p90": np.percentile(values, [10, 50, 90]).tolist(),
                 "maximum": float(values.max()), "minimum": float(values.min()),
                 "valid_trials": int(valid.sum()), "invalid_trials": int((~valid).sum()),
                 "above_market_count": int((values >= target).sum()),
                 "above_market_frequency": float((values >= target).mean())}
        result["runs"][name] = stats
        print(name, json.dumps(stats), flush=True)

    record("triangular", main_positions)
    record("uniform", 2*correlated_u-1)
    record("independent", triangular(normal_cdf(draws)))
    stressed = np.eye(k) + 1.3*(c-np.eye(k))
    record("correlations_x1_3", triangular(normal_cdf(draws @ np.linalg.cholesky(stressed).T)))
    x18 = np.random.default_rng(seed).standard_normal((n, k+1))
    positions = triangular(normal_cdf(x18[:, :k] @ np.linalg.cholesky(c).T))
    w_position = triangular(normal_cdf(x18[:, -1]))
    w0 = am.WACC
    for width in (0.01, 0.02):
        record(f"wacc_plus_minus_{width:.2f}", positions, w0+width*w_position)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / "robustness_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--trials", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    if args.workbook:
        am.load_workbook(args.workbook)
        mc.refresh_bridge()
    run(args.trials, args.seed, args.output_dir)

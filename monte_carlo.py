"""
Monte Carlo DCF, tornado and reverse DCF on the calibrated sheet replica.

Each driver takes a position z in [-1, +1]: 0 = Base, +1 = Bull row, -1 = Bear row
of the sheet's Assumptions tab. z is drawn from a symmetric triangular distribution
(mode 0), with dependence applied through a Gaussian copula. The matrix specifies
latent Gaussian correlations, not exact Pearson correlations of financial inputs.
Piecewise mapping of z to asymmetric or non-monotonic scenario paths need not
produce a standard triangular distribution in the financial input's own units.
Bear/Base/Bull are anchors, not categories with assigned probabilities. One z per
driver applies across its forecast path; the model does not redraw annual shocks.

Ranges and evidence/judgement distinctions are documented in Simulation inputs.
Results are conditional on those ranges, the copula and the model. See
robustness.py for the uniform-position robustness run.
"""
import json
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import alphabet_model as am
from alphabet_model import value

DRIVERS = ["search", "yt", "net", "subs", "cloud_demand", "cloud_margin", "capex_int",
           "commission", "hw_life", "tac_change", "ai_unit", "ai_workload",
           "research_elast", "ob_cost", "funding", "term_return", "term_growth"]
LABELS = {
    "search": "Search growth", "yt": "YouTube ad growth", "net": "Network growth",
    "subs": "Subscriptions growth", "cloud_demand": "Cloud demand growth",
    "cloud_margin": "Cloud margin", "capex_int": "CapEx intensity",
    "commission": "Commissioning rate", "hw_life": "Hardware life",
    "tac_change": "TAC partner pricing", "ai_unit": "AI unit-cost gain",
    "ai_workload": "AI workload growth", "research_elast": "Research cost elasticity",
    "ob_cost": "Other Bets (revenue and cost)", "funding": "Customer-funding stress",
    "term_return": "Terminal return ceiling",
    "term_growth": "Terminal growth"}

# Latent Gaussian correlations (analyst assumption; positive = tend toward Bull together)
CORR_PAIRS = {("search", "yt"): 0.5, ("search", "subs"): 0.4, ("yt", "subs"): 0.4,
              ("search", "net"): 0.3, ("cloud_demand", "cloud_margin"): 0.4,
              ("cloud_demand", "capex_int"): 0.4, ("cloud_margin", "term_return"): 0.3,
              ("search", "term_return"): 0.3, ("commission", "cloud_demand"): 0.3,
              ("funding", "cloud_demand"): 0.3}

CORR_ROWS = {("search", "yt"): 24, ("search", "subs"): 25, ("yt", "subs"): 26,
             ("search", "net"): 27, ("cloud_demand", "cloud_margin"): 28,
             ("cloud_demand", "capex_int"): 29, ("commission", "cloud_demand"): 30,
             ("funding", "cloud_demand"): 31, ("cloud_margin", "term_return"): 32,
             ("search", "term_return"): 33}

def refresh_bridge():
    """Read the same Base bridge as the workbook; simulation holds this bridge fixed."""
    global MARKET_CAP, NON_OP, CLAIMS_EX_NCI, NCI_PLACEHOLDER
    n = am.WORKBOOK.number
    MARKET_CAP = n("Valuation", "B7")
    NON_OP = n("Valuation", "B49")
    NCI_PLACEHOLDER = n("Valuation", "B17")
    CLAIMS_EX_NCI = sum(n("Valuation", cell) for cell in ("B8", "B13", "B14", "B16"))
    for pair, row in CORR_ROWS.items():
        r = n("Simulation inputs", f"B{row}")
        if not -1 <= r <= 1:
            raise ValueError(f"Invalid latent correlation in Simulation inputs!B{row}")
        CORR_PAIRS[pair] = r


refresh_bridge()


def corr_matrix():
    n = len(DRIVERS); c = np.eye(n)
    for (a, b), r in CORR_PAIRS.items():
        i, j = DRIVERS.index(a), DRIVERS.index(b); c[i, j] = c[j, i] = r
    return c


def sample(n, seed=7):
    rng = np.random.default_rng(seed)
    L = np.linalg.cholesky(corr_matrix())
    x = rng.standard_normal((n, len(DRIVERS))) @ L.T
    u = np.array([.5 * (1 + math.erf(v / math.sqrt(2))) for v in x.flat]).reshape(x.shape)
    return np.where(u < .5, np.sqrt(2*u)-1, 1-np.sqrt(2*(1-u)))


def brentq(f, lo, hi):
    """Bracketed bisection fallback; no SciPy dependency is needed for these smooth roots."""
    flo, fhi = f(lo), f(hi)
    if not np.isfinite(flo + fhi) or flo * fhi > 0:
        raise ValueError("Root is not bracketed")
    for _ in range(100):
        mid = (lo + hi) / 2
        fm = f(mid)
        if not np.isfinite(fm):
            raise ValueError("Non-finite function inside bracket")
        if abs(hi-lo) < 1e-12 or fm == 0:
            return mid
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def run(n=10000, tax_explicit=None, nci=None, seed=7):
    if n < 1:
        raise ValueError("Trial count must be positive.")
    nci = NCI_PLACEHOLDER if nci is None else nci
    zs = sample(n, seed)
    outs = [value(dict(zip(DRIVERS, z)), tax_explicit=tax_explicit) for z in zs]
    ev = np.array([r["ev"] for r in outs])
    global FLOOR_BIND_TRIALS
    FLOOR_BIND_TRIALS = int(sum(bool(r.get("floor_bind", np.zeros(1)).any()) for r in outs))
    claims = CLAIMS_EX_NCI + nci
    # trials where the starting return on new capital is not positive have no defined terminal
    # value in the workbook (#N/A); they are reported separately and excluded from percentiles
    equity = ev + NON_OP - claims
    market_ev = MARKET_CAP + claims - NON_OP
    return ev, equity, market_ev, zs


def tornado(tax_explicit=None):
    base = value(tax_explicit=tax_explicit)["ev"]
    rows = []
    for d in DRIVERS:
        lo = value({d: -1}, tax_explicit=tax_explicit)["ev"]
        hi = value({d: 1}, tax_explicit=tax_explicit)["ev"]
        if not (np.isfinite(lo) and np.isfinite(hi)):
            continue
        rows.append((LABELS[d], lo, hi))
    rows.sort(key=lambda r: abs(r[2] - r[1]), reverse=True)
    return base, rows


def reverse_dcf(target, tax_explicit=None):
    """Single-lever values that reproduce the market-implied operating EV."""
    out = {}
    f = lambda **kw: value(tax_explicit=tax_explicit, overrides=kw)["ev"] - target
    def solve(key, lo, hi):
        try:
            return brentq(lambda x: f(**{key: x}), lo, hi)
        except ValueError:
            return None
    out["terminal_margin"] = solve("term_margin", 0.3, 0.9)
    out["terminal_return"] = solve("term_return", 0.0926, 50)
    out["capex_scale"] = solve("capex_scale", 0.05, 1.0)
    out["cloud_margin_add"] = solve("cloud_margin_add", 0.0, 1.0)
    return out


def simulate(n=10000, seed=7, output_dir="results", tax=None, nci=None):
    """Write results and charts for one reproducible simulation run."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ev_all, eq_all, mkt_ev, zs = run(n=n, tax_explicit=tax, nci=nci, seed=seed)
    ok = np.isfinite(ev_all)
    ev, eq = ev_all[ok], eq_all[ok]
    if not len(ev):
        raise ValueError("No valid trials; review the growth/return assumptions.")
    base_ev = value(tax_explicit=tax)["ev"]
    pct = np.percentile(ev, [5, 10, 50, 90, 95])
    res = dict(trials=n, seed=seed, valid_trials=int(ok.sum()),
               workbook=am.WORKBOOK.path.name, workbook_sha256=am.WORKBOOK.sha256,
               units="USD millions", valuation_date=am.VAL_DATE.isoformat(),
               distribution="triangular scenario positions; Gaussian copula",
               base_ev=base_ev, market_implied_ev=mkt_ev,
               ev_p5=pct[0], ev_p10=pct[1], ev_p50=pct[2], ev_p90=pct[3], ev_p95=pct[4],
               ev_mean=ev.mean(), prob_ev_above_market=float((ev >= mkt_ev).mean()),
               market_percentile=float(100 * (ev <= mkt_ev).mean()),
               equity_p10=np.percentile(eq, 10), equity_p50=np.percentile(eq, 50),
               equity_p90=np.percentile(eq, 90), max_ev=ev.max(), min_ev=ev.min(),
               invalid_trials=int((~ok).sum()), all_bull=am.scenario("bull", tax_explicit=tax)["ev"],
               all_bear=am.scenario("bear", tax_explicit=tax)["ev"])
    base, rows = tornado(tax)
    rev = reverse_dcf(mkt_ev, tax)
    res["reverse_dcf"] = rev
    # value-maximising combination within the Bear-Bull ranges (coordinate search)
    zmax = {d: 1.0 for d in DRIVERS}; grid = np.linspace(-1, 1, 21)
    for _ in range(3):
        for d in DRIVERS:
            zmax[d] = max(grid, key=lambda x: np.nan_to_num(value({**zmax, d: x}, tax_explicit=tax)["ev"], nan=-1))
    res["max_combo_ev"] = value(zmax, tax_explicit=tax)["ev"]
    res["max_combo"] = {k: float(v) for k, v in zmax.items()}
    res["floor_bind_trials"] = FLOOR_BIND_TRIALS
    w0 = am.WACC
    def ev_at(w, z=None):
        am.WACC = w
        try:
            return value(z, tax_explicit=tax)["ev"]
        finally:
            am.WACC = w0
    res["max_combo_ev_wacc_minus_10bp"] = ev_at(w0 - 0.001, zmax)
    def breakeven_wacc(z=None):
        # A market refresh can put the best case above the current market EV.
        # Search on both sides of current WACC, above every terminal-growth rate.
        try:
            return brentq(lambda w: ev_at(w, z) - mkt_ev, 0.04, max(0.20, w0))
        except ValueError:
            return None  # No crossing in the stated economic search interval.
    res["max_combo_breakeven_wacc"] = breakeven_wacc(zmax)
    res["base_breakeven_wacc"] = breakeven_wacc()
    res["tornado"] = [(l, lo, hi) for l, lo, hi in rows]
    res["above_market_count"] = int((ev >= mkt_ev).sum())
    res["frequency_note"] = "Qualifying valid trials / valid trials; conditional on the model, not calibrated real-world odds."
    (output_dir / "monte_carlo_results.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    print(json.dumps(res, indent=2, default=float))

    # histogram
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    ax.hist(ev / 1e6, bins=70, color="#4C72B0", alpha=0.85)
    ax.axvline(mkt_ev / 1e6, color="#C44E52", lw=2, label=f"Market-implied EV {mkt_ev/1e6:.2f}tn")
    ax.axvline(np.median(ev) / 1e6, color="#333333", lw=1.2, ls="--", label=f"Median {np.median(ev)/1e6:.2f}tn")
    ax.set_xlabel("Operating EV (USD tn)"); ax.set_ylabel(f"Trials (of {n:,})")
    ax.set_title(f"Monte Carlo operating EV | {am.VAL_DATE:%d %B %Y}")
    ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(output_dir / "mc_histogram.png"); plt.close(fig)
    # tornado
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    top = rows[:10][::-1]
    for i, (lab, lo, hi) in enumerate(top):
        ax.barh(i + 0.19, (lo - base) / 1e6, height=0.36, color="#C44E52", label="Bear-case setting" if i == 0 else None)
        ax.barh(i - 0.19, (hi - base) / 1e6, height=0.36, color="#55A868", label="Bull-case setting" if i == 0 else None)
    ax.legend(frameon=False, loc="lower right")
    ax.set_yticks(range(len(top))); ax.set_yticklabels([r[0] for r in top])
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_xlabel(f"Change in operating EV vs Base of {base/1e6:.2f}tn (USD tn)")
    ax.set_title("What moves the value: one driver at a time")
    fig.text(0.01, 0.01, "Bull-case CapEx is a larger build, so both CapEx settings lower value.", fontsize=7, color="#555")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(output_dir / "mc_tornado.png"); plt.close(fig)
    return res


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Workbook-backed Alphabet Monte Carlo DCF")
    parser.add_argument("--workbook", type=Path, help="Recalculated XLSX export; defaults to data/Business_Valuation.xlsx")
    parser.add_argument("--trials", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    if args.workbook:
        am.load_workbook(args.workbook)
        refresh_bridge()
    simulate(n=args.trials, seed=args.seed, output_dir=args.output_dir)


if __name__ == "__main__":
    main()

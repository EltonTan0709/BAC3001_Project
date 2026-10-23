"""
Alphabet DCF replica of the included Business Valuation workbook.

Inputs are read from data/Business_Valuation.xlsx (or BAC3001_WORKBOOK).
The workbook must be recalculated before export; Python computes each trial's DCF.

Mirrors the sheet's driver chain, tab by tab:
  Operating forecast : segment revenue -> Services / Cloud reference EBIT (TAC mix, AI serving
                       cost) -> Other Bets and Alphabet-level costs -> reference D&A replaced by
                       the capital schedule -> NOPAT
  Cloud demand       : opening backlog schedule + new business, delivery limited by capacity
                       coverage (average in-service PP&E vs capacity required by planned demand)
  Capital and FCFF   : CapEx = intensity x planned group demand; commissioning; cohort depreciation
  Working capital    : operating WC = non-cash NOWC plus required cash (2% of annual/TTM sales)
  Transition         : 2032-2036 fade of growth, tax and return on new capital; the margin fades to
                       the 2031 margin after construction-in-progress normalisation; terminal return
                       = min(ceiling, starting implied return)
  Valuation          : mid-period discounting, H2 2026 stub at its midpoint, TV shifted once.

USD millions. Driver positions z in [-1, +1]: 0 = Base row, +1 = Bull row, -1 = Bear row.
"""
import numpy as np
from workbook_inputs import load_inputs


def load_workbook(path=None):
    """Load inputs from a recalculated XLSX export; retain the Python DCF engine."""
    workbook = load_inputs(path)
    globals().update(workbook.inputs())
    globals()['WORKBOOK'] = workbook
    return workbook


load_workbook()


def _z(z, name):
    return z.get(DRIVER_OF.get(name, name), 0.0)


def path(name, z):
    s = SCEN[name]
    base = np.array(s["base"], float)
    other = np.array(s["bull"] if z >= 0 else s["bear"], float)
    return base + abs(z) * (other - base)


def scalar(name, z):
    b, bu, be = SCALAR[name]
    if be is None:
        be = WACC
    return b + z * (bu - b) if z >= 0 else b + (-z) * (be - b)


def value(z=None, tax_explicit=None, tax_terminal=None, mid_year=None, overrides=None):
    """Operating EV for driver positions z (dict driver -> [-1, 1]); returns a dict of outputs."""
    z = z or {}
    o = overrides or {}
    P = lambda k: path(k, _z(z, k))
    S = lambda k: o.get(k, scalar(k, _z(z, k)))
    tax_ex = TAX_EXPLICIT if tax_explicit is None else np.asarray(tax_explicit, float)
    tax_terminal = TAX_TERMINAL if tax_terminal is None else tax_terminal
    mid_year = MID_YEAR if mid_year is None else mid_year

    # --- Services and Other Bets revenue (H2 = prior-year H2 x growth; FY2026 = H1 + H2)
    def grow(h2_25, h1_26, gr):
        v = [h2_25 * (1 + gr[0])]
        lvl = h1_26 + v[0]
        for t in range(1, 6):
            lvl *= 1 + gr[t]
            v.append(lvl)
        return np.array(v)
    seg = {k: grow(H2_25[k], H1_26[k], P(k)) for k in ["search", "yt", "net", "subs"]}
    services = seg["search"] + seg["yt"] + seg["net"] + seg["subs"]
    ob_rev = grow(H2_25["ob"], H1_26["ob"], P("ob_rev"))

    # --- planned Cloud demand (Cloud demand rows 10-13)
    cg = P("cloud_demand")
    sched = BACKLOG * BACKLOG_SHARE
    planned = np.zeros(6)
    pre = H2_25["cloud"] * (1 + cg[0])
    planned[0] = max(pre, sched[0] / (1 - MIN_NEW_SHARE))
    pre = (H1_26["cloud"] + planned[0]) * (1 + cg[1])
    planned[1] = max(pre, sched[1] / (1 - MIN_NEW_SHARE))
    for t in range(2, 6):
        planned[t] = max(planned[t - 1] * (1 + cg[t]), sched[t] / (1 - MIN_NEW_SHARE))
    group_demand = services + ob_rev + planned

    # --- CapEx, commissioning, depreciation (Capital and FCFF)
    ci = P("capex_int") * o.get("capex_scale", 1.0)
    capex = np.zeros(6); capex[0] = CAPEX_H2
    capex[1:] = ci[1:] * group_demand[1:]
    rate = S("commission"); life = S("hw_life")
    ends = np.cumsum(PERIOD); starts = ends - PERIOD
    cip, ppe = CIP_OPEN, PPE_OPEN
    cohorts = []
    dep = np.zeros(6); comm = np.zeros(6); cip_close = np.zeros(6); avg_insvc = np.zeros(6)
    floor_bind = np.zeros(11, bool)

    def open_dep(s, e):
        return (HW_OPEN / HW_OPEN_LIFE * max(0, min(e, HW_OPEN_LIFE) - max(s, 0))
                + OTH_OPEN / OTH_OPEN_LIFE * max(0, min(e, OTH_OPEN_LIFE) - max(s, 0)))

    def renewal_floor(s, e):
        # Capital and FCFF rows 11 and 78-88: opening-asset D&A plus hardware cohorts reaching expiry
        return open_dep(s, e) + sum(amt for amt, L, st in cohorts if L == life and amt_is_hw(amt, L)
                                    and s < st + L <= e)
    amt_is_hw = lambda amt, L: True        # hardware cohorts are the only ones with life == hw life
    for t in range(6):
        s, e = starts[t], ends[t]
        if t > 0:
            fl = renewal_floor(s, e)
            if fl > capex[t]:
                capex[t] = fl; floor_bind[t] = True
        c = min(cip + capex[t], (cip + 0.5 * capex[t]) * rate * PERIOD[t])
        comm[t] = c
        mid = s + PERIOD[t] / 2
        cohorts.append((c * HW_SHARE, life, mid)); cohorts.append((c * (1 - HW_SHARE), OTH_LIFE, mid))
        d = open_dep(s, e)
        for amt, L, st in cohorts:
            d += amt / L * max(0, min(e, st + L) - max(s, st))
        dep[t] = d
        insvc_open = ppe - cip
        cip = cip + capex[t] - c
        ppe = ppe + capex[t] - d
        cip_close[t] = cip
        avg_insvc[t] = (insvc_open + (ppe - cip)) / 2

    # --- Cloud delivery and revenue (Cloud demand rows 17-28)
    required = group_demand / PERIOD * CAPACITY_REQ * o.get("cap_req_scale", 1.0)
    coverage = np.minimum(1.0, avg_insvc / required)
    sens = o.get("delivery_sensitive", DELIVERY_SENSITIVE)
    deliv = 1 - sens + sens * coverage
    fund_rec = 1 - FUND_EXPOSURE * S("fund_defer")
    remaining, deferred = BACKLOG, 0.0
    cloud = np.zeros(6)
    for t in range(6):
        due = sched[t] + deferred
        rec = min(remaining, due * deliv[t] * fund_rec)
        remaining -= rec
        deferred = max(0.0, due - rec)
        new = (planned[t] - sched[t]) * min(1.0, deliv[t])
        new -= new * FUND_EXPOSURE * S("fund_pressure")
        cloud[t] = rec + new
    revenue = services + cloud + ob_rev

    # --- Services EBIT with TAC mix and AI serving cost (Operating forecast rows 46-58)
    ads = seg["search"] + seg["yt"] + seg["net"]
    tac_rate = P("tac_change") + (seg["net"] / ads - REF_NET_SHARE) * SERV_TAC_DIFF
    tac_cost = tac_rate * ads
    step = (1 - S("ai_unit")) * (1 + S("ai_workload"))
    ai_factor = step ** np.array([0.5, 1.5, 2.5, 3.5, 4.5, 5.5])
    ai_cost = services * AI_EXPOSURE * (ai_factor - 1)
    serv_ebit = services * SERV_MARGIN - tac_cost - ai_cost
    cloud_ebit = cloud * (P("cloud_margin") + o.get("cloud_margin_add", 0.0))
    # Other Bets loss
    oc = P("ob_cost")
    ob_loss = grow(OB_LOSS_FY25 - OB_LOSS_H1_25, OB_LOSS_H1_26, oc) * o.get("ob_loss_scale", 1.0)
    # Alphabet-level costs: research follows planned group revenue with elasticity
    el = S("research_elast")
    research = np.zeros(6)
    research[0] = ALPHA_H1_26 * RESEARCH_SHARE * (1 + S("research_h2"))
    fy = ALPHA_H1_26 * RESEARCH_SHARE + research[0]
    plan_prev = H1_26_REV + group_demand[0]
    for t in range(1, 6):
        fy = fy * (1 + (group_demand[t] / plan_prev - 1) * el)
        research[t] = fy; plan_prev = group_demand[t]
    other_sh = np.zeros(6)
    other_sh[0] = ALPHA_H1_26 * (1 - RESEARCH_SHARE) * (1 + OTHER_SHARED_GROWTH) ** 0.5
    fy = ALPHA_H1_26 * (1 - RESEARCH_SHARE) + other_sh[0]
    for t in range(1, 6):
        fy *= 1 + OTHER_SHARED_GROWTH
        other_sh[t] = fy
    ref_ebit = serv_ebit + cloud_ebit - ob_loss - research - other_sh
    _dbg = dict(serv_ebit=serv_ebit, tac=tac_cost, ai=ai_cost, services=services)
    ebit = ref_ebit + REF_DA_RATIO * revenue - dep - INTANG
    intang_tax_deductible = o.get("intang_tax_deductible", INTANG_TAX_DEDUCTIBLE)
    nopat = ebit - np.maximum(0, ebit + INTANG * (1-intang_tax_deductible)) * tax_ex

    # --- working capital and FCFF
    inv = P("inventory")
    rev_fy = revenue.copy(); rev_fy[0] = H1_26_REV + revenue[0]
    cash_ratio = o.get("operating_cash_ratio", OPERATING_CASH_RATIO)
    required_cash = rev_fy * cash_ratio
    nowc = rev_fy * (NOWC_EX_INV + inv) + required_cash
    d_nowc = np.diff(np.concatenate([[NOWC_OPEN + OPENING_TTM_REVENUE * cash_ratio], nowc]))
    fcff = nopat + dep + INTANG - capex - d_nowc

    # --- transition 2032-2036 and terminal (Transition tab)
    gT = S("term_growth")
    g31 = revenue[5] / revenue[4] - 1
    m31 = ebit[5] / revenue[5]
    excess_cip = cip_close[5] - capex[5] * (1 / HIST_COMMISSION - 0.5)
    dep_rate = HW_SHARE / life + (1 - HW_SHARE) / OTH_LIFE
    m_norm = m31 - excess_cip * dep_rate / revenue[5]        # Transition!B52
    m_norm_pre_am = m_norm + INTANG[5] / revenue[5]
    mT = o.get("term_margin", TERM_MARGIN_OVERRIDE if TERM_MARGIN_OVERRIDE is not None else m_norm_pre_am)
    tax31 = tax_ex[5]
    frac = np.array([0.2, 0.4, 0.6, 0.8, 1.0, 1.0])
    gr = g31 + (gT - g31) * frac
    mr = m_norm_pre_am + (mT - m_norm_pre_am) * frac
    tx = tax31 + (tax_terminal - tax31) * frac
    rev_t = revenue[5] * np.cumprod(1 + gr)
    amort_t = np.asarray(o.get("intang_tail", INTANG_TAIL), float)
    ebit_t = rev_t * mr - amort_t
    nop_t = ebit_t - np.maximum(0, ebit_t + amort_t*(1-intang_tax_deductible)) * tx
    cash_profit_t = nop_t + amort_t
    # Growth investment is linked to pre-amortisation NOPAT; expiry of old acquisition
    # amortisation or its finite tax shield is not growth generated by new investment.
    growth_nop_t = rev_t * mr - np.maximum(0, rev_t * mr) * tx
    reinv31 = capex[5] + d_nowc[5] - dep[5]
    e31n = revenue[5] * m_norm_pre_am
    nopat31_norm = e31n - max(0, e31n) * tax31
    reinv31n = reinv31 - excess_cip * dep_rate               # Transition!B15 - B51
    r0 = (growth_nop_t[0] - nopat31_norm) / reinv31n
    RT = min(r0, o.get("term_return", S("term_return")))
    if not (r0 > 0 and RT > gT and WACC > gT):
        # the sheet returns #N/A when the starting return is not positive; flag the trial
        return dict(ev=np.nan, r0=r0, RT=RT, valid=False)
    rr = r0 + (RT - r0) * frac[:5]
    nops = np.concatenate([[nopat[5]+INTANG[5]], growth_nop_t])
    reinv = (nops[2:7] - nops[1:6]) / rr                    # 2032-2036, growth-implied
    # Capital and FCFF 2032-2036: CapEx solved for the growth-implied net investment, then the
    # renewal floor applies (rows 90-97); a binding floor raises actual net reinvestment.
    nowc_ratio = nowc[5] / revenue[5]
    nowc_prev = nowc[5]
    h92 = 0.5 * (HW_SHARE / life + (1 - HW_SHARE) / OTH_LIFE)
    actual = reinv.copy(); tr_dbg = []
    for k in range(5):
        s = ends[5] + k; e = s + 1.0
        d_nowc_t = rev_t[k] * nowc_ratio - nowc_prev; nowc_prev = rev_t[k] * nowc_ratio
        d_prior = open_dep(s, e) + sum(amt / L * max(0, min(e, st + L) - max(s, st)) for amt, L, st in cohorts)
        d_indep = d_prior + cip * rate * h92
        h94 = 0.5 * rate * h92
        solved = max(0.0, (reinv[k] + d_indep - d_nowc_t) / (1 - h94))
        fl = renewal_floor(s, e)
        cx = max(solved, fl)
        if fl > solved:
            floor_bind[6 + k] = True
        c = min(cip + cx, (cip + 0.5 * cx) * rate)
        cohorts.append((c * HW_SHARE, life, s + 0.5)); cohorts.append((c * (1 - HW_SHARE), OTH_LIFE, s + 0.5))
        d_t = d_indep + h94 * cx
        cip = cip + cx - c
        actual[k] = cx + d_nowc_t - d_t
        tr_dbg.append((round(solved), round(fl), round(d_t), round(cip)))
    fcff_t = cash_profit_t[:5] - actual
    tv = nop_t[5] * (1 - gT / RT) / (WACC - gT)

    shift = 0.5 if mid_year else 0.0
    t_ex = YRS_EX - shift; t_ex[0] = YRS_EX[0] * (0.5 if mid_year else 1.0)
    cf_ex = fcff.copy(); cf_ex[0] *= STUB_FRAC
    pv_ex = (cf_ex / (1 + WACC) ** t_ex).sum()
    t_tr = YRS_TR - shift
    pv_tr = (fcff_t / (1 + WACC) ** t_tr).sum()
    pv_tv = tv / (1 + WACC) ** t_tr[-1]
    ev = pv_ex + pv_tr + pv_tv
    return dict(ev=ev, pv_ex=pv_ex, pv_tr=pv_tr, pv_tv=pv_tv, revenue=revenue, cloud=cloud,
                ebit=ebit, margin=ebit / revenue, nopat=nopat, capex=capex, dep=dep, fcff=fcff,
                coverage=coverage, cip=cip_close, m31=m31, mT=mT, r0=r0, RT=RT,
                operating_wc=nowc, d_operating_wc=d_nowc, required_cash=required_cash,
                transition_amort=amort_t, transition_nopat=nop_t, transition_fcff=fcff_t,
                ob_loss=ob_loss, research=research, ob_rev=ob_rev, m_norm=m_norm, valid=True, dbg=_dbg, floor_bind=floor_bind, tr_dbg=tr_dbg)


SCENARIO_DRIVERS = ["search", "yt", "net", "subs", "cloud_demand", "cloud_margin", "ob_rev", "ob_cost",
                    "capex_int", "tac_change", "inventory", "commission", "hw_life", "research_elast",
                    "ai_unit", "ai_workload", "term_return", "term_growth", "funding"]


def scenario(name, **kwargs):
    zz = {"base": 0.0, "bull": 1.0, "bear": -1.0}[name]
    return value({d: zz for d in SCENARIO_DRIVERS}, **kwargs)


if __name__ == "__main__":
    b = value()
    print("Base EV", round(b["ev"]), "pv_ex", round(b["pv_ex"]), "pv_tr", round(b["pv_tr"]), "pv_tv", round(b["pv_tv"]))
    for k in ["revenue", "cloud", "ebit", "nopat", "capex", "dep", "fcff"]:
        print(k, np.round(b[k]).astype(int))
    print("coverage", np.round(b["coverage"], 4), "m31", round(b["m31"], 4), "mT", round(b["mT"], 4), "r0", round(b["r0"], 4))
    for s in ["bull", "bear"]:
        print(s, round(scenario(s)["ev"]))

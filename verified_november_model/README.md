# Alphabet valuation — verified 6 November 2026 revision

This is the current reproducible model. The earlier October package remains archived.
Valuation cutoff: 25 October 2026, using 23 October closes. This is not a current-price valuation.

## Files

- `alphabet_model.py`: operating forecasts, capital cohorts, transition and DCF.
- `workbook_inputs.py`: inputs from the included recalculated workbook.
- `monte_carlo.py`: 10,000-trial simulation, charts, tornado and reverse DCF.
- `robustness.py`: distribution, correlation and WACC stresses.
- `verify_model.py`: native workbook reconciliation and behavioural checks.
- `data/Business_Valuation.xlsx`: complete formula workbook with saved caches.
- `data/workbook_manifest.json`: source and SHA-256 fingerprint.
- `results/`: verification, simulation, robustness JSON and both charts.

## Setup and reproduce

Use Python 3.12. From this extracted folder, create a virtual environment and install
`requirements-lock.txt` with pip. Then run:

    python verify_model.py
    python monte_carlo.py --trials 10000 --seed 7
    python robustness.py --trials 10000 --seed 7

All outputs go to `results/`. Python recomputes each DCF; Excel/Google login is not
required. The workbook must be recalculated before exporting a changed version.

## November controls and sampling

The model includes Assumptions rows 241–261: capacity-requirement share,
commercial Cloud-margin recovery, front-loaded surplus absorption and Other Bets
loss-margin reduction. Other Bets revenue and capital remain in group totals;
there are no closure proceeds or separately forecast Waymo profits.

Seventeen joint driver positions use symmetric triangular distributions on [-1,1],
with mode 0 and a judgemental Gaussian copula. Positions map piecewise to whole
Bear/Base/Bull paths. Scenario categories have no assigned probabilities.

To retain 17 drivers, capital productivity also maps capacity-requirement share
(100%/50%/100%) and absorption exponent (1/2/1); Cloud margin maps its mature
margin (28%/38%/42%); Other Bets maps its loss-margin removal (50%/100%/100%).
Orders above are Bear/Base/Bull. These joint paths are not necessarily monotonic.
The full scenarios also change inventory; Monte Carlo retains Base inventory.
The financial-capacity benchmark is not engineering evidence of compute capacity.

## Verified results (operating EV, USD trillion)

| Bear | Base | Bull | P10 | Median | P90 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.864 | 2.611 | 4.567 | 2.091 | 2.470 | 2.875 |

Mean EV is 2.476tn. At a fixed Base financial-assets/claims bridge, mean equity
is 2.642tn. Main-run maximum EV is 3.711tn against market-implied 3.750tn;
zero of 10,000 trials reaches it. This is not proof of zero real-world probability.
Uniform positions produce 9 exceedances; WACC ±1pp produces 8 and ±2pp 196.
All runs have 10,000 valid trials. The favourable coordinate search reaches
4.628tn; it is not a proof of a global maximum.

All three native scenario EVs and all 25 sensitivity cells reconcile within 0.01%.
Reverse DCF's reported margin includes the separate recovery uplifts; its raw
workbook margin override is an intermediate input. SOTP is retained in the workbook
and is not recomputed in each trial. The Base equity bridge is held fixed in the
simulation. Deterministic scenarios use their respective equity bridges: Bear
1.009tn, Base 2.777tn and Bull 4.741tn. These bridges are not scenario probabilities.

## Capital definition and comparability

Operating capital includes net PP&E, recognised net operating intangibles and
adjusted operating working capital (including required cash of 2% of revenue).
Goodwill remains excluded: the ratio measures operating efficiency, not total
acquisition returns. Research is expensed and operating leases retain their
existing expense treatment, so this is not a comprehensive economic ROIC.

June 2026 net intangibles are USD 9,105m. Existing finite-lived assets run off
through the amortisation schedule; USD 211m of indefinite-lived assets remains
in terminal capital. Amortisation is already reflected in EBIT and added back
in FCFF. Including the asset in the return denominator does not add acquisition
spending or asset value a second time.

December 2024 and June 2025 net intangibles use USD 1,283m each as a labelled
analyst proxy from the disclosed December 2025 balance. The opening amounts
were not separately disclosed in the checked filings. Doubling or removing
the proxy gives FY2025 returns of 44.0–44.3% and TTM June 2026 returns of
39.4–39.5%; the central values are 44.2% and 39.4%. See Historical base and
Sources and basis for the reconciliation. Forecast 2036 return is 27.1%;
terminal new-capital return is 26.9%, a separate modelling assumption.

The workbook's relative valuation uses CY2027 analyst EBIT forecasts, rather
than consensus estimates or trailing multiples. Shared D&A is allocated and
reconciled to the DCF. Forward SOTP equity is USD 2.90–3.56tn (central 3.23tn).
Peer accounting and business mixes remain imperfectly comparable.

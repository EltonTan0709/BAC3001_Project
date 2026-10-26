# BAC3001 â€” Alphabet Valuation and Monte Carlo Simulation

Reproducible Python implementation of Group 9's Alphabet operating DCF, backed by
the included valuation workbook. The valuation date and information cutoff are
**25 October 2026**, using **23 October 2026 market closes** (the preceding Friday).
The workbook snapshot was exported on **26 October 2026**; it is a frozen project version, not a
live market-data feed. The written report is excluded from this repository.

## Repository structure

```text
BAC3001_Project/
â”œâ”€â”€ README.md
â”œâ”€â”€ requirements.txt                # Tested Python dependencies
â”œâ”€â”€ requirements-lock.txt           # Exact direct and transitive package versions
â”œâ”€â”€ alphabet_model.py               # Segment forecast, capital schedule and DCF engine
â”œâ”€â”€ workbook_inputs.py              # XLSX input mappings and layout checks
â”œâ”€â”€ monte_carlo.py                  # 17-driver simulation, charts and reverse DCF
â”œâ”€â”€ robustness.py                   # Distribution, correlation and WACC checks
â”œâ”€â”€ verify_model.py                 # Python-to-workbook reconciliation
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ Business_Valuation.xlsx      # Complete formula workbook with cached values
â”‚   â””â”€â”€ workbook_manifest.json      # Source, export date and SHA-256 fingerprint
â””â”€â”€ results/
    â”œâ”€â”€ verification.json
    â”œâ”€â”€ monte_carlo_results.json
    â”œâ”€â”€ robustness_results.json
    â”œâ”€â”€ mc_histogram.png
    â””â”€â”€ mc_tornado.png
```

Installed package directories, virtual environments, local audit files and other
coursework are excluded through `.gitignore`. Dependencies are installed with pip.

## Set up

Use **Python 3.12** and Git. Python 3.11 is insufficient for the pinned NumPy version.
The commands below run from the repository root. Excel, a Google login and API keys
are not required to reproduce the included snapshot.

### Windows PowerShell

```powershell
git clone https://github.com/EltonTan0709/BAC3001_Project.git
cd BAC3001_Project
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe verify_model.py
.\.venv\Scripts\python.exe monte_carlo.py --trials 10000 --seed 7
.\.venv\Scripts\python.exe robustness.py --trials 10000 --seed 7
```

Using the virtual environment's Python directly avoids PowerShell activation-policy
issues. `requirements.txt` pins the three direct dependencies; `requirements-lock.txt`
also fixes their dependencies to the versions used for the committed results.

### macOS / Linux

```bash
git clone https://github.com/EltonTan0709/BAC3001_Project.git
cd BAC3001_Project
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python verify_model.py
.venv/bin/python monte_carlo.py --trials 10000 --seed 7
.venv/bin/python robustness.py --trials 10000 --seed 7
```

All outputs are written to `results/`. Use `--output-dir another_folder` to retain a
separate run. To inspect only the deterministic DCF, run `python alphabet_model.py`
using the same environment. Charts render without an interactive display.

## How the workbook and Python fit together

`data/Business_Valuation.xlsx` contains the model's inputs, formula calculations,
sources, sensitivity grid and relative-valuation cross-check. The main tabs are:

| Workbook tabs | Role in Python |
| --- | --- |
| Historical base | Opening revenue, earnings, working capital and PP&E |
| Assumptions | Bear/Base/Bull paths, tax, backlog timing, capacity and asset lives |
| Working capital | Receivables and operating assets less operating liabilities; required cash included |
| Capital and FCFF | Period lengths and acquired-intangible amortisation schedule; cash flows recomputed in Python |
| Cloud demand | Opening backlog; demand and delivery recomputed in Python |
| Financial assets / Valuation | Operating-cash reserve, valuation date, WACC and equity bridge |
| Simulation inputs | Latent correlations, range rationale and scenario comparison snapshots |
| Relative valuation | Multiples-based SOTP cross-check; retained in Excel, not recomputed by the simulation |

`workbook_inputs.py` reads the workbook's **saved numeric values**, including cached
formula results. Python then recomputes segment earnings, Cloud delivery, cohort
depreciation, operating working capital, FCFF, transition reinvestment and terminal
value for every trial. It does not execute Excel or Google Sheets formulas.

The explicit forecast covers **H2 2026 and FY2027â€“2031**, followed by a **2032â€“2036
transition** and terminal cash flow from **2037**. FCFF is NOPAT plus PP&E depreciation
and acquired-intangible amortisation, less cash CapEx and the increase in operating
working capital, including required operating cash. Model figures are in **USD
millions**; charts display USD trillions. There is no per-share target.

Base WACC is approximately **9.3831%**. The simulation holds the Base equity bridge
fixed; financing stress affects Cloud delivery rather than assigning a separate
random value to the investment portfolio. Minority interests remain a book-value
proxy. These are project assumptions, documented in the workbook.

## Reproduce and check the results

Run `verify_model.py` first. It compares Base EV, CapEx, depreciation, NOPAT,
working-capital investment, FCFF and present values with workbook caches. It also
compares the three full scenarios with the workbook's scenario snapshots. A failed
check exits with an error instead of silently accepting a different model.

Rounded reference values for the included workbook are:

| Output | Operating EV (USD tn) |
| --- | ---: |
| Full Bear scenario | 0.837 |
| Base | 2.496 |
| Full Bull scenario | 4.450 |
| Monte Carlo P10 | 1.994 |
| Monte Carlo median | 2.361 |
| Monte Carlo P90 | 2.759 |
| Market-implied operating EV | 3.750 |

The Python engine and live workbook reconcile within USD 0.001m for all three
scenario EVs. The included snapshot is exported with Base selected.

`monte_carlo.py` writes:

- `monte_carlo_results.json`: percentiles, valid/invalid trial counts, conditional
  exceedance frequency, deterministic cases, tornado inputs and reverse-DCF results.
- `mc_histogram.png`: simulated operating EV against market-implied operating EV.
- `mc_tornado.png`: changing one driver to its Bear or Bull anchor while others stay Base.

The favourable-combination search is a coordinate search within the 17 sampled
driver ranges, not a proof of a global optimum. Inventory follows Base in the
simulation; the full Bear/Bull scenarios also change inventory. Reverse-DCF entries
of `null` mean no solution was bracketed within that lever's specified search range.

## Post-build revision (26 October 2026)

The detailed 2026–2031 forecast is unchanged. From 2032, required productive assets
fade from actual 2031 net in-service PP&E to the existing demand-capacity benchmark.
The benchmark is converted from average to closing assets, then multiplied by
110% / 100% / 90% in Bear / Base / Bull. These are judgemental efficiency scenarios,
not measured physical utilisation. The 17-driver structure is retained: capital
intensity replaces the old terminal-return ceiling as a sampled driver.

Commissioning fills the gap between required assets and the existing assets after
cohort depreciation. Purchases consume opening CIP first, subject to delivery timing
and a normal construction pipeline. The model no longer applies a permanent excess-CIP
EBIT deduction or mechanically replaces every expiring asset after 2031. It assumes
CIP can support future demand; completion costs and hardware incompatibility are not
separately estimated. Longer hardware lives reduce the resulting replacement need.

Base CapEx falls from USD 210.1bn in 2031 to USD 185.8bn in 2036; parent tangible
returns recover from 22.0% to 23.0%. Bear cuts 2032 purchases to USD 50.9bn and reduces
CIP from USD 390.1bn to USD 247.9bn by 2036, with returns reaching 12.4%. Bull returns
reach 32.0%. These are average-capital returns, not project IRRs.

Terminal new-project returns use 2036 pre-amortisation NOPAT divided by closing
tangible capital, with WACC as an approval hurdle. This mature-productivity assumption
does not uplift earnings on sunk assets and does not repeat a temporary CIP drawdown
forever. Bear terminal growth is 1.5%; Base and Bull retain 3% and 3.5%.

The formula-based sensitivity tab rebuilds the capital schedule at each growth rate.
Verification covers all 25 cells, the three scenarios, asset balances, slower delivery
reducing value, and longer hardware lives reducing replacement spending.

## Simulation interpretation

Each of 17 drivers receives one position `z` between **âˆ’1 (Bear)**, **0 (Base)** and
**+1 (Bull)**. Symmetric triangular positions favour the central judgement. A
Gaussian copula applies the ten assumed latent correlations from `Simulation inputs`.
One position applies to a driver's whole forecast path, rather than redrawing an
independent shock each year. Some scenario paths are asymmetric or non-monotonic,
so the resulting financial inputs need not themselves have triangular distributions.

No 25%/50%/25% or other probabilities are assigned to complete Bear/Base/Bull cases.
P10/P50/P90 describe simulated outputs. The reported exceedance frequency is the
number of qualifying **valid** trials divided by all valid trials; it is conditional
on the assumptions, not an estimated real-world probability. Invalid trials are
counted separately. Guardrails require terminal return and WACC above terminal growth. A weak
one-year incremental return is a diagnostic, not a permanent ceiling on new projects.

`robustness.py` reruns the model with uniform positions, independent drivers,
stronger latent correlations and independent triangular WACC stresses of Â±1 and
Â±2 percentage points. Distribution comparisons share latent draws and the copula;
the WACC tests use a separate 18-column random stream, so their 17 operating draws
differ from the main run. The default is 10,000 trials with seed 7. The uniform
P10â€“P90 range is approximately USD 1.43â€“2.56tn. Full results are committed in JSON.

The October refresh uses the latest available Alphabet June results; it does not
invent September actuals. The bridge estimates elapsed H2 cash flow, dividends and
disclosed subsequent financing. SpaceX holdings are marked using the quoted price
change under an unchanged-share-count assumption. Other debt, investment tax bases
and minority claims retain the explicitly labelled proxies in the workbook.
Meta's September and Oracle's August filings update the peer cross-check. Meta's
one-off settlement cost is removed from benchmark earnings and its unpaid claim
is included in EV. These approximations remain part of the investment judgement.

No main-run trial exceeds the refreshed market EV, but the full Bull scenario does.
Full Bull deliberately combines its scenario anchors, whereas triangular sampling
favours Base and rarely produces comparably favourable joint combinations. The
highest of the 10,000 main-run trials is USD 3.63tn, versus USD 4.45tn for full Bull.
The independent Â±2-point WACC stress produces 104 exceedances in 10,000 valid trials
(1.04%). A zero sample exceedance is not evidence that upside is impossible.

## Update inputs

1. Edit assumptions in the workbook's existing layout. Recalculate in Excel or
   Google Sheets and save/export as `.xlsx`, with **Base selected**.
2. Replace `data/Business_Valuation.xlsx`, or point a run at another export:

   ```powershell
   .\.venv\Scripts\python.exe verify_model.py --workbook "path\to\recalculated.xlsx"
   .\.venv\Scripts\python.exe monte_carlo.py --workbook "path\to\recalculated.xlsx"
   ```

3. Update the deterministic snapshots in `Simulation inputs` when intentionally
   changing scenario assumptions; then rerun verification and both simulations.
4. Record the new source/export date and SHA-256 in `data/workbook_manifest.json`
   before committing updated outputs. Each output JSON records the workbook hash.

For Python imports, `BAC3001_WORKBOOK` can select a different workbook before import.
The scripts intentionally target this workbook layout and horizon. If tabs, row
locations, scenario relationships or the horizon change, update the cell mappings
and Python logic, then verify again. Several inputs shared by all cases are checked
for equality; they cannot silently become additional scenario drivers.

**Missing numeric caches:** open and recalculate the workbook in Excel or Google
Sheets, then save/export again. Saving a formula-edited file using `openpyxl` alone
does not calculate formulas and can remove caches. The Python loader leaves the
workbook unchanged.

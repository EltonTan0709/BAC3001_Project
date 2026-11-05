# BAC3001 - Alphabet valuation (Group 9)

Current model: [verified_november_model](verified_november_model/), aligned on 6 November 2026. The valuation remains frozen at 25 October 2026, using 23 October market prices; it is not a current-price recommendation.

## Repository structure

- [Model and setup instructions](verified_november_model/README.md): Python DCF, Monte Carlo and verification commands.
- [Formula workbook](verified_november_model/data/Business_Valuation.xlsx): included locally; no Google account is needed to run the code.
- [Results](verified_november_model/results/): simulation statistics, robustness checks, reconciliation and charts.
- [October archive](archive_2026-10-26/): superseded version retained for reference.

## Quick start

With Python 3.12 installed, run from the repository root:

```sh
cd verified_november_model
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux instead: source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python verify_model.py
python monte_carlo.py --trials 10000 --seed 7
python robustness.py --trials 10000 --seed 7
```

The report is maintained separately and is not included in this repository.

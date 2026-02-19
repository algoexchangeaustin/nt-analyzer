# NT Analyzer JS Dashboard Clone

This folder contains a JavaScript/HTML/CSS clone of your current public dashboard style, adapted for the `nt-analyzer` repo.

## Run locally

From `dashboard-js`:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## Backtest CSV files wired

These files are now wired in `dashboard-js/reports/`:

- `mil_150k_prop.csv` -> **Millennium Algo ($10K)**
- `falcon_10k.csv` -> **Falcon Algo ($10K)**
- `raptor_10k.csv` -> **Raptor Algo ($10K)**

## Expected backtest columns (current template)

The NT parser now reads standard NinjaTrader export columns, including:

- `Profit`
- `Entry price`
- `Entry time` / `Exit time`
- `Market pos.`
- `Qty`
- `Instrument`

If you later want Monte Carlo sources in this NT dashboard, we can wire those files next (`nt_mc_stats.csv`, `nt_mc_trade_paths.csv`, `nt_mc_equity_percentiles.csv`).

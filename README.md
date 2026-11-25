# Atlas Momentum

An intraday momentum strategy for Nasdaq-100 E-mini (NQ) futures, designed to pass prop-firm funding evaluations such as APEX Trader Funding and FTMO, with Interactive Brokers for data and paper trading.

## The strategy

- **Signals:** 8 and 21-period EMA crossover, 14-period RSI and 20-period Bollinger Bands, with ATR for volatility.
- **Market regime filter:** separates trending from ranging conditions and only trades strong signals.
- **Risk:** 1% base position (up to 2.5%), 1.2% stop loss, 2.5% take profit, at most 12 trades a day and an 8% maximum drawdown.

The full parameters and the simulation results are in [ATLAS_FINAL_SUMMARY.md](ATLAS_FINAL_SUMMARY.md). All results come from backtests and simulated evaluations, not live trading.

## What's in the repo

| File | What it is |
| --- | --- |
| `ATLAS_FINAL_SUMMARY.md` | Strategy design, parameters and simulation results |
| `atlas_requirements.txt` | Python packages (backtrader, ibapi, pandas, TA-Lib and others) |
| `atlas_final.py`, `atlas_simple_ib.py` | Placeholders for the final strategy and the Interactive Brokers bot |

The research code (data feeds, backtests, FTMO and APEX simulations, risk management and the IB integration) is in the repository's first commit, [`b56075e`](../../tree/b56075e).

## Run it

```bash
pip install -r atlas_requirements.txt
```

TA-Lib needs its C library installed first. See the [TA-Lib install notes](https://ta-lib.github.io/ta-lib-python/install.html).

## Licence

MIT. See [LICENSE](LICENSE). This is a research project, not investment advice.

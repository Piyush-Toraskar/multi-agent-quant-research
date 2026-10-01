# Quantitative methodology

## Data

The model is daily and close-to-close. Live input is the provider's adjusted Close;
the project does not independently reconstruct corporate actions. Adjustments can change retrospectively,
which is why the source, retrieval timestamp, exact price snapshot and its hash are retained.
The selected universe is fixed, not a point-in-time reconstruction of an index. Survivorship and
selection bias remain possible. All symbols must have a common currency and comparable session.

No missing observations are filled. The downloader takes the intersection of available dates and
reports the number removed. Dates must be unique and increasing; prices must be finite and positive.
Historical missing/de-listed coverage is not manufactured. More than 20 calendar years or 8 assets
per request is rejected. At least 80 common observations and 60 post-warm-up observations are required.

## Signals and portfolio construction

- Momentum: `adjusted_close[t] / adjusted_close[t-lookback] - 1 > 0`.
- SMA crossover: the fast rolling mean exceeds the slow rolling mean, after full warm-up.
- Buy-and-hold: equal allocation across the chosen assets, a single initial entry, no later rebalance.

For momentum/SMA, each active asset receives `1/N` of the total portfolio, where N is the original
asset count. Unused allocations stay in cash; they are not reallocated to active assets. No shorting
or leverage is allowed. Between trades, risky weights drift with market prices.

Monthly/weekly decisions occur on the first observed session in a new calendar period, plus the first
eligible post-warm-up session. These decisions do not require observing the future final date of a period.
Daily mode decides every eligible day. A decision uses only data through that day's close.

## Execution chronology

For the normal delay of one:

```text
close t:     Observe adjusted closing prices and decide target weights.
close t+1:   Old positions earn the t -> t+1 return. Rebalance at this close and pay costs.
close t+2:   New positions first earn an asset return, for t+1 -> t+2.
```

The program does not pretend a strategy can both observe and trade at the same closing price.
The benchmark enters on the same first eligible execution date, pays the same cost rule and then
holds. Metrics begin from the pre-entry cash baseline and include the entry fee. Warm-up is excluded
from the performance comparison. There is no end-of-backtest forced liquidation or exit charge;
terminal positions are marked to market and this is stated in every report.

## Self-financing trading costs

Let `V` be NAV just before the rebalance, `w` the drifted risky weights, `q` the desired post-cost
risky weights and `c = (commission_bps + slippage_bps) / 10000`.
The fee fraction `f` solves:

```text
f = c * sum(abs(q * (1 - f) - w))
post_cost_NAV = V * (1 - f)
traded_notional_i = V * (q_i * (1 - f) - w_i)
```

A bounded fixed-point calculation solves this with a tight tolerance. Thus target positions are
funded from post-cost NAV, and fees are not accidentally invested as well. A 100% entry with a 1%
fee leaves `initial_capital / 1.01` invested. Tests reconcile the trade-fee ledger to the equity curve.
Turnover is the sum of absolute risky-asset traded notional divided by pre-rebalance NAV; it is
reported as a full-period sum, not an annualised half-turnover statistic.

Fractional units and linear costs are assumed. There is no market impact, capacity, spread/volume
model, short borrow, tax, contract multiplier, order rejection or intraday fill simulation.

## Metrics

For net daily portfolio returns r:

```text
Total return = product(1 + r) - 1
CAGR = final_growth ** (365.25 / elapsed_calendar_days) - 1
Annualised volatility = sample_std(r, ddof=1) * sqrt(252)
daily_rf = (1 + annual_rf) ** (1/252) - 1
Sharpe = mean(r - daily_rf) / sample_std(r, ddof=1) * sqrt(252)
Sortino = mean(r - daily_rf) / sqrt(mean(min(r-daily_rf, 0)**2)) * sqrt(252)
Drawdown = equity / running_max(equity) - 1
Max drawdown = minimum drawdown (zero or negative)
Beta = sample_cov(strategy, benchmark) / sample_var(benchmark)
```

The drawdown includes the initial baseline, so a loss on the first day is not lost from the calculation.
Zero denominators yield `null` / N/A rather than invented infinities. Cash earns zero regardless of
the risk-free hurdle. This choice is explicit, not a cash interest model.

Historical 95% one-day VaR is `max(0, -quantile(r, 0.05))`. Historical CVaR is the non-negative loss
associated with the mean of observations at/below that quantile. Both are loss magnitudes, not
probability forecasts. An all-risky-assets-minus-20% scenario is labelled illustrative.

Asset-level descriptive performance uses the entire data snapshot. Strategy/benchmark metrics use
its eligible execution window. Holdout rows use the later holdout period. These different horizons
are labelled; they should not be read as identical-sample comparisons.

## Chronological holdout, not spurious optimisation

The first 70% of eligible return observations is the development portion and the last 30% is the
holdout by default. The fraction is configurable. Parameters are fixed in the request: no fitting,
search, strategy selection by realised return or optimisation occurs. Positions continue across the
split, with previous observations available for lookback, and no artificial liquidation at the split.

The later period is useful for a fixed-parameter temporal comparison, but is not necessarily an
untouched final test once a user inspects it repeatedly. No p-values, predictive significance tests,
multiple-testing adjustments or claim of a persistent edge are produced.

## Critic checks

The critic verifies snapshot linkage, delayed execution, signal-before-trade chronology, non-negative
costs, positive NAV, long-only/unlevered weights and holdout size. It also perturbs all future prices
from a chosen split and verifies that earlier equity values remain unchanged.

A causality failure can route back once to a stricter execution delay; every attempt is logged.
Other unresolved failures produce a REJECTED report. A language-model summary cannot override the
verdict. The test is a useful software invariant, not proof against survivorship bias, provider revisions,
user parameter selection or every possible form of look-ahead.

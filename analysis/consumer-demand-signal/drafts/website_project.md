## Context
Weak consumer confidence does not automatically translate into weak demand. The real challenge for consumer teams is knowing **which categories are still structurally resilient** and **which pockets of demand look strong only because the benchmark is misleading**.

## Question
Where is U.S. consumer demand still holding up in 2026, and how does the answer change when I look at both category-level sales and income-segment spending behavior?

## Data Sources
- [Opportunity Insights Economic Tracker monthly consumer spending data](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/Affinity%20-%20National%20-%20Monthly.csv)
- [Opportunity Insights data documentation](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/docs/oi_tracker_data_documentation.md)
- [Opportunity Insights Jan 2020 income shares](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/Affinity%20Income%20Shares%20-%20National%20-%202020.csv)
- [FRED: University of Michigan Consumer Sentiment](https://fred.stlouisfed.org/series/UMCSENT)
- [FRED: Consumer Price Index](https://fred.stlouisfed.org/series/CPIAUCSL)
- [FRED: E-commerce retail sales](https://fred.stlouisfed.org/series/MRTSSM4541USN)
- [FRED: Food services and drinking places](https://fred.stlouisfed.org/series/MRTSSM7225USN)
- [FRED: Clothing stores](https://fred.stlouisfed.org/series/MRTSSM4481USN)
- [FRED: Furniture stores](https://fred.stlouisfed.org/series/MRTSSM442USN)
- [FRED: Grocery stores](https://fred.stlouisfed.org/series/MRTSSM44511USN)
- [FRED: General merchandise stores](https://fred.stlouisfed.org/series/MRTSSM452USN)

## What I Built
- A refreshed data pull that combines public consumer card-spend, retail-sales, inflation, and sentiment series
- A real-sales index for six retail categories, normalized to a 2019 baseline
- An income-segment view of spending change by category using Opportunity Insights' monthly Affinity cut
- A simple share model to separate **relative growth** from **absolute dollar concentration**

![Real retail demand by category](/uploads/retail-real-index.svg)

![Latest income-segment spend snapshot](/uploads/income-heatmap-latest.svg)

## Key Findings
- **E-commerce remained the strongest structural winner.** In February 2026, real e-commerce sales were +59.2% versus the 2019 average and gained +9.73 percentage points of share inside the tracked retail basket.
- **Experiences stayed healthier than big-ticket goods.** Restaurants were still +15.8% above the 2019 baseline, while furniture was -20.7% below it.
- **Low-income ZIP codes showed stronger relative growth than high-income ZIP codes.** In Opportunity Insights' March 2026 monthly release, total spending was up 48.3% for Q1 ZIP codes versus 28.6% for Q4 ZIP codes relative to the January 2020 baseline.
- **High-income households still mattered most in dollar terms.** Q4 ZIP codes represented 37.0% of baseline card spend and an estimated 34.8% in the latest month even after the slower relative growth.
- **General merchandise had the widest persistent income gap.** Since 2024, low-income ZIP codes have consistently outpaced high-income ZIP codes the most in general merchandise, which is a useful signal for value positioning and mass-channel planning.

## Why It Matters
This is the kind of work I want to keep doing: connecting external demand signals to concrete business questions around category risk, customer mix, channel strategy, and message prioritization. The project is especially relevant to consumer analytics, customer insights, business intelligence, and commercial strategy roles because it shows how I move from public data to decisions, not just charts.

![Estimated income share shift](/uploads/income-share-slope.svg)

## Output Assets
- `analysis/consumer-demand-signal/artifacts/retail-real-index.svg`
- `analysis/consumer-demand-signal/artifacts/income-heatmap-latest.svg`
- `analysis/consumer-demand-signal/artifacts/income-share-slope.svg`
- `analysis/consumer-demand-signal/data/processed/consumer_demand_summary.json`

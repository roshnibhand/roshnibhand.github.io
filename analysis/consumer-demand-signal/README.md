# Consumer Demand Signal

This folder contains a portfolio-ready consumer analytics project built from live public web data.

## What it does

- pulls monthly national consumer spending data from Opportunity Insights
- pulls retail sales, CPI, and consumer sentiment series from FRED
- creates processed CSV outputs for reuse
- generates SVG charts and a draft preview page
- writes website-ready draft copy for a project page and companion article

## Run

```bash
python3 /Users/roshnibhandula/rosh-website/analysis/consumer-demand-signal/analyze_consumer_demand.py
```

## Main outputs

- `data/processed/consumer_demand_summary.json`
- `data/processed/fred_real_retail_index.csv`
- `data/processed/oi_income_category_growth.csv`
- `data/processed/estimated_income_share_shift.csv`
- `artifacts/consumer-demand-signal-cover.svg`
- `artifacts/retail-real-index.svg`
- `artifacts/income-heatmap-latest.svg`
- `artifacts/income-share-slope.svg`
- `artifacts/portfolio-preview.html`
- `drafts/website_project.md`
- `drafts/website_article.md`
- `drafts/website_metadata.json`

## Publishing status

These files are draft assets only. They are not wired into the published website yet.

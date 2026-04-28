# Pharma Project Framework

## Recommended Project
**Pharma Supply Stress Map: Which drugs combine shortage pressure, high patient exposure, and rising spend?**

This is the pharma project I would recommend building next for your website because it has the same strengths as the consumer analytics case study:

- it uses public official data rather than a synthetic toy dataset
- it answers a business-facing question rather than only a technical one
- it creates room for scoring, segmentation, trend analysis, and prioritization
- it is relevant to healthcare analytics, BI, operations, market access, and commercial strategy roles

## Website Positioning
This should be framed as a **pharma / healthcare analytics case study** rather than a clinical or medical project.

The core positioning is:

> I used official FDA and CMS data to identify where drug shortages matter most, not only in supply terms, but in terms of patient exposure, spending concentration, and operational risk.

That framing is strong for your website because it shows:

- external data discovery
- entity matching across messy public sources
- KPI design
- risk scoring
- business storytelling

## Core Business Question
If a drug is in shortage, how do we know whether it is a small operational issue or a high-priority market signal?

This project should answer:

1. Which currently-shortage drugs affect the most Medicare beneficiaries?
2. Which shortage-exposed drugs carry the highest Part D spending?
3. Which therapeutic areas appear most exposed to shortage pressure?
4. Where are shortages concentrated among a small number of manufacturers?
5. Which drugs look most important when I combine shortage status, beneficiary exposure, and spend growth into one ranking?

## Why This Is a Good Analytics Project
Many public pharma analyses stop at listing shortages or ranking drug spend. That is not enough.

This project becomes stronger because it combines:

- **supply stress** from FDA shortage data
- **patient exposure** from CMS Medicare Part D utilization data
- **manufacturer and product structure** from openFDA NDC data

That creates a much better prioritization framework than any one source alone.

## Official Open Data Sources
These are the sources I recommend using.

### 1. FDA / openFDA Drug Shortages
Use the openFDA Drug Shortages API as the shortage backbone.

- Overview: [openFDA Drug Shortages](https://open.fda.gov/apis/drug/drugshortages/)
- Endpoint documentation: [How to use the Drug Shortages endpoint](https://open.fda.gov/apis/drug/drugshortages/how-to-use-the-endpoint/)
- Base API endpoint: `https://api.fda.gov/drug/shortages.json`

Why it matters:

- daily-updated
- current and historical shortage records
- shortage reasons, status, dates, dosage form, and harmonized fields

Important notes from the source:

- the API covers data from `2012` onward
- updates are `daily`
- openFDA adds harmonized fields to make cross-dataset matching easier

### 2. CMS Drug Spending
Use CMS Medicare Part D Spending by Drug for exposure and financial scale.

- CMS landing page: [CMS Drug Spending](https://www.cms.gov/data-research/statistics-trends-and-reports/cms-drug-spending)
- CMS data dictionary: [Medicare Part D Spending by Drug Data Dictionary](https://data.cms.gov/sites/default/files/2024-03/Medicare%20Part%20D%20Spending%20by%20Drug%20Data%20Dictionary%2020240214_508.pdf)
- CMS methodology: [Medicare Part D Spending by Drug Methodology](https://data.cms.gov/sites/default/files/2023-02/DSD_PTD_R22_20230118_Methodology_WDDSE%20508.pdf)

Why it matters:

- includes total spending, dosage units, claims, and beneficiaries
- includes brand name, generic name, manufacturer, and manufacturer count
- includes multi-year trend metrics such as spending-per-unit change and CAGR

Important notes from the source:

- Part D data reflects drugs generally self-administered by patients
- it covers a subset of Medicare beneficiaries enrolled in Part D
- spending does **not** reflect manufacturer rebates or other confidential price concessions
- drugs with fewer than 11 claims in the most recent year are excluded or redacted

### 3. openFDA NDC Directory
Use openFDA NDC data for product-level enrichment.

- Overview: [openFDA Drug NDC Directory](https://open.fda.gov/apis/drug/ndc/)
- Endpoint documentation: [How to use the NDC endpoint](https://open.fda.gov/apis/drug/ndc/how-to-use-the-endpoint/)
- Base API endpoint: `https://api.fda.gov/drug/ndc.json`

Why it matters:

- manufacturer name
- route
- dosage form
- product identifiers
- pharmacologic class fields

This helps bridge the gap between the shortage records and the CMS spending data.

### Optional 4. openFDA Drug Labeling
Only use this if you want a richer article narrative or therapeutic framing.

- Overview: [openFDA Drug Labeling](https://open.fda.gov/apis/drug/label/)
- Endpoint documentation: [How to use the Label endpoint](https://open.fda.gov/apis/drug/label/how-to-use-the-endpoint/)

Why it matters:

- indications
- warnings
- adverse reactions
- richer product context

This is optional because it increases complexity. I would not use it in phase 1 unless we need stronger explanatory copy for the article.

## Recommended Project Structure
I would organize the project into five layers.

### Layer 1. Raw ingestion
Pull the official source files / API responses into a local project workspace.

Suggested folders:

- `data/raw/openfda_shortages/`
- `data/raw/cms_part_d/`
- `data/raw/openfda_ndc/`
- `data/processed/`
- `artifacts/`
- `drafts/`

### Layer 2. Canonical drug table
Create one cleaned master table that tries to align:

- brand name
- generic name
- manufacturer
- dosage form
- route
- normalized product key

This is one of the most important parts of the project because public pharma datasets rarely line up perfectly.

### Layer 3. Shortage exposure table
Create a table at the drug level with:

- shortage status
- shortage start date
- shortage duration in days
- shortage reason category
- current vs resolved flag
- number of manufacturers
- Part D total beneficiaries
- Part D total claims
- Part D total spending
- average spending per beneficiary
- average spending per dosage unit
- spending CAGR or latest year-over-year change

### Layer 4. Risk scoring layer
Build a shortage-exposure score that combines:

- shortage severity
- patient exposure
- spending concentration
- manufacturer concentration
- spend growth

### Layer 5. Storytelling outputs
Turn the score and supporting tables into website-ready visuals and a long-form article.

## Matching Logic
This project will be strongest if the matching logic is explained clearly, because that is where a lot of the real analytics work lives.

Recommended matching sequence:

1. Normalize text for brand, generic, and manufacturer names.
2. Match shortage records to NDC entries using harmonized openFDA fields where possible.
3. Create drug-level keys using combinations of:
   - generic name
   - brand name
   - manufacturer
   - dosage form
4. Link CMS Part D records primarily through brand/generic/manufacturer logic.
5. Flag low-confidence matches instead of forcing questionable joins.

This is good material for the article because it shows thoughtful data engineering rather than pretending public datasets match cleanly out of the box.

## KPI Framework
I would recommend the following KPI groups.

### Supply KPIs
- number of drugs currently in shortage
- average shortage duration
- shortage count by reason
- shortage count by dosage form
- shortage count by therapeutic class

### Exposure KPIs
- total beneficiaries exposed to currently-shortage drugs
- total claims linked to currently-shortage drugs
- total Part D spending linked to currently-shortage drugs
- average spending per beneficiary for shortage-linked drugs

### Concentration KPIs
- manufacturer count per shortage-linked drug
- share of shortage-linked spend concentrated in single-manufacturer drugs
- share of shortage-linked beneficiaries concentrated in top 10 drugs

### Trend KPIs
- spending CAGR for shortage-linked drugs
- average spending-per-unit trend for shortage-linked drugs
- change in shortage-linked exposure year over year

## Recommended Risk Score
This does not need to be clinically perfect. It needs to be analytically clear and defensible.

Suggested scoring model:

`Shortage Exposure Score = (shortage status weight * duration weight) + beneficiary exposure weight + spending weight + manufacturer concentration weight + spend growth weight`

Example components:

- current shortage gets higher weight than resolved shortage
- longer shortages get higher weight than newer ones
- drugs with more beneficiaries get higher weight
- drugs with higher total spending get higher weight
- single-manufacturer or low-manufacturer drugs get higher weight
- rapidly rising spend per unit can add additional pressure weight

The exact formula can be tuned later, but the website project should emphasize the logic more than pretending the score is the only truth.

## Best Visuals For The Website
These are the visuals I would recommend building.

### 1. Shortage Exposure Scorecard
A ranked table or bar chart of the top 15 drugs with the highest shortage exposure score.

Why it works:

- easy to scan
- decision-oriented
- interview-friendly

### 2. Therapeutic Area Heatmap
A heatmap showing:

- therapeutic class
- shortage count
- total beneficiaries
- total spend

Why it works:

- makes the exposure story feel more strategic
- good for category-level discussion

### 3. Manufacturer Concentration View
A scatter or quadrant chart showing:

- x-axis: number of manufacturers
- y-axis: total spending or beneficiaries
- point size: shortage duration

Why it works:

- visually surfaces where concentration risk overlaps with scale

### 4. Spend vs Exposure Bubble Chart
Plot drugs by:

- x-axis: total beneficiaries
- y-axis: total spending
- color: current shortage vs resolved
- size: spend growth or duration

Why it works:

- turns the project into a clear prioritization map

### 5. Reason-for-Shortage Breakdown
A clean categorical chart for:

- manufacturing issues
- increased demand
- discontinuation
- shipping delays
- other

Why it works:

- makes the operational story more understandable for general readers

## Recommended Website Project Page
### Suggested title
**Pharma Supply Stress Map**

### Suggested summary
A healthcare analytics case study that combines FDA shortage data, openFDA product information, and CMS Medicare Part D spending data to rank which drug shortages matter most from an exposure and cost perspective.

### Suggested project framing
This page should focus on:

- the business question
- the scoring logic
- the key visuals
- what the project reveals about exposure, concentration, and risk

## Recommended Website Article
### Suggested title
**A Drug Shortage Is Not Just a Supply Problem**

### Suggested article angle
The strongest story is:

> Drug shortage data becomes far more useful when it is connected to beneficiary exposure, spending concentration, and manufacturer concentration.

### Suggested article sections
1. Why shortage lists alone are not enough
2. The business question behind the analysis
3. The official datasets used and what each adds
4. How I matched the sources and handled ambiguity
5. How I built the shortage exposure score
6. What the analysis surfaced
7. Why this matters for healthcare and pharma decision-making
8. Limitations and next steps

## Why This Would Be Strong On Your Website
This framework would help your website in a few ways.

### 1. It broadens your domain range
Your current portfolio already shows strong business and consumer analytics thinking. A pharma case study would show that your analytics approach transfers well into healthcare and life sciences.

### 2. It feels more like real BI work
This project is not just "look at a dataset and summarize it." It is:

- cross-source integration
- scoring
- risk segmentation
- prioritization
- executive-friendly storytelling

### 3. It gives you a better healthcare conversation in interviews
You would be able to talk about:

- data quality tradeoffs
- entity resolution
- public-data limitations
- KPI design
- analytical prioritization

That is exactly the kind of material that makes a case study useful in interviews.

## Risks And How To Handle Them
### Risk 1. Matching will be messy
Mitigation:

- use layered matching
- retain confidence flags
- document what was matched directly vs inferred

### Risk 2. CMS Part D is not the whole market
Mitigation:

- be explicit that this is Medicare Part D exposure, not total U.S. market exposure
- position the project as a structured lens, not a total market estimate

### Risk 3. Therapeutic classification may be inconsistent
Mitigation:

- use openFDA pharm class fields where available
- fall back to simpler category buckets if coverage is uneven

### Risk 4. Readers may interpret it clinically
Mitigation:

- keep the framing operational and analytical
- clearly state that the project is not intended for medical decision-making

## Suggested Build Phases
### Phase 1. Framework and ingestion
- pull source data
- inspect schemas
- define canonical drug key

### Phase 2. Matching and cleaned model
- build crosswalks
- score match quality
- create drug-level integrated table

### Phase 3. Exposure scoring
- create shortage exposure score
- rank drugs
- build therapeutic and manufacturer slices

### Phase 4. Website outputs
- create charts
- draft project page
- draft long-form article
- design a cover image and publish

## If You Want The Simplest Possible Version First
Start with this narrower scope:

- current shortages only
- top 100 Part D drugs by spending
- match on generic name + manufacturer
- one ranked exposure score
- three charts

That version will still be strong enough for your website and much easier to finish quickly.

## My Recommendation
If we build this, I would start with the narrow version and then expand only after the first pass looks clean.

That gives you a realistic path to a publishable project without getting stuck in perfect-data complexity.

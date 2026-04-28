## Introduction
Consumer spending is one of the most watched business signals in the U.S. economy, but it is also one of the easiest to flatten into a misleading headline.

Depending on the week, the story can sound like:

- the consumer is finally weakening
- the consumer is more resilient than expected
- inflation is making spending look stronger than it really is
- high-income households are carrying everything

The problem is that all of those statements can be directionally true at the same time and still be incomplete.

If I were supporting a consumer business, I would not want a one-line answer to the question "How is the consumer doing?" I would want a more useful answer to a harder question:

**Where is demand actually holding up, where is it still under pressure, and how does that change when I look at category performance and income mix together?**

That is the question behind this project.

I built it as a consumer analytics case study using live public data from Opportunity Insights and FRED. The goal was not just to produce a few charts, but to create a piece of analysis that explains the process clearly enough for someone seeing it for the first time to follow:

- what question I asked
- why I chose the data sources I used
- how I transformed the data
- what each chart is intended to answer
- what the results mean from a business perspective

This article is the long-form explanation of that process.

## The business question
At a high level, I wanted to test four ideas.

1. Which consumer categories still look structurally strong after accounting for inflation?
2. Which categories look weaker than they were before the pandemic?
3. Do lower-income and higher-income consumers show the same spending pattern?
4. Are the fastest-growing segments also the segments that matter most in absolute dollar terms?

Those questions matter because they lead to very different business actions.

If e-commerce is still structurally stronger than most categories, that matters for channel investment, retention strategy, and digital experience.

If restaurants and experience-adjacent categories are holding up better than furniture or apparel, that matters for promotional timing, inventory assumptions, and forecasting conversations.

If lower-income ZIP codes are recovering faster relative to their baseline, but higher-income ZIP codes still contribute more of the total spend, that matters for positioning, pricing, value messaging, and customer prioritization.

In other words, this is not really a project about "the consumer" as one monolithic group. It is a project about how to break a broad macro story into a set of decisions that would actually help a commercial team act.

## Why I chose these data sources
I wanted a mix of public sources that were credible, current, and useful for a business audience rather than only an academic one.

### Opportunity Insights Economic Tracker
The most important source in this project was the [Opportunity Insights Economic Tracker monthly Affinity consumer spending file](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/Affinity%20-%20National%20-%20Monthly.csv).

I chose it because it solves a major problem that often comes up in public consumer analysis: most macro datasets tell us what is happening overall, but not enough about **who** is driving the movement.

This file includes seasonally adjusted consumer spending change relative to a January 2020 baseline across categories such as:

- all spending
- grocery
- restaurants and hotels
- apparel and accessories
- general merchandise
- retail excluding grocery

More importantly, it breaks those categories into income quartiles based on the ZIP code where the cardholder lives. That gave me a practical way to compare how lower-income and higher-income areas were moving.

I also used the [Opportunity Insights January 2020 income-share reference file](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/Affinity%20Income%20Shares%20-%20National%20-%202020.csv). That file provides the baseline share of card spending by income quartile and helped me answer a subtle but important question:

**Is a segment growing faster because it is becoming more commercially important, or is it simply rebounding from a smaller base?**

To make sure I interpreted the fields correctly, I also reviewed:

- the [Opportunity Insights data documentation](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/docs/oi_tracker_data_documentation.md)
- the [Opportunity Insights variable dictionary](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/docs/oi_tracker_data_dictionary.md)

### FRED retail sales series
The second major source was FRED, the Federal Reserve Economic Data platform. I used monthly U.S. retail sales series for:

- [E-commerce retail sales](https://fred.stlouisfed.org/series/MRTSSM4541USN)
- [General merchandise stores](https://fred.stlouisfed.org/series/MRTSSM452USN)
- [Grocery stores](https://fred.stlouisfed.org/series/MRTSSM44511USN)
- [Food services and drinking places](https://fred.stlouisfed.org/series/MRTSSM7225USN)
- [Clothing stores](https://fred.stlouisfed.org/series/MRTSSM4481USN)
- [Furniture stores](https://fred.stlouisfed.org/series/MRTSSM442USN)

I picked those categories because they provide a useful mix of:

- convenience-led behavior
- routine/essential demand
- experience spending
- discretionary goods

That makes them useful for comparison instead of only describing one narrow pocket of spending.

### CPI and consumer sentiment
I added two supporting series from FRED:

- [Consumer Price Index](https://fred.stlouisfed.org/series/CPIAUCSL)
- [University of Michigan Consumer Sentiment](https://fred.stlouisfed.org/series/UMCSENT)

The CPI series was necessary because raw retail sales are nominal, which means inflation can make demand look healthier than it really is. I used CPI to convert the retail sales into a real-sales view.

The sentiment series was useful for a different reason. I wanted to compare **what consumers were saying** with **what consumers were still doing**. That contrast is often where the more interesting business story appears.

## A quick note on why the baselines are different
This is one of the most important methodological points in the project, so I want to say it very clearly.

The two main datasets do not use the same baseline:

- Opportunity Insights reports spending change relative to **January 2020**
- My retail category index from FRED is normalized to **2019 average = 100**

That is intentional, not a mistake.

I kept the Opportunity Insights framing because the dataset itself is already structured around that baseline and it is the cleanest way to preserve the meaning of the published series.

I used a 2019 baseline for the retail category index because I wanted a stable pre-pandemic benchmark for real category demand.

That means I do **not** directly compare the numeric levels across the two systems as if they were the same measure. Instead, I use them for two different but complementary purposes:

- the FRED-based index answers: "How does category demand compare with a pre-pandemic real-sales baseline?"
- the Opportunity Insights data answers: "How does spending by income group compare with the January 2020 starting point?"

Together, they create a richer picture than either source could on its own.

## How I built the analysis
I wanted the analysis to be reproducible, transparent, and easy to extend. So I built a local Python pipeline that downloads the public files, processes them, and generates the draft outputs.

### Step 1. Pull the live source files
The script downloads the source files directly from their public URLs and stores them inside the project workspace.

That matters for two reasons:

- the project is easy to rerun later with updated data
- the analysis is traceable back to the exact sources used

### Step 2. Convert everything to a common monthly structure
The files are all time series, but they do not arrive in the same format.

- Opportunity Insights provides a monthly indexed series
- FRED retail files are nominal sales levels
- CPI and sentiment are additional monthly series

I standardized the date fields so that all of them could be aligned by month before I started any calculations.

### Step 3. Deflate the FRED retail series
This is one of the most important transformation steps in the project.

Raw retail sales levels can rise simply because prices rose. That does not necessarily mean consumers bought more in real terms.

To fix that, I deflated each retail category using CPI and then indexed the resulting real values to **2019 average = 100**.

This creates a cleaner interpretation:

- above 100 means the category is above its 2019 real baseline
- below 100 means the category is below its 2019 real baseline

That let me compare categories in a way that is much more useful than raw nominal dollar levels.

### Step 4. Address a minor continuity issue
The CPI series had a missing observation for October 2025 in the downloaded file. To keep the monthly index continuous, I interpolated that single point using the adjacent months.

I am deliberately including that detail because small adjustments like that should not be hidden. The effect on the broader analysis is minor, but the process should still be transparent.

### Step 5. Build the income-segment view
The Opportunity Insights file already contains spending change by income quartile, so I used it to build a category-by-quartile comparison for the latest available month.

That gives an immediate answer to the question:

**Which consumer groups are showing stronger relative spending growth in each category?**

### Step 6. Estimate the latest income share mix
This was an important extra step because growth rate alone can be misleading.

Suppose one segment grows faster than another. That still does not tell us whether it now represents more of total spending. A smaller segment can post a stronger growth rate and still remain smaller in absolute terms.

To avoid that trap, I started from the January 2020 baseline income shares provided by Opportunity Insights and re-weighted those shares using the latest all-spending growth values.

This created a simple estimate of current spend share by income quartile. It is not meant to replace a full market-size model, but it is very useful for separating:

- relative momentum
- absolute contribution

That distinction is central to good consumer analysis.

## What I created
The project produces four main outputs.

### 1. Real retail demand by category
This chart shows six categories of U.S. retail demand after adjusting for inflation and indexing to a 2019 baseline.

This is the best chart for understanding structural category resilience.

![Real retail demand by category](/uploads/retail-real-index.svg)

### 2. Income-segment spending heatmap
This heatmap shows the latest Opportunity Insights category growth by income quartile.

This is the best chart for understanding how the spending story changes when I stop treating the consumer as a single group.

![Latest income-segment spend snapshot](/uploads/income-heatmap-latest.svg)

### 3. Income-share slope chart
This chart compares January 2020 baseline spend share by income quartile with an estimated latest share based on current all-spending growth.

This is the best chart for explaining why "fastest-growing segment" and "largest spending segment" are not the same thing.

![Estimated income share shift](/uploads/income-share-slope.svg)

### 4. Website-ready written narrative
I also created a draft project summary and article so the analysis is understandable to someone who is not reading the code, the data files, or the charts in isolation.

That matters because a portfolio project should communicate well to multiple audiences:

- recruiters
- hiring managers
- interviewers
- business stakeholders
- other analysts

## How to read the results
Before I get into the findings, it helps to frame what each source is really telling us.

The FRED retail view is most useful for answering:

- what categories are structurally stronger or weaker in real terms?
- where has demand shifted over the last several years?

The Opportunity Insights view is most useful for answering:

- which income segments are showing more momentum?
- are growth patterns different across categories?

The share model is most useful for answering:

- does stronger relative growth also mean greater dollar concentration?

Thinking about the project that way helps prevent over-interpreting any single chart.

## Finding 1. E-commerce still looks like the clearest structural winner
After adjusting for inflation and normalizing each series to its 2019 average, e-commerce stood at **159.2** in **February 2026**.

That means real e-commerce sales were **+59.2% above** their 2019 benchmark.

It also gained **+9.73 percentage points** of share inside the tracked retail basket, which was the largest positive shift among the categories in the analysis.

That matters because it does not look like a temporary distortion anymore. It looks like a lasting change in how consumers prefer to buy.

If I were supporting a retailer, marketplace, or consumer platform, I would treat that as evidence that convenience continues to be a strategic advantage, not just an operational channel.

## Finding 2. Experience-oriented demand held up better than heavier discretionary goods
Restaurants were at **115.8** in February 2026, which means they remained **+15.8% above** their 2019 real-sales baseline.

Furniture, by contrast, was at **79.3**, or **-20.7% below** baseline.

Clothing was at **77.6**, or **-22.4% below** baseline.

General merchandise was also below baseline at **88.7**, or **-11.3%**.

This was one of the most useful pattern splits in the project because it suggests consumers are not simply "strong" or "weak." They are selective.

Some categories tied to convenience, routine, and experiences continue to hold up relatively well. Categories tied to heavier discretionary purchases still look much more pressured.

That difference matters for:

- forecasting assumptions
- promotional planning
- category messaging
- pricing and elasticity conversations

## Finding 3. Weak consumer confidence did not translate into uniform demand weakness
The University of Michigan consumer sentiment reading was **53.3 in March 2026**.

That places it very close to the low end of its post-2000 history. In this project, it lands near the bottom of the observed distribution for the modern period.

If I only looked at that sentiment measure, I might expect demand to look broadly soft across the board.

But the retail category data does not support a single uniform pullback story.

Instead, it shows a split:

- e-commerce remains very strong
- restaurants remain positive versus pre-pandemic baseline
- grocery is closer to flat in real terms
- furniture and clothing remain more pressured

This is exactly why I wanted sentiment in the project. It acts as a useful reminder that stated confidence and observed spending do not move in a perfectly simple way.

For business teams, that is important. It means macro headlines should inform decision-making, but they should not replace category-level analysis.

## Finding 4. Lower-income ZIP codes showed stronger relative growth in several categories
In the **March 2026** Opportunity Insights release:

- all spending was **+48.3%** for Q1 low-income ZIP codes versus **+28.6%** for Q4 high-income ZIP codes
- restaurants and hotels were **+43.1%** for Q1 versus **+20.9%** for Q4
- general merchandise was **+110.0%** for Q1 versus **+74.0%** for Q4
- retail excluding grocery was **+55.2%** for Q1 versus **+33.0%** for Q4

That tells me that lower-income ZIP codes were showing stronger **relative growth versus their own baseline** in multiple categories.

This is an important point, because a lot of consumer commentary implicitly assumes that higher-income households are the only relevant story. This dataset suggests the reality is more nuanced.

Momentum can be stronger in lower-income areas even if those areas are not the biggest spend contributors in absolute terms.

## Finding 5. Grocery behaved differently from other categories
One of the subtler findings in the income-segment data is grocery.

Grocery did not show the same large income gap as categories like general merchandise or restaurants and hotels.

In March 2026:

- Q1 grocery spending was **+20.5%**
- Q4 grocery spending was **+19.5%**

That relative similarity makes sense. Grocery is more routine and less discretionary than many other categories in the analysis.

This is a good example of why category context matters. A high gap in one category may reflect promotional sensitivity, channel behavior, or value-seeking, while a smaller gap in another category may simply reflect the fact that it serves a more universal spending need.

## Finding 6. High-income ZIP codes still carried the largest share of spend
This is where I think the project becomes more useful than a simple growth table.

The January 2020 income-share file shows that baseline card spending was distributed roughly like this:

- Q1 low-income ZIP codes: **14.4%**
- Q2: **21.5%**
- Q3: **27.1%**
- Q4 high-income ZIP codes: **37.0%**

So even before looking at current growth, higher-income ZIP codes were starting from a much larger share of total spending.

After re-weighting those baseline shares using the latest all-spending growth rates, the estimated latest mix becomes:

- Q1: **15.6%**
- Q2: **22.4%**
- Q3: **27.1%**
- Q4: **34.8%**

This means two things are true at the same time:

- lower-income ZIP codes are showing faster relative growth
- higher-income ZIP codes still account for the largest share of total spending

That is the kind of nuance that matters in real business decisions. A team that only watches growth rates might overstate the size of the lower-income opportunity. A team that only watches share might miss an important change in momentum.

The better approach is to hold both views at once.

## What the charts are meant to communicate
### The retail demand chart
This chart is the structural view.

It answers:

- which categories have truly moved above pre-pandemic real demand?
- which ones are still below where they used to be?

Its main value is that it strips away some of the confusion created by nominal growth and inflation.

### The income heatmap
This chart is the segmentation view.

It answers:

- where is spending growth strongest by income group?
- which categories show the widest spread between lower-income and higher-income consumers?

Its main value is that it makes the spending story more human and more commercially useful.

### The income share slope chart
This chart is the interpretation guardrail.

It answers:

- does faster growth automatically mean a segment now dominates spend?

Its main value is that it prevents an easy but common analytical mistake.

## What this means for a consumer business
If I were presenting this analysis to a brand, retailer, marketplace, or strategy team, I would convert the findings into a short set of decisions.

### 1. Do not treat all discretionary demand the same way
Furniture, clothing, and restaurants should not be grouped into one broad "discretionary" bucket without qualification.

Restaurants are showing a very different demand profile from furniture and clothing. Treating them the same would flatten the strategy.

### 2. Convenience still deserves strategic investment
The strength of e-commerce suggests convenience is not just a pandemic-era distortion. It remains a central part of how consumers want to shop.

That should influence:

- channel strategy
- lifecycle communication
- customer journey design
- retention thinking

### 3. Lower-income growth may matter more than broad assumptions suggest
If lower-income ZIP codes are showing relatively stronger growth in general merchandise and other value-sensitive categories, then there may be more opportunity there than a top-line income narrative would suggest.

That does not automatically mean a business should pivot entirely toward that segment, but it does mean the segment deserves close attention.

### 4. Scale and momentum should be tracked separately
This is one of the strongest takeaways from the project.

Businesses should separately track:

- who is growing fastest
- who is contributing the most dollars

Those are related questions, but they are not the same question.

## Limitations of the project
Even though the project is useful, it is important to be clear about what it does not do.

### It is a national view
This analysis is built on national monthly data. It does not capture how the story may vary across states, cities, or local markets.

### It uses public external data only
That means the project is great for market context, but it is not a substitute for internal transaction, loyalty, CRM, pricing, or marketing performance data.

### The income share refresh is an estimate
The latest spend-share view is estimated by re-weighting published baseline shares with current all-spending growth. It is a useful interpretation tool, but not a perfect substitute for a fully published current-period share file.

### Category definitions are source-specific
Opportunity Insights and FRED do not define categories in exactly the same way. I use them side by side to answer related questions, not to force a false one-to-one reconciliation.

## What I would do next
If I extended this into a larger analytics product or business review, I would add:

- a longer time-series view of income-quartile trends by category
- state or metro cuts to identify regional differences
- event markers for inflation peaks, stimulus periods, and rate changes
- internal business overlays such as brand sales, paid media response, or conversion metrics

That would move the project from a strong external consumer signal framework into a more operational decision system.

## Why this project matters for my work
I built this project to reflect the kind of analytics work I want to do more of.

What I enjoy most is not simply pulling data or making dashboards. It is:

- framing the right business question
- finding credible data that actually helps answer it
- combining multiple signals without confusing them
- designing metrics that reduce analytical shortcuts
- translating the results into something a business team can use

That is what I wanted this project to show.

For me, good analytics should make a complex topic easier to reason about without oversimplifying it. Consumer demand is a perfect example of that challenge.

## Final takeaway
The main lesson from this project is simple:

**Consumer spending is not one story.**

A soft confidence reading does not automatically mean weak demand everywhere.

Fast growth in one segment does not automatically mean that segment now carries the business.

And a top-line consumer narrative is rarely enough for real decision-making.

The more useful view is one that separates:

- category resilience
- income-segment momentum
- spend concentration

Once those are separated, the story becomes more actionable.

That is the type of analysis I wanted this project to demonstrate.

## Research notes and sources
- [Opportunity Insights Economic Tracker monthly Affinity data](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/Affinity%20-%20National%20-%20Monthly.csv)
- [Opportunity Insights methodology and processing notes](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/docs/oi_tracker_data_documentation.md)
- [Opportunity Insights variable dictionary](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/docs/oi_tracker_data_dictionary.md)
- [Opportunity Insights January 2020 income-share file](https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/Affinity%20Income%20Shares%20-%20National%20-%202020.csv)
- [FRED consumer sentiment series](https://fred.stlouisfed.org/series/UMCSENT)
- [FRED CPI series](https://fred.stlouisfed.org/series/CPIAUCSL)
- [FRED e-commerce retail sales](https://fred.stlouisfed.org/series/MRTSSM4541USN)
- [FRED restaurants and drinking places](https://fred.stlouisfed.org/series/MRTSSM7225USN)
- [FRED clothing stores](https://fred.stlouisfed.org/series/MRTSSM4481USN)
- [FRED furniture stores](https://fred.stlouisfed.org/series/MRTSSM442USN)
- [FRED grocery stores](https://fred.stlouisfed.org/series/MRTSSM44511USN)
- [FRED general merchandise stores](https://fred.stlouisfed.org/series/MRTSSM452USN)

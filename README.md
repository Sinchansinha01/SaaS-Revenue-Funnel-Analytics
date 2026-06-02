# SaaS Revenue Funnel Analytics

An end-to-end go-to-market (GTM) pipeline analytics project that takes simulated CRM data from raw generation through SQL cleaning, Python enrichment and modelling, and into a fully specified Power BI dashboard. Every Python and SQL step is runnable as-is and reproducible from a fixed random seed.

## Outputs at a glance

| Funnel | Forecast vs Target |
|---|---|
| ![Funnel](charts/funnel_chart.png) | ![Forecast](charts/forecast_chart.png) |

**Stack:** Python (pandas, numpy, scikit-learn, matplotlib) · SQL (ANSI / SQLite / PostgreSQL) · Power BI (DAX, star schema)


Here's a first-person walkthrough you can use to explain the project — written the way you'd actually talk someone through it, with the plain-English version first and the technical detail folded in right after. I've kept it in clear steps.

---

**Opening (how to frame it)**

"So this is an end-to-end GTM pipeline analytics project. The idea was to take raw sales data and carry it all the way through to a finished Power BI dashboard — basically simulating what a Revenue Operations team does in real life. I built it in six stages, and each stage feeds the next one."

---

**Step 1 — I created the data first**

"In simple terms, I didn't have a real CRM to pull from, so I generated my own realistic sales dataset — leads, opportunities, closed deals, and a calendar table covering two years.

*Technically*, I used **Python with pandas and numpy** to simulate four tables. I made the data behave like the real world — for example, bigger companies get bigger deal sizes, and a deal's chance of closing depends on what stage it's in. I also deliberately broke the data a little — added duplicate records, some missing dates, a few blank values — because real CRM data is always messy, and I wanted something to clean up in the next step. Everything's seeded with a fixed random number, so it reproduces identically every time I run it."

---

**Step 2 — I cleaned and validated it with SQL**

"Next I loaded that messy data into a database and cleaned it up — removed duplicates, filled in the gaps, and standardized the labels.

*Technically*, I wrote it all in **ANSI SQL** (works in both SQLite and PostgreSQL). I started with *profiling queries* — counting nulls, finding duplicate IDs, spotting outliers — basically diagnosing the problems first. Then I built cleaned tables: I deduplicated leads, filled missing deal values using the **median for that industry and company size**, and estimated missing close dates from the average sales-cycle length. After that, I wrote eight **analytical queries** answering real business questions — funnel conversion rates, win rate by rep, pipeline coverage, a weighted revenue forecast, and so on."

---

**Step 3 — I enriched it and added some modelling**

"Then I took the clean data back into Python to add smarter columns and do a bit of light data science.

*Technically*, I did three things. First, **feature engineering** — I calculated how long each deal had been sitting in the pipeline, flagged 'stalled' deals, and grouped deals into size bands. Second, I ran a **KMeans clustering model** to automatically group closed deals into three archetypes — I labelled them 'High Value Fast Close', 'Mid Market Standard', and 'Long Tail'. Third, I built a **weighted revenue forecast** — each open deal's value multiplied by its probability of closing — and compared it against a $1.2M quarterly target. I also produced two charts: a forecast-vs-target chart with a confidence band, and a sales funnel chart."

---

**Step 4 — I built the Power BI data model**

"With clean, enriched data ready, I set up the structure inside Power BI so all the tables talk to each other correctly.

*Technically*, I designed a **star schema** — fact tables in the middle (opportunities, closed deals, forecast) connected to dimension tables around them (leads, dates, sales reps). I defined every relationship, the cardinality, and the filter direction. Then I wrote **20 DAX measures** — these are the calculations behind every number on the dashboard, like Win Rate, Forecasted ARR, Rolling 3-Month Revenue, and CAC efficiency — using proper patterns like `CALCULATE`, `DATESINPERIOD`, and `SWITCH`."

---

**Step 5 — I designed the report itself**

"Then I laid out the actual dashboard — five pages, each aimed at a different audience.

*Technically*, I specified every page: an **Executive Summary** for leadership, a **Funnel & Conversion** page, a **Forecast vs Target** page, a **Rep Leaderboard**, and a **Customer Segment Deep Dive**. For each one I defined exactly which visual goes where, what fields sit on each axis, the conditional formatting rules (like turning win rate green or red), the slicers for filtering, and even the tooltip text so a first-time viewer understands each chart."

---




A couple of delivery tips: if you're explaining to a **non-technical** person, just read the first sentence of each step and skip the *"Technically"* parts. If it's an **interview or a technical reviewer**, lead with the plain sentence and then go into the technical detail — it shows you can do the work *and* communicate it.

Want me to make a shorter 60-second version, or drop this into a one-page document (or slides) you can hand over?

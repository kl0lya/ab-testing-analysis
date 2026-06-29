# ab-testing-analysis
A/B test significance analysis: 4 tests · Z-test for proportions · segment breakdowns · Tableau dashboard

> **Statistical analysis of 4 A/B tests** for an e-commerce platform — evaluating the impact of product changes on key funnel metrics using Z-tests for proportions, with segment-level breakdowns by country, device, continent, and traffic channel.

---

## Live Dashboard

**[View on Tableau Public →](https://public.tableau.com/app/profile/olha.klochnyk/viz/ABTestingAnalytics/ABTestingAnalytics)**

---

## Project Goals

- Extract A/B test data from **Google BigQuery** using a multi-CTE SQL query
- Calculate **conversion rates** and **statistical significance** for each test and metric
- Detect **segment-level effects** that are hidden in aggregate results
- Present findings in an **interactive Tableau dashboard**

---

## Dataset

Data extracted from **Google BigQuery** (`data-analytics-mate.DA`) via a custom SQL query with 4 CTEs joining 5 tables:

| Table | Description |
|---|---|
| `ab_test` | Test assignments — session ID, test name, group (control/treatment) |
| `session` | Session dates |
| `session_params` | Country, device, continent, traffic channel |
| `event_params` | Funnel events per session |
| `order` | Completed purchases |
| `account_session` | New account registrations |

**Output dataset:** long-format table with one row per `date × dimension × test × group × event`, enabling flexible aggregation across any slice.

---

## Methodology

### Metric Definition
Each metric is measured as a **conversion rate**:

```
CR = event_count / session_count
```

| Metric | Description |
|---|---|
| `add_payment_info` | Share of sessions where payment info was added |
| `add_shipping_info` | Share of sessions where shipping info was added |
| `begin_checkout` | Share of sessions where checkout was initiated |
| `new_account` | Share of sessions that resulted in a new registration |

### Statistical Test
**Z-test for two proportions** (`statsmodels.stats.proportion.proportions_ztest`)
- Significance level: **α = 0.05**
- Alternative: two-sided
- Groups: control (group 1) vs. treatment (all other groups combined)

### Dimensions Analysed
Results calculated at **5 levels**: total · country · device · continent · channel

---

## Key Findings

| Test | Significant metrics | Direction | Conclusion |
|---|---|---|---|
| **Test 1** | `add_payment_info`, `add_shipping_info`, `begin_checkout` | Positive | Strong positive impact — recommend rollout |
| **Test 2** | None (all p > 0.2) | — | No reliable effect — insufficient evidence |
| **Test 3** | `begin_checkout` | Negative (−3.35%) | Introduced friction at checkout — do not ship |
| **Test 4** | `begin_checkout`, `new_account` | Negative | Negative effect on checkout and registration |

### Key Insight: Segment Effects Hidden in Aggregates
> Aggregate ("total") results often mask **opposite effects in different segments**.  
> Example: in **Test 4**, the "Direct" and "Undefined" channels showed strong **positive** shifts — even while the overall test result trended negative for the same metrics.  
> This highlights the importance of always checking segment-level breakdowns before making a ship/no-ship decision.

---

## Tech Stack

| Tool | Usage |
|---|---|
| **Python 3.10** | Core analysis language |
| **pandas / NumPy** | Data manipulation and aggregation |
| **SciPy / statsmodels** | Z-test for proportions |
| **Google BigQuery** | Data source (multi-CTE SQL query) |
| **Google Colab** | Development environment |
| **Tableau Public** | Interactive results dashboard |

---

## Author

**Olha Klochnyk** — Data Analyst


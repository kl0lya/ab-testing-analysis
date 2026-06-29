# Data Loading


# imports
import numpy as np
import pandas as pd

import scipy.stats as stats
from statsmodels.stats.proportion import proportions_ztest

# Install the BigQuery client library
!pip install --upgrade google-cloud-bigquery

# Authenticate with Google credentials
from google.colab import auth
from google.cloud import bigquery

auth.authenticate_user()

# Create a BigQuery client
client= bigquery.Client(project="data-analytics-mate")

# Join tables
sql_query = """
        WITH session_info AS (
        SELECT
          s.date,
          s.ga_session_id,
          sp.country,
          sp.device,
          sp.continent,
          sp.channel,
          ab.test,
          ab.test_group
        FROM `DA.ab_test` ab
        JOIN `DA.session` s
          ON ab.ga_session_id = s.ga_session_id
        JOIN `DA.session_params` sp
          ON sp.ga_session_id = ab.ga_session_id
        ),
        session_with_orders AS (
        SELECT
          session_info.date,
          session_info.country,
          session_info.device,
          session_info.continent,
          session_info.channel,
          session_info.test,
          session_info.test_group,
          COUNT(DISTINCT o.ga_session_id) AS session_with_orders
        FROM `DA.order` o
        JOIN session_info
          ON o.ga_session_id = session_info.ga_session_id
        GROUP BY
          session_info.date,
          session_info.country,
          session_info.device,
          session_info.continent,
          session_info.channel,
          session_info.test,
          session_info.test_group
        ),
        events AS (
        SELECT
          session_info.date,
          session_info.country,
          session_info.device,
          session_info.continent,
          session_info.channel,
          session_info.test,
          session_info.test_group,
          sp.event_name,
          COUNT(sp.ga_session_id) AS event_cnt
        FROM `DA.event_params` sp
        JOIN session_info
          ON sp.ga_session_id = session_info.ga_session_id
        GROUP BY
          session_info.date,
          session_info.country,
          session_info.device,
          session_info.continent,
          session_info.channel,
          session_info.test,
          session_info.test_group,
          sp.event_name
        ),
        session AS (
        SELECT
          session_info.date,
          session_info.country,
          session_info.device,
          session_info.continent,
          session_info.channel,
          session_info.test,
          session_info.test_group,
          COUNT(DISTINCT session_info.ga_session_id) AS session_cnt
        FROM session_info
        GROUP BY
          session_info.date,
          session_info.country,
          session_info.device,
          session_info.continent,
          session_info.channel,
          session_info.test,
          session_info.test_group
        ),
        account AS (
        SELECT
          session_info.date,
          session_info.country,
          session_info.device,
          session_info.continent,
          session_info.channel,
          session_info.test,
          session_info.test_group,
          COUNT(DISTINCT acs.ga_session_id) AS new_account_cnt
        FROM `DA.account_session` acs
        JOIN session_info
          ON acs.ga_session_id = session_info.ga_session_id
        GROUP BY
          session_info.date,
          session_info.country,
          session_info.device,
          session_info.continent,
          session_info.channel,
          session_info.test,
          session_info.test_group
        )
        SELECT
        session_with_orders.date,
        session_with_orders.country,
        session_with_orders.device,
        session_with_orders.continent,
        session_with_orders.channel,
        session_with_orders.test,
        session_with_orders.test_group,
        'session with orders' AS event_name,
        session_with_orders.session_with_orders AS value
        FROM session_with_orders
        UNION ALL
        SELECT
        events.date,
        events.country,
        events.device,
        events.continent,
        events.channel,
        events.test,
        events.test_group,
        events.event_name,
        events.event_cnt AS value
        FROM events
        UNION ALL
        SELECT
        session.date,
        session.country,
        session.device,
        session.continent,
        session.channel,
        session.test,
        session.test_group,
        'session' AS event_name,
        session.session_cnt AS value
        FROM session
        UNION ALL
        SELECT
        account.date,
        account.country,
        account.device,
        account.continent,
        account.channel,
        account.test,
        account.test_group,
        'new account' AS event_name,
        account.new_account_cnt AS value
        FROM account;

    """

# Processing the request
query_job = client.query(sql_query)

# Loading into a DataFrame without the BigQuery Storage API
ab_test = query_job.to_dataframe(create_bqstorage_client=False)

print(ab_test.head())

"""# Data Overview"""

# Shape & column types

print("Number of columns:", ab_test.shape[1])
print("Number of rows:   ", ab_test.shape[0])
print("Numeric columns:  ", ab_test.select_dtypes(include="number").columns.tolist())
print("Object columns:   ", ab_test.select_dtypes(include="object").columns.tolist())
print("Datetime columns: ", ab_test.select_dtypes(include="datetime").columns.tolist())
print("\nDetailed info:\n")
print(ab_test.info())

# Change data format to datetime
ab_test["date"] = pd.to_datetime(ab_test["date"])

# Quick data checks

for col in ["continent", "channel", "device", "test",
            "test_group", "event_name"]:
    print(f"\n--- {col} ---")
    print(ab_test[col].value_counts())

"""# Calculation of Statistical Significance"""

metrics = {
    "add_payment_info":  "add_payment_info",
    "add_shipping_info": "add_shipping_info",
    "begin_checkout":    "begin_checkout",
    "new_account":       "new account",
}

alpha   = 0.05
session = "session"

dimensions = ["country", "device", "continent", "channel"]

# Calculation function

def calc_significance(df, group_cols):

    results = []

    # Iterate each unique group
    for group_vals, group_df in df.groupby(group_cols):

        if isinstance(group_vals, str):
            group_vals = (group_vals,)
        group_dict = dict(zip(group_cols, group_vals))

        # Number of sessions for treatment and control groups (1 - control, 2 - treatment)
        sessions = (
            group_df[group_df["event_name"] == session]
            .groupby("test_group")["value"].sum()
        )
        n_ctrl = sessions.get(1, 0)
        n_trt  = sessions[sessions.index != 1].sum()

        # Iterate each metric
        for metric_col, event_name in metrics.items():

            events = (
                group_df[group_df["event_name"] == event_name]
                .groupby("test_group")["value"].sum()
            )
            suc_ctrl = events.get(1, 0)
            suc_trt  = events[events.index != 1].sum()

            # Conversion
            cr_ctrl = round(suc_ctrl / n_ctrl, 6) if n_ctrl > 0 else np.nan
            cr_trt  = round(suc_trt  / n_trt,  6) if n_trt  > 0 else np.nan
            rel_diff = round((cr_trt - cr_ctrl) / cr_ctrl, 4) if cr_ctrl else np.nan

            # Z-test
            if n_ctrl > 0 and n_trt > 0:
                stat, p_value = proportions_ztest(
                    count=[suc_ctrl, suc_trt],
                    nobs= [n_ctrl,   n_trt],
                    alternative="two-sided"
                )
                p_value = round(p_value, 6)
                stat    = round(stat, 4)
            else:
                stat, p_value = np.nan, np.nan

            is_sig = (not np.isnan(p_value)) and (p_value < alpha)

            results.append({
                **group_dict,
                "metric":         metric_col,
                "denominator":    session,
                "sessions_ctrl":  int(n_ctrl),
                "sessions_trt":   int(n_trt),
                "events_ctrl":    int(suc_ctrl),
                "events_trt":     int(suc_trt),
                "cr_ctrl":        cr_ctrl,
                "cr_trt":         cr_trt,
                "relative_diff":  rel_diff,
                "z_stat":         stat,
                "p_value":        p_value,
                "is_significant": is_sig
            })

    return pd.DataFrame(results)

# Calculations

# Total results per test
print("Total results per test\n")
results_total = calc_significance(ab_test, group_cols=["test"])
results_total.insert(1, "slice_dim",   "total")
results_total.insert(2, "slice_value", "total")
print(results_total[["test", "metric", "cr_ctrl", "cr_trt", "p_value", "is_significant"]])

# Results by dimensions
all_results = [results_total]

for dim in dimensions:
    print(f"Results by {dim}")
    res = calc_significance(ab_test, group_cols=["test", dim])
    res = res.rename(columns={dim: "slice_value"})
    res.insert(1, "slice_dim", dim)
    print(res[["test", "slice_value", "metric", "p_value", "is_significant"]].head())
    all_results.append(res)

# Combine results in one dataset
final_df = pd.concat(all_results, ignore_index=True)

print(final_df.head())

# Save the DataFrame to a CSV file
final_df.to_csv("ab_test_results.csv", index=False, encoding="utf-8")

"""# [CSV File with results](https://drive.google.com/file/d/1uR3IAhUzfoEuVhcWGYqEpBK45z4LQ15x/view?usp=drive_link)

# [Tableau Dashboard](https://public.tableau.com/views/ABTestingAnalytics/ABTestingAnalytics?:language=en-US&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link)

# Conclusions
Each of the 4 metrics is tested as a conversion rate (event / sessions) and compared between the control and test groups using a **Z-test for two proportions**.
This tells us whether the difference we observe is a real effect of the test — or just random noise in the data.

**Significant (p < 0.05)** — we're 95%+ confident the result is real, not chance.

**Not Significant (p ≥ 0.05)** — the difference could easily have happened by chance; more data may be needed.


- **Test 1** showed the clearest positive impact: 3 out of 4 metrics (add_payment_info, add_shipping_info, begin_checkout) improved with high statistical confidence (p < 0.01).

- **Test 2** showed no statistically significant change on any metric (all p-values > 0.2) — despite small positive movements in the raw numbers, none of them are reliably different from random variation.

- **Test 3** showed a significant *negative* effect specifically on begin_checkout (p = 0.012, -3.35%), while the other three metrics were not statistically significant.

- **Test 4** showed significant negative effects on begin_checkout and new_account (p = 0.046 and 0.018), suggesting the tested variant may have introduced friction at both checkout completion and account creation.

- Level breakdowns (channel, continent, country, device) reveal that aggregate ("total") results  often hide opposite effects in different segments — for example,  in Test 4 the "Direct" and "Undefined" channels show strong positive shifts even where the overall test trends negative for some metrics.
"""

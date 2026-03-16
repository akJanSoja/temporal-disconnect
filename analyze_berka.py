"""Extract Berka dataset metrics for the Temporal Disconnect demo page."""
import duckdb
import json

con = duckdb.connect()
con.execute("CREATE TABLE trans AS SELECT * FROM read_csv_auto('data/berka/trans.csv', delim=';', header=true)")

# Shared CTE: parse dates and classify transactions
CLASSIFY_SQL = """
WITH parsed AS (
  SELECT
    trans_id, account_id,
    STRPTIME('19' || LPAD(CAST(date AS VARCHAR), 6, '0'), '%Y%m%d')::DATE AS txn_date,
    type, operation, amount, balance, k_symbol
  FROM trans
),

anchors AS (
  SELECT
    account_id,
    txn_date AS anchor_date,
    amount,
    ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY txn_date) AS event_seq
  FROM parsed
  WHERE type = 'PRIJEM'
    AND amount > 10000
    AND (k_symbol IS NULL OR k_symbol = ' ')
),

first_anchors AS (
  SELECT account_id, anchor_date, amount
  FROM anchors WHERE event_seq = 1
),

windows AS (
  SELECT
    account_id, anchor_date,
    anchor_date - INTERVAL '30 days' AS window_start,
    anchor_date + INTERVAL '90 days' AS window_end
  FROM first_anchors
),

classified AS (
  SELECT
    t.account_id, t.txn_date, t.amount, t.type,
    CASE
      WHEN t.txn_date < w.anchor_date THEN 'Stage 0: Pre-signal'
      WHEN t.txn_date <= w.anchor_date + INTERVAL '30 days' THEN 'Stage 1: Initiation'
      WHEN t.txn_date <= w.anchor_date + INTERVAL '60 days' THEN 'Stage 2: Active'
      ELSE 'Stage 3: Normalization'
    END AS event_stage,
    w.anchor_date
  FROM parsed t
  JOIN windows w
    ON t.account_id = w.account_id
    AND t.txn_date BETWEEN w.window_start AND w.window_end
)
"""

# 1. Total transactions
total_txns = con.execute("SELECT COUNT(*) FROM trans").fetchone()[0]
print(f"Total transactions: {total_txns:,}")

# 2. Total accounts
total_accounts = con.execute("SELECT COUNT(DISTINCT account_id) FROM trans").fetchone()[0]
print(f"Total accounts: {total_accounts:,}")

# 3. Accounts with detectable events
accounts_with_events = con.execute("""
  SELECT COUNT(DISTINCT account_id) FROM trans
  WHERE type = 'PRIJEM' AND amount > 10000 AND (k_symbol IS NULL OR k_symbol = ' ')
""").fetchone()[0]
print(f"Accounts with events: {accounts_with_events:,}")

# 4. Event stage distribution
stages = con.execute(f"""
{CLASSIFY_SQL}
SELECT event_stage, COUNT(*) AS txn_count, ROUND(AVG(amount), 0) AS avg_amount,
       ROUND(SUM(amount), 0) AS total_amount
FROM classified GROUP BY event_stage ORDER BY event_stage
""").fetchall()
print("\nEvent stage distribution:")
stage_data = []
for row in stages:
    print(f"  {row[0]}: {row[1]:,} txns, avg {row[2]:,.0f} CZK, total {row[3]:,.0f} CZK")
    stage_data.append({
        "stage": row[0],
        "transaction_count": row[1],
        "avg_amount": int(row[2]),
        "total_amount": int(row[3])
    })

# 5. Average window duration
avg_window = con.execute(f"""
{CLASSIFY_SQL}
SELECT ROUND(AVG(span), 0) FROM (
  SELECT account_id, DATEDIFF('day', MIN(txn_date), MAX(txn_date)) AS span
  FROM classified GROUP BY account_id
)
""").fetchone()[0]
print(f"\nAvg window duration: {avg_window:.0f} days")

# 6. Stage 1 (initiation) avg amount vs overall avg
comparison = con.execute(f"""
{CLASSIFY_SQL},
overall AS (
  SELECT ROUND(AVG(amount), 0) AS avg FROM (
    SELECT amount FROM parsed
    WHERE account_id IN (SELECT account_id FROM first_anchors)
  )
)
SELECT
  c.event_stage,
  ROUND(AVG(c.amount), 0) AS stage_avg,
  (SELECT avg FROM overall) AS overall_avg
FROM classified c
GROUP BY c.event_stage
ORDER BY c.event_stage
""").fetchall()
print("\nStage avg vs overall avg:")
overall_avg = None
stage_comparison = []
for row in comparison:
    if overall_avg is None:
        overall_avg = int(row[2])
    pct = round(row[1] / row[2] * 100)
    print(f"  {row[0]}: {row[1]:,.0f} CZK ({pct}% of overall avg {row[2]:,.0f})")
    stage_comparison.append({
        "stage": row[0],
        "avg_amount": int(row[1]),
        "pct_of_overall": pct
    })

# 7. Naive segment stability
stability = con.execute("""
WITH parsed AS (
  SELECT account_id,
    STRPTIME('19' || LPAD(CAST(date AS VARCHAR), 6, '0'), '%Y%m%d')::DATE AS txn_date,
    amount
  FROM trans
),
monthly AS (
  SELECT account_id, STRFTIME(txn_date, '%Y-%m') AS month, SUM(amount) AS monthly_spend
  FROM parsed GROUP BY account_id, month
),
ranked AS (
  SELECT account_id, month, monthly_spend,
    NTILE(4) OVER (PARTITION BY month ORDER BY monthly_spend) AS spend_quartile
  FROM monthly
),
stability AS (
  SELECT account_id, COUNT(DISTINCT spend_quartile) AS quartile_changes
  FROM ranked GROUP BY account_id
)
SELECT ROUND(AVG(quartile_changes), 2) FROM stability
""").fetchone()[0]
print(f"\nNaive segment changes (avg quartiles per account): {stability}")

# Build the summary JSON
summary = {
    "total_transactions": total_txns,
    "total_accounts": total_accounts,
    "accounts_with_events": accounts_with_events,
    "pct_accounts_with_events": round(accounts_with_events / total_accounts * 100),
    "avg_window_days": int(avg_window),
    "overall_avg_amount": overall_avg,
    "naive_segment_changes": float(stability),
    "stages": stage_data,
    "stage_comparison": stage_comparison,
    "note": "Berka dataset. Anchors: PRIJEM type, amount > 10000 CZK, non-recurring. Window: -30d to +90d from first anchor per account."
}

with open("data/berka_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print("\nSaved to data/berka_summary.json")

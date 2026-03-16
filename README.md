# Temporal Disconnect in Transaction Data
**A framework for modeling life events, not just transactions**

*Jan Soja — BI Analyst & Data Engineer, Göteborg*

---

## TL;DR

A family books a ski trip in November. The trip happens in February.
For 103 days, every related purchase — gear, pharmacy, ski passes,
restaurants — looks like unrelated noise to a naive model. Temporal
Disconnect is the framework that connects them: one event, four stages,
predictable arc. Validated on 1M+ transactions (Berka dataset), where
72% of accounts show the same pattern and naive segmentation churns
2.8× per account. The fix is not more data — it is a different question.

---

## The Problem

Most transaction models ask: *when did money move?*

The more useful question is: *what was happening in this person's life?*

These are not the same question. The gap between them is **Temporal Disconnect** —
the delay between when a life event begins and when it fully materializes
in transaction data.

Ignore this gap and your model sees noise.
Model it correctly and you see signal.

---

## Definition

> **Temporal Disconnect** is the structural lag between the onset of a
> behavioral event and its complete expression in recorded transaction data.

This is not a data quality problem. The data is accurate.
It is a **framing problem** — transactions are timestamped,
but the events that drive them are not.

---

## Why It Matters

A model trained on raw transaction timestamps will:

- Misclassify spend patterns mid-event as anomalies
- Fail to detect early-stage events before spending peaks
- Build incorrect customer segments based on lagged behavior
- Miss churn signals that appear weeks before a category shift

A model that accounts for Temporal Disconnect will:

- Detect life events earlier, from the first signal transaction
- Cluster customers by *event stage*, not just spend level
- Generate more stable segments over time
- Enable proactive rather than reactive decision-making

---

## The Sportlov Example

The Lindqvist family booked a ski trip on **November 3rd**.
The trip happened **February 14–19th**. That is **103 days** between
the decision and the event.

| Date        | Transaction                            | Naive label      | TD-aware label                |
|-------------|----------------------------------------|------------------|-------------------------------|
| 3 Nov       | Resia.se — 4 flights Arlanda–Mora      | Travel           | Stage 1 — Initiation (anchor) |
| 18 Nov      | Stadium — ski jackets ×2, helmets      | Sporting goods   | Stage 1 — Core spend          |
| 2 Dec       | Apoteket — sunscreen, blister plasters | Health & pharmacy| Stage 1 — Cascade spend       |
| 9 Jan       | Stadium — ski boots rental pre-order   | Sporting goods   | Stage 2 — Core spend          |
| 14 Feb      | Ski-pass Lindvallen, 4 pers × 6 days  | Leisure          | Stage 2 — Core spend          |
| 14–19 Feb   | Restaurants in Sälen × 8 txns          | Food & beverage  | Stage 2 — Cascade spend       |
| 19 Feb      | Apotek Hjärtat — ibuprofen, knee support | Health         | Stage 3 — Cascade spend       |
| 2 Mar       | Fotoboken.se — photobook               | Other retail     | Stage 3 — Normalization       |

A naive model sees 8 transactions across 6 categories over 4 months.
A TD-aware model sees **one event, four stages, and a predictable arc**.

---

## Berka Dataset Validation

The framework was validated against the Czech banking Berka dataset
(1,056,320 transactions across 4,500 accounts).

**Key findings:**

- **72%** of accounts contain detectable event patterns
- Pre-signal spend is **78% below** the overall average — the quiet
  before the event is itself a detectable pattern
- Initiation spend spikes to **152% of baseline** — the anchor
  transaction creates a measurable step change
- Naive segmentation churns **2.8× per account** — without event
  context, the same customer lands in a different quartile almost
  every month
- Average event window: **104 days** of structurally misframed data
  per account

Anchors: high-value (>10,000 CZK), non-recurring credit transactions.
Window: −30 to +90 days from first anchor per account.

See `analyze_berka.py` for the full extraction script (requires DuckDB).

---

## How to Identify Temporal Disconnect in Your Data

### Step 1 — Identify anchor transactions
Anchor transactions are high-signal, low-frequency purchases that
typically mark the *start* of a life event.

Examples: flight bookings, ski pass purchases, real estate agents,
moving companies, equipment rental.

### Step 2 — Build event windows
For each anchor transaction, define a lookback and lookahead window.
The window size is domain-specific and should be calibrated on
labeled data where available.

```
Event window = [anchor_date - T_before, anchor_date + T_after]
```

Typical starting points (financial data):
- Short events (job change, travel): T = 30–60 days
- Medium events (moving, sports holiday): T = 90–180 days
- Long events (retirement, major renovation): T = 180–365 days

### Step 3 — Classify transactions within the window
Within each event window, reclassify transactions by their
*event role*, not just their category:

- **Pre-signal**: early spend that predicts the event
- **Core spend**: expected category spend during the event
- **Cascade spend**: downstream categories activated by the event

### Step 4 — Assign event stage labels
Divide the event window into stages:

```
Stage 0: Pre-signal     (before anchor)
Stage 1: Initiation     (anchor + 0–30 days)
Stage 2: Active         (31–90 days post-anchor)
Stage 3: Normalization  (event winding down)
Stage 4: Post-event     (new baseline forming)
```

Labeling each transaction with a stage turns a flat timeline
into a structured event model.

---

## Data Model Pattern (Kimball-compatible)

If you are working in a star schema or tabular model,
Temporal Disconnect can be incorporated as a bridge table.

```
FactTransaction
  TransactionKey
  CustomerKey
  DateKey
  Amount
  CategoryKey
  EventWindowKey    ← new FK

DimEventWindow
  EventWindowKey
  EventType
  EventStage        (0–4)
  AnchorDate
  WindowStart
  WindowEnd
  ConfidenceScore
```

This preserves the original transaction record while adding
event context without denormalizing the fact table.

---

## Implementation Notes

**SQL approach**: Use window functions to scan forward/backward
from anchor transactions and assign `EventWindowKey` in a
staging or transformation layer.

**ML approach**: Treat event detection as a sequence classification
problem. Input: ordered transaction vectors per customer.
Output: event type + stage label.

**Power BI approach**: Build event window logic in the
transformation layer (SQL or dataflow), not in DAX.
DAX is not suited for row-context temporal lookups at scale.

---

## Scaling

- **Partitioning**: Partition by `account_id` so each event window
  is computed independently. No cross-account joins needed.
- **Delta Lake / Fabric**: Stage classification as a medallion layer.
  Bronze = raw transactions, Silver = anchor-detected,
  Gold = stage-labeled.
- **Spark**: The window join is embarrassingly parallel per account.
  Broadcast the anchor table, partition transactions by account.

---

## Limitations and Open Questions

- **Window calibration** requires labeled ground truth or
  domain expert input. Without it, window sizes are assumptions.
- **Sparse customers** (few transactions per month) produce
  unreliable event detection.
- **Multi-event overlap** (customer is simultaneously moving
  and planning a holiday) requires disambiguation logic.
- **Privacy and regulation**: event-level inference from
  transaction data has GDPR implications in Sweden/EU.
  Model outputs should be aggregate or anonymized unless
  explicit consent exists.

---

## Demo Site

Open `index.html` in a browser to see the interactive demo, including:
- Toggle between naive and TD-aware transaction views
- Live DuckDB-WASM SQL query
- Berka dataset validation with Chart.js visualizations
- Naive vs TD comparison and insight callout

To run locally: `python -m http.server 8080` and open `http://localhost:8080`.

---

## Summary

Temporal Disconnect is not an exotic concept.
It is a structural property of any dataset where behavior
precedes or extends beyond the timestamps that record it.

The fix is not more data. It is a different question:
not *when did money move* but *what was happening*.

That reframe changes what you model, how you segment,
and what decisions the model can support.

---

*Framework version 1.1 — March 2026*
*Feedback and forks welcome.*

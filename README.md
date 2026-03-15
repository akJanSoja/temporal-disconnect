# Temporal Disconnect in Transaction Data
**A framework for modeling life events, not just transactions**

*Jan Soja — BI Analyst & Data Engineer, Göteborg*

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

## The Three-Transaction Example

| Date    | Transaction        | Category        | Naive label      |
|---------|--------------------|-----------------|------------------|
| March   | Jewelry store      | Retail          | Gift?            |
| April   | Event venue        | Entertainment   | Party?           |
| June    | Hawaii flights     | Travel          | Vacation         |

Individually: noise.
Sequentially, with category awareness: **engagement → wedding planning → honeymoon**.

One life event. Three months. Three data points that only make sense together.

---

## How to Identify Temporal Disconnect in Your Data

### Step 1 — Identify anchor transactions
Anchor transactions are high-signal, low-frequency purchases that
typically mark the *start* of a life event.

Examples: jewelry, fertility clinics, real estate agents,
moving companies, baby specialty stores.

### Step 2 — Build event windows
For each anchor transaction, define a lookback and lookahead window.
The window size is domain-specific and should be calibrated on
labeled data where available.

```
Event window = [anchor_date - T_before, anchor_date + T_after]
```

Typical starting points (financial data):
- Short events (job change, travel): T = 30–60 days
- Medium events (moving, new baby): T = 90–180 days
- Long events (divorce, retirement): T = 180–365 days

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

## Limitations and Open Questions

- **Window calibration** requires labeled ground truth or
  domain expert input. Without it, window sizes are assumptions.
- **Sparse customers** (few transactions per month) produce
  unreliable event detection.
- **Multi-event overlap** (customer is simultaneously moving
  and having a child) requires disambiguation logic.
- **Privacy and regulation**: event-level inference from
  transaction data has GDPR implications in Sweden/EU.
  Model outputs should be aggregate or anonymized unless
  explicit consent exists.

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

*Framework version 1.0 — March 2026*
*Feedback and forks welcome.*

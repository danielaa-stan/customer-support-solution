# 05. Knowledge base for RAG (C → B contract)

C creates the files; B indexes them. Numeric values come from [04-business-rules.md](04-business-rules.md).

## Policies: `data/policies/*.md`

One file = one document. File name = `doc_id` + `.md` (e.g. `refund-policy.md`).
For required documents and sections, see the table in 04.

Format:

```markdown
---
doc_id: refund-policy
title: Refund policy
version: 1.0
---

## 2.1 Refund window
Refunds are available within 14 days of the charge date ...

## 2.2 Duplicate charge
If we charged you twice ...
```

Rules:

1. Section headings use `## <number> <title>`. The number is the citation anchor.
2. Citation format (`policy_ref`): `doc_id#number`, e.g. `refund-policy#2.1`.
3. Each section contains 2–6 self-contained sentences (no "see above"), because B splits the document into chunks by section.
4. All content must be in English, including policies, cases, titles, customer messages, summaries, and examples, as required by [01-ownership.md](01-ownership.md).

B returns objects from `search_policy` in the form `{doc_id, section, title, text, policy_ref}`.

## Similar cases: `data/cases.json`

An array of ≥ 150 resolved cases (target: 200). Item format:

```json
{
  "case_id": "case_0042",
  "title": "Cancellation due to price, retained with a discount",
  "intent": "cancel_subscription",
  "reason": "price_too_high",
  "plan": "individual",
  "customer_message": "It has become too expensive for me. I want to cancel.",
  "summary": "The customer listened for 35 hours/month. Offered discount_50_3m; accepted.",
  "actions": [
    {"tool": "get_available_offers", "args": {}},
    {"tool": "apply_retention_offer", "args": {"offer_code": "discount_50_3m"}}
  ],
  "resolution": "retained",
  "policy_refs": ["retention-rules#1.1"],
  "tags": ["price", "discount"]
}
```

- `intent`, `reason`, `resolution`: enum values from [06](06-transcript-and-analysis.md).
- `actions[].tool`: only actual tool names from [03](03-mcp-tools.md).
- The case distribution must be realistic: approximately 30% cancellations, 25% billing, 15% refunds, 15% technical issues, 10% plan changes, 5% other.
- B indexes the text `title + customer_message + summary` for search.

## B's contract

B guarantees that the agent cites at least one `policy_ref` when explaining a decision involving a policy-governed action
(refund, cancellation, retention offer).

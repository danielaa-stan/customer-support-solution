# RAG source data

Policies are authored for the fictional music-streaming demo; they are not scraped company policies.
Technical troubleshooting and escalation priority details fill the demo-specific sections requested by the contracts.
Historical cases are synthetic examples produced from explicit scenario templates, not real customer records or LLM training data.

## Files

- `policies/*.md`: eight documents with front matter and 21 numbered, self-contained sections.
- `cases.json`: 200 historical examples in the exact contracted object format.
- `generate_cases.py`: deterministic, dependency-free Python generator for the case file.
- `tests/test_rag_data.py`: contract, reference, action-sequence, and reproducibility checks.

## Generate and validate

From the repository root:

```powershell
python data/generate_cases.py
python -m unittest discover -s data/tests -v
```

The checked-in cases can be indexed immediately without running the generator.
Generation requires no API key, database, network connection, or third-party package.

## Case coverage

| Category | Count | Examples |
|----------|-------|----------|
| Cancellation | 60 | Discounts, free month, accepted pauses, confirmed cancellations |
| Billing | 50 | Renewals, failed charges, pending downgrades, shared-plan totals, prior refunds |
| Refund | 30 | Eligible refunds, duplicates, exactly 14 days and 20.00 USD, expired window, human-only amounts |
| Technical | 30 | Offline downloads, CarPlay, missing playlists |
| Plan changes | 20 | Upgrades, downgrades, verified student eligibility |
| Other | 10 | Five account-access cases and five feature requests |

Cases are template-generated and vary customer wording, tenure, usage, payment age, amounts,
device context, or outcome; they are an initial retrieval corpus, not an independent quality benchmark.
Scenario facts not represented as case fields are described in each summary. Review paraphrases
against the policies when extending the dataset instead of changing prices or eligibility randomly.

## Indexing instructions

Read policy metadata from front matter, split on `## <number> <title>`, and assign each chunk
`policy_ref = doc_id#number`. Index each case using `title + customer_message + summary`.
Return the contracted fields from retrieval tools; `policy_refs` in the case file are existing section anchors.
The retrieval tool's `outcome` may be derived from the case summary and resolution; it is not an extra stored case field.

Historical `pay_case_*` and `pa_case_*` identifiers describe fictional past actions and must not be
replayed against a current account. Cancellation cases summarize explicit confirmation in a later user turn;
their action arrays are historical summaries, not an instruction to skip live confirmation.
Escalated cases represent a completed handoff with the underlying refund or repair still pending.
Current eligibility and tool results always take precedence over a retrieved example.

Customer seed data belongs separately in `data/seed/seed.json`; these cases do not populate
the support database or represent new conversations for the analytics dashboard.

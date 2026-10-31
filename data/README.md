# RAG source data

Policies are authored for the fictional music-streaming demo; they are not scraped company policies.
Technical troubleshooting and escalation priority details fill the demo-specific sections requested by the contracts.
Historical cases are synthetic examples produced from explicit scenario templates, not real customer records or LLM training data.

## Files

- `policies/*.md`: eight documents with front matter and 21 numbered, self-contained sections.
- `cases.json`: 200 historical examples in the exact contracted object format.
- `generate_cases.py`: deterministic, dependency-free Python generator for the case file.
- `tests/test_rag_data.py`: contract, reference, action-sequence, and reproducibility checks.
- `generate_seed.py`: deterministic starting-state generator for customer data.
- `seed/seed.json`: three fixed demo customers plus 40 synthetic background customers.
- `tests/test_seed_data.py`: customer relationships, starting states, and reproducibility checks.
- `validate_seed.py`: emits a rollback-only PostgreSQL schema validation transaction.
- `load_seed.py`: inserts starting data into an empty local PostgreSQL support database.

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

## Customer seed data

```powershell
python data/generate_seed.py
python -m unittest discover -s data/tests -v
python data/validate_seed.py | docker compose exec -T db psql -U support_app -d support -v ON_ERROR_STOP=1
```

The generator writes JSON only. The validation command creates an isolated schema inside a transaction,
applies `contracts/schema.sql`, inserts the generated records, and rolls everything back. It does not
populate or replace the live support tables.

To load the current JSON into the local Docker database:

```powershell
python data/load_seed.py --dry-run
python data/load_seed.py
```

The first command rolls back all inserted customer records; the second saves them. The loader uses
the container's `psql` client and needs no additional Python packages. It locks and checks all eight
support tables, refuses a nonempty database, and commits only if every insert succeeds. Re-running
it against loaded data fails without overwriting existing customers, payments, or runtime history.
No reset or delete option is provided. `--seed path/to/seed.json` selects an alternative seed file.
The loader does not regenerate data or change its prices; review the generated JSON before loading.

PostgreSQL loader tests use an isolated schema and roll back their fixtures:

```powershell
$env:RUN_POSTGRES_TESTS = '1'
python -m unittest discover -s data/tests -v
Remove-Item Env:RUN_POSTGRES_TESTS
```

All dates use the fixed `DEMO_NOW = 2026-10-31T12:00:00Z`; changing your machine clock or `.env`
does not change this dataset. Demo identifiers, duplicate payment timestamps, and required usage values
are preserved exactly. Background records cover all four plans and subscription statuses, historical
payments and refunds, pending downgrades, and retention-offer history. Runtime audit records, tickets,
and pending actions start empty. The optional large-refund bonus customer is not included yet.

The regular monthly catalog uses the supplied Ukraine prices: individual 4.99 USD, duo 6.49 USD,
family 7.99 USD, and student 2.49 USD. Introductory free-month promotions are not modeled.
All synthetic customers use that catalog; country remains a profile attribute, not a regional-price selector.

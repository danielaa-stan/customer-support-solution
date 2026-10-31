-- Run with psql against analytics as analytics_app. All fixtures are rolled back.
\set ON_ERROR_STOP on
BEGIN;
INSERT INTO dim_date (full_date) VALUES ('2026-10-31') ON CONFLICT (full_date) DO NOTHING;
INSERT INTO dim_customer (user_id, country, signed_up_at)
VALUES ('u_star_check', 'UA', '2026-02-10T09:00:00Z');

INSERT INTO fact_conversation (
  session_id, started_date_key, customer_key, plan_key, intent_key, reason_key, resolution_key,
  started_at, ended_at, sentiment_start, sentiment_end, churn_risk, quality_correctness,
  quality_policy_compliance, quality_tone, quality_resolved, kb_gap, summary, analyzed_at
)
SELECT 'ses_star_refund_check', 20261031, c.customer_key, p.plan_key,
       i.intent_key, r.reason_key, res.resolution_key,
       '2026-10-31T14:00:00+02:00', '2026-10-31T12:04:00Z', -2, 1, 0.1, 5, 5, 4, true, false,
       'Verified duplicate-charge refund.', '2026-10-31T12:05:00Z'
FROM dim_customer c CROSS JOIN dim_plan p CROSS JOIN dim_intent i
CROSS JOIN dim_reason r CROSS JOIN dim_resolution res
WHERE c.user_id = 'u_star_check' AND p.plan_code = 'individual' AND i.intent_code = 'refund_request'
  AND r.reason_code = 'double_charge' AND res.resolution_code = 'refunded';

-- Reanalysis updates the same session instead of duplicating its measures.
INSERT INTO fact_conversation (
  session_id, started_date_key, customer_key, plan_key, intent_key, reason_key, resolution_key,
  started_at, ended_at, kb_gap, summary, analyzed_at
)
SELECT session_id, started_date_key, customer_key, plan_key, intent_key, reason_key, resolution_key,
       started_at, ended_at, kb_gap, 'Reanalyzed verified duplicate-charge refund.', analyzed_at
FROM fact_conversation WHERE session_id = 'ses_star_refund_check'
ON CONFLICT (session_id) DO UPDATE SET summary = EXCLUDED.summary;

INSERT INTO fact_conversation (
  session_id, started_date_key, customer_key, intent_key, reason_key, resolution_key,
  started_at, ended_at, kb_gap, summary, analyzed_at
)
SELECT 'ses_star_unassessed_check', 20261031, customer_key, intent_key, reason_key, resolution_key,
       '2026-10-31T12:10:00Z', '2026-10-31T12:11:00Z', true,
       'Customer left before the issue could be assessed.', '2026-10-31T12:12:00Z'
FROM dim_customer CROSS JOIN dim_intent CROSS JOIN dim_reason CROSS JOIN dim_resolution
WHERE user_id = 'u_star_check' AND intent_code = 'other'
  AND reason_code = 'unknown' AND resolution_code = 'abandoned';

INSERT INTO fact_tool_call (
  audit_id, session_id, date_key, customer_key, tool_key, policy_key, occurred_at,
  result_status, autonomy_level, actor, args_json, payment_id, refunded_amount, currency
)
SELECT 2147000001, 'ses_star_refund_check', 20261031, c.customer_key, t.tool_key, p.policy_key,
       '2026-10-31T12:02:00Z', 'done', 'auto', 'agent',
       '{"payment_id":"pay_star_check","reason_code":"double_charge","policy_ref":"refund-policy#2.2"}',
       'pay_star_check', 4.99, 'USD'
FROM dim_customer c CROSS JOIN dim_tool t CROSS JOIN dim_policy p
WHERE c.user_id = 'u_star_check' AND t.tool_name = 'issue_refund' AND p.policy_ref = 'refund-policy#2.2';

-- Reimporting the same audit event does not add another refund.
INSERT INTO fact_tool_call (
  audit_id, session_id, date_key, customer_key, tool_key, policy_key, occurred_at,
  result_status, autonomy_level, actor, args_json, payment_id, refunded_amount, currency
)
SELECT audit_id, session_id, date_key, customer_key, tool_key, policy_key, occurred_at,
       result_status, autonomy_level, actor, args_json, payment_id, refunded_amount, currency
FROM fact_tool_call WHERE audit_id = 2147000001
ON CONFLICT (audit_id) DO NOTHING;

INSERT INTO fact_tool_call (
  audit_id, session_id, date_key, customer_key, tool_key, occurred_at,
  result_status, autonomy_level, actor, error_code, args_json
)
SELECT 2147000002, 'ses_star_refund_check', 20261031, c.customer_key, t.tool_key,
       '2026-10-31T12:03:00Z', 'error', 'auto', 'agent', 'ALREADY_DONE',
       '{"payment_id":"pay_star_check"}'
FROM dim_customer c CROSS JOIN dim_tool t
WHERE c.user_id = 'u_star_check' AND t.tool_name = 'issue_refund';

-- Audit imports need not wait for a completed conversation.
INSERT INTO fact_tool_call (
  audit_id, session_id, date_key, tool_key, occurred_at,
  result_status, autonomy_level, actor, args_json
)
SELECT 2147000003, 'ses_star_not_analyzed', 20261031, tool_key,
       '2026-10-31T12:20:00Z', 'done', 'read', 'agent', '{}'
FROM dim_tool WHERE tool_name = 'get_user_profile';

INSERT INTO bridge_conversation_policy (conversation_key, policy_key)
SELECT f.conversation_key, p.policy_key FROM fact_conversation f CROSS JOIN dim_policy p
WHERE f.session_id = 'ses_star_refund_check'
  AND p.policy_ref IN ('refund-policy#2.1', 'refund-policy#2.2')
ON CONFLICT DO NOTHING;

DO $$
DECLARE
  convo fact_conversation%ROWTYPE;
  call fact_tool_call%ROWTYPE;
BEGIN
  SELECT * INTO STRICT convo FROM fact_conversation WHERE session_id = 'ses_star_refund_check';
  SELECT * INTO STRICT call FROM fact_tool_call WHERE audit_id = 2147000001;
  IF convo.duration_seconds <> 240 OR convo.summary NOT LIKE 'Reanalyzed%' THEN
    RAISE EXCEPTION 'Conversation duration or reanalysis is incorrect';
  END IF;
  IF (SELECT count(*) FROM analysis WHERE user_id = 'u_star_check') <> 2 THEN
    RAISE EXCEPTION 'Multiple tool calls or policy citations multiplied conversation rows';
  END IF;
  IF (SELECT jsonb_array_length(actions_json::jsonb) FROM analysis
      WHERE session_id = 'ses_star_refund_check') <> 1 THEN
    RAISE EXCEPTION 'Denied or duplicate calls counted as successful actions';
  END IF;
  IF (SELECT jsonb_array_length(policy_refs_json::jsonb) FROM analysis
      WHERE session_id = 'ses_star_refund_check') <> 2 THEN
    RAISE EXCEPTION 'Policy bridge did not preserve distinct citations';
  END IF;
  IF (SELECT sum(refunded_amount) FROM fact_tool_call WHERE session_id = 'ses_star_refund_check') <> 4.99 THEN
    RAISE EXCEPTION 'Refund was duplicated during audit reimport';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM analysis WHERE session_id = 'ses_star_unassessed_check'
                 AND sentiment_start IS NULL AND churn_risk IS NULL
                 AND quality_json::jsonb -> 'correctness' = 'null'::jsonb) THEN
    RAISE EXCEPTION 'Missing estimates were converted to zero';
  END IF;
  BEGIN
    UPDATE fact_conversation SET reason_key = -999 WHERE conversation_key = convo.conversation_key;
    RAISE EXCEPTION 'Invalid dimension reference was accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  BEGIN
    UPDATE fact_conversation SET sentiment_start = 3 WHERE conversation_key = convo.conversation_key;
    RAISE EXCEPTION 'Invalid sentiment was accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    UPDATE fact_conversation SET churn_risk = 1.1 WHERE conversation_key = convo.conversation_key;
    RAISE EXCEPTION 'Invalid churn risk was accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    UPDATE fact_conversation SET quality_correctness = 0 WHERE conversation_key = convo.conversation_key;
    RAISE EXCEPTION 'Invalid quality score was accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    UPDATE fact_conversation SET ended_at = started_at - INTERVAL '1 second'
    WHERE conversation_key = convo.conversation_key;
    RAISE EXCEPTION 'Negative duration was accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO dim_date(full_date) VALUES ('2026-11-01') ON CONFLICT DO NOTHING;
    UPDATE fact_conversation SET started_date_key = 20261101 WHERE conversation_key = convo.conversation_key;
    RAISE EXCEPTION 'Date key did not match the UTC timestamp';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    UPDATE fact_tool_call SET result_status = 'denied' WHERE tool_call_key = call.tool_call_key;
    RAISE EXCEPTION 'Denied call was allowed to carry a completed refund';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO fact_tool_call (
      audit_id, session_id, date_key, customer_key, tool_key, occurred_at,
      result_status, autonomy_level, actor, args_json, payment_id, refunded_amount, currency
    ) VALUES (
      2147000004, call.session_id, call.date_key, call.customer_key, call.tool_key, call.occurred_at,
      'done', 'auto', 'agent', call.args_json, call.payment_id, 4.99, 'USD'
    );
    RAISE EXCEPTION 'Same payment was counted as two refunds';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
END $$;
ROLLBACK;
SELECT 'Star schema grain, constraints, views, and retry checks passed' AS result;

"""Read operational evidence and atomically upsert one analytics session."""

from datetime import datetime, timezone

from analytics.analysis import timestamp


def read_source(connection, doc):
    with connection.transaction():
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        user = connection.execute('SELECT id, country, created_at FROM users WHERE id = %s', (doc['user_id'],)).fetchone()
        if user is None:
            raise ValueError('Transcript customer does not exist in support')
        audit = connection.execute('SELECT * FROM audit_log WHERE session_id = %s ORDER BY id', (doc['session_id'],)).fetchall()
        payments = connection.execute('SELECT * FROM payments WHERE user_id = %s', (doc['user_id'],)).fetchall()
        pending = connection.execute('SELECT * FROM pending_actions WHERE session_id = %s', (doc['session_id'],)).fetchall()
    return {'user': user, 'audit': audit, 'payments': payments, 'pending': pending}


def persist(connection, doc, source, result, dry_run=False):
    from psycopg.types.json import Jsonb
    from psycopg import Rollback

    with connection.transaction():
        # Serialize reanalysis of the same session, including citation replacement.
        connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (doc['session_id'],))

        def key(table, code_column, code):
            # Table and column identifiers are internal constants, never model input.
            row = connection.execute(f'SELECT * FROM {table} WHERE {code_column} = %s', (code,)).fetchone()
            if row is None:
                raise ValueError(f'Missing reference dimension: {table} / {code}')
            return row[table.removeprefix('dim_') + '_key']

        def day(value):
            date = timestamp(value).date()
            connection.execute('INSERT INTO dim_date(full_date) VALUES (%s) ON CONFLICT DO NOTHING', (date,))
            return int(date.strftime('%Y%m%d'))

        user = source['user']
        customer = connection.execute('''INSERT INTO dim_customer(user_id, country, signed_up_at)
            VALUES (%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET country=EXCLUDED.country,
            signed_up_at=EXCLUDED.signed_up_at RETURNING customer_key''',
            (user['id'], user.get('country'), user.get('created_at'))).fetchone()['customer_key']
        quality = result['quality']
        values = {
            'session_id': doc['session_id'], 'started_date_key': day(doc['started_at']), 'customer_key': customer,
            'plan_key': key('dim_plan', 'plan_code', result['plan']),
            'intent_key': key('dim_intent', 'intent_code', result['primary_intent']),
            'reason_key': key('dim_reason', 'reason_code', result['underlying_reason']),
            'resolution_key': key('dim_resolution', 'resolution_code', result['resolution']),
            'started_at': timestamp(doc['started_at']), 'ended_at': timestamp(doc['ended_at']),
            'sentiment_start': result['sentiment_start'], 'sentiment_end': result['sentiment_end'],
            'churn_risk': result['churn_risk'], 'quality_correctness': quality['correctness'],
            'quality_policy_compliance': quality['policy_compliance'], 'quality_tone': quality['tone'],
            'quality_resolved': quality['resolved'], 'kb_gap': result['kb_gap'], 'summary': result['summary'],
            'analyzed_at': max(datetime.now(timezone.utc), timestamp(doc['ended_at'])),
        }
        columns = list(values)
        updates = ', '.join(f'{column}=EXCLUDED.{column}' for column in columns if column not in {'session_id', 'customer_key'})
        row = connection.execute(f'''INSERT INTO fact_conversation({','.join(columns)})
            VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT(session_id) DO UPDATE SET {updates}
            WHERE fact_conversation.customer_key=EXCLUDED.customer_key RETURNING conversation_key''',
            tuple(values.values())).fetchone()
        if row is None:
            raise ValueError('Session identity collision: existing conversation belongs to another customer')
        conversation = row['conversation_key']
        for audit in source['audit']:
            args = audit['args']
            values = {
                'audit_id': audit['id'], 'session_id': doc['session_id'], 'date_key': day(audit['ts']),
                'customer_key': customer, 'tool_key': key('dim_tool', 'tool_name', audit['tool']),
                'reason_key': key('dim_reason', 'reason_code', audit['reason_code']) if audit.get('reason_code') else None,
                'policy_key': key('dim_policy', 'policy_ref', audit['policy_ref']) if audit.get('policy_ref') else None,
                'offer_key': key('dim_offer', 'offer_code', args['offer_code']) if audit['tool'] == 'apply_retention_offer' and args.get('offer_code') in {'discount_50_3m', 'free_month_1'} else None,
                'occurred_at': timestamp(audit['ts']), 'result_status': audit['result_status'],
                'autonomy_level': audit['autonomy_level'], 'actor': audit['actor'],
                'error_code': audit.get('error_code'), 'args_json': Jsonb(args),
                'payment_id': args.get('payment_id'), 'refunded_amount': audit['refunded_amount'], 'currency': audit['currency'],
            }
            columns = list(values)
            updates = ', '.join(f'{column}=EXCLUDED.{column}' for column in columns if column not in {'audit_id', 'session_id', 'customer_key'})
            row = connection.execute(f'''INSERT INTO fact_tool_call({','.join(columns)})
                VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT(audit_id) DO UPDATE SET {updates}
                WHERE fact_tool_call.session_id=EXCLUDED.session_id AND fact_tool_call.customer_key=EXCLUDED.customer_key
                RETURNING tool_call_key''', tuple(values.values())).fetchone()
            if row is None:
                raise ValueError('Audit identity collision; support source may have been reset')
        connection.execute('DELETE FROM bridge_conversation_policy WHERE conversation_key=%s', (conversation,))
        for ref in result['policy_refs']:
            connection.execute('INSERT INTO bridge_conversation_policy VALUES (%s,%s) ON CONFLICT DO NOTHING',
                               (conversation, key('dim_policy', 'policy_ref', ref)))
        if dry_run:
            raise Rollback()
    return conversation

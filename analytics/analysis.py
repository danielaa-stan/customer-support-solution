"""Validate completed transcripts and reconcile model estimates with audit evidence."""

import copy
import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTENTS = {'cancel_subscription', 'billing_issue', 'refund_request', 'plan_change', 'technical_issue', 'account_access', 'other'}
REASONS = {'price_too_high', 'low_usage', 'technical_problems', 'switching_competitor', 'double_charge', 'billing_confusion', 'temporary_break', 'other', 'unknown'}
RESOLUTIONS = {'resolved_auto', 'retained', 'canceled', 'refunded', 'escalated', 'abandoned'}
END_REASONS = {'resolved_by_agent', 'escalated', 'user_left'}
REF = re.compile(r'\b[a-z][a-z-]*#\d+\.\d+\b')


class OpenConversation(ValueError):
    """An incomplete transcript must not be published as completed analysis."""


def timestamp(value):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    else:
        raise ValueError('Expected a timestamp')
    if result.tzinfo is None:
        raise ValueError('Timestamps must include a timezone')
    return result.astimezone(timezone.utc)


def policy_refs():
    return {f'{path.stem}#{section}' for path in (ROOT / 'data/policies').glob('*.md')
            for section in re.findall(r'^## (\d+\.\d+) ', path.read_text(encoding='utf-8'), re.M)}


def validate_transcript(doc):
    if not isinstance(doc, dict):
        raise ValueError('Transcript must be an object')
    if not doc.get('ended_at') or not doc.get('end_reason'):
        raise OpenConversation('Conversation is still open')
    if doc['end_reason'] not in END_REASONS:
        raise ValueError('Invalid end_reason')
    for field in ('session_id', 'user_id'):
        if not isinstance(doc.get(field), str) or not doc[field].strip():
            raise ValueError(f'Missing {field}')
    start, end = timestamp(doc['started_at']), timestamp(doc['ended_at'])
    if end < start:
        raise ValueError('Conversation ended before it started')
    messages = doc.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ValueError('Transcript requires messages')
    previous = start
    for seq, message in enumerate(messages, 1):
        if message.get('seq') != seq or message.get('role') not in {'user', 'assistant', 'tool', 'system'}:
            raise ValueError('Invalid message order or role')
        current = timestamp(message['ts'])
        if not previous <= current <= end:
            raise ValueError('Message timestamp is outside conversation order')
        previous = current
        if message['role'] == 'tool':
            if not isinstance(message.get('content'), dict) or not isinstance(message.get('name'), str):
                raise ValueError('Tool messages require a name and structured response')
        elif not isinstance(message.get('content'), str):
            raise ValueError('Message content must be text')


def prepare_source(doc, source):
    """Copy and validate evidence; never mutate caller data or operational records."""
    validate_transcript(doc)
    source = copy.deepcopy(source)
    if source['user']['id'] != doc['user_id']:
        raise ValueError('Customer does not match transcript')
    audit = source['audit']
    seen = set()
    for row in audit:
        if row['session_id'] != doc['session_id'] or row['user_id'] != doc['user_id']:
            raise ValueError('Audit session/customer mismatch')
        if type(row['id']) is not int or row['id'] in seen:
            raise ValueError('Invalid or duplicate audit ID')
        seen.add(row['id'])
        timestamp(row['ts'])
        row['args'] = json.loads(row['args_json']) if isinstance(row['args_json'], str) else row['args_json']
        if not isinstance(row['args'], dict):
            raise ValueError('Audit arguments must be an object')
    # A purely conversational/RAG turn can legitimately have no MCP audit rows.
    mcp_tools = {'get_user_profile', 'get_payments', 'get_available_offers', 'pause_subscription',
                 'change_plan', 'apply_retention_offer', 'issue_refund', 'cancel_subscription',
                 'confirm_action', 'reject_action', 'escalate_to_human'}
    if not audit and any(message['role'] == 'tool' and message['name'] in mcp_tools for message in doc['messages']):
        raise ValueError('No matching audit evidence; retry after audit ingestion is complete')
    audit.sort(key=lambda row: row['id'])
    payments = {p['id']: p for p in source.get('payments', [])}
    for payment in payments.values():
        if payment['user_id'] != doc['user_id']:
            raise ValueError('Payment customer mismatch')
    pending = {p['id']: p for p in source.get('pending', [])}
    for item in pending.values():
        if item['user_id'] != doc['user_id'] or item['session_id'] != doc['session_id']:
            raise ValueError('Pending action session/customer mismatch')
    refunded = set()
    for row in audit:
        row['refunded_amount'] = row['currency'] = None
        row['business_tool'] = row['tool']
        if row['tool'] == 'confirm_action' and row['result_status'] == 'done':
            item = pending.get(row['args'].get('pending_action_id'))
            if not item or item['status'] != 'confirmed':
                raise ValueError('Successful confirmation lacks matching confirmed pending action')
            row['business_tool'] = item['tool']
        if row['tool'] != 'issue_refund' or row['result_status'] != 'done':
            continue
        payment_id = row['args'].get('payment_id')
        payment = payments.get(payment_id)
        if (not payment or payment['status'] != 'refunded' or not payment.get('refunded_at')
                or timestamp(payment['refunded_at']) != timestamp(row['ts'])
                or payment.get('refund_reason') != row.get('reason_code')):
            raise ValueError('Successful refund lacks matching refunded payment evidence')
        if payment_id in refunded:
            continue
        amount = Decimal(str(payment['amount']))
        if not amount.is_finite() or amount <= 0 or not re.fullmatch('[A-Z]{3}', payment['currency']):
            raise ValueError('Invalid verified refund amount or currency')
        row['refunded_amount'], row['currency'] = str(amount), payment['currency']
        refunded.add(payment_id)
    return source


def reconcile(doc, source, estimate):
    required = {'primary_intent', 'underlying_reason', 'resolution', 'sentiment_start', 'sentiment_end',
                'churn_risk', 'quality', 'kb_gap', 'summary', 'policy_refs'}
    if not isinstance(estimate, dict) or set(estimate) != required:
        raise ValueError('Model output must match the analysis JSON contract exactly')
    for field, choices in (('primary_intent', INTENTS), ('underlying_reason', REASONS), ('resolution', RESOLUTIONS)):
        if estimate[field] not in choices:
            raise ValueError(f'Invalid {field}')
    for field in ('sentiment_start', 'sentiment_end'):
        value = estimate[field]
        if value is not None and (type(value) is not int or not -2 <= value <= 2):
            raise ValueError(f'Invalid {field}')
    risk = estimate['churn_risk']
    if risk is not None and (type(risk) not in (int, float) or not math.isfinite(risk) or not 0 <= risk <= 1):
        raise ValueError('Invalid churn_risk')
    quality = estimate['quality']
    if not isinstance(quality, dict) or set(quality) != {'correctness', 'policy_compliance', 'tone', 'resolved'}:
        raise ValueError('Invalid quality assessment')
    for field in ('correctness', 'policy_compliance', 'tone'):
        if quality[field] is not None and (type(quality[field]) is not int or not 1 <= quality[field] <= 5):
            raise ValueError('Invalid quality score')
    if quality['resolved'] is not None and type(quality['resolved']) is not bool:
        raise ValueError('Invalid quality resolved flag')
    if type(estimate['kb_gap']) is not bool or not isinstance(estimate['summary'], str) or not 0 < len(estimate['summary'].strip()) <= 2000:
        raise ValueError('Invalid summary or knowledge-base-gap flag')
    successful = [r for r in source['audit'] if r['result_status'] == 'done']
    tools = {r['business_tool'] for r in successful}
    if 'escalate_to_human' in tools:
        outcome = 'escalated'
    elif any(r['refunded_amount'] is not None for r in successful):
        outcome = 'refunded'
    elif 'cancel_subscription' in tools:
        outcome = 'canceled'
    elif estimate['primary_intent'] == 'cancel_subscription' and tools & {'apply_retention_offer', 'pause_subscription', 'change_plan'}:
        outcome = 'retained'
    elif doc['end_reason'] == 'user_left' or quality['resolved'] is not True:
        outcome = 'abandoned'
    else:
        outcome = 'resolved_auto'
    if estimate['resolution'] != outcome:
        raise ValueError(f'Model resolution disagrees with verified evidence; expected {outcome}')
    known = policy_refs()
    cited = {r['policy_ref'] for r in source['audit'] if r.get('policy_ref')}
    for message in doc['messages']:
        if message['role'] == 'assistant':
            cited.update(REF.findall(message['content']))
    cited &= known
    if not isinstance(estimate['policy_refs'], list) or any(not isinstance(ref, str) or ref not in cited for ref in estimate['policy_refs']):
        raise ValueError('Model cited a policy without transcript/audit evidence')
    plan = 'unknown'
    by_id = {r['id']: r for r in source['audit']}
    changes = [r['id'] for r in successful if r['business_tool'] == 'change_plan']
    for message in doc['messages']:
        if message['role'] != 'tool' or message['name'] != 'get_user_profile':
            continue
        response = message['content']
        receipt = by_id.get(response.get('audit_id'))
        if receipt and receipt['tool'] == 'get_user_profile' and receipt['result_status'] == 'done' and (not changes or receipt['id'] < min(changes)):
            candidate = response.get('data', {}).get('subscription', {}).get('plan')
            if candidate in {'individual', 'duo', 'family', 'student'}:
                plan = candidate
                break
    return {**estimate, 'policy_refs': sorted(cited), 'plan': plan}

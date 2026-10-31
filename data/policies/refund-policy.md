---
doc_id: refund-policy
title: Refund policy
version: 1.0
---

## 2.1 Refund window
A payment is eligible for a refund only when its status is succeeded, it has not already been refunded, and no more than 14 days have elapsed since its charge timestamp.
Check the payment record before proposing a refund and use the fixed demo clock when evaluating demo data.
A payment outside the 14-day window must be denied with POLICY_DENIED rather than described as refunded.
Canceling a subscription does not automatically refund a payment.

## 2.2 Duplicate charge
A duplicate-charge candidate consists of two succeeded payments for the same user and the same amount, charged no more than 24 hours apart.
Refund the second payment with reason_code double_charge only when the refund window and automatic refund limit also permit it.
Explain which payment was refunded and retain the first legitimate payment.
A repeated request for an already refunded payment returns ALREADY_DONE and must not create another refund.

## 2.3 Automatic limit and escalation
An eligible refund of 20.00 USD or less may be executed automatically through issue_refund.
An amount above 20.00 USD requires human review, even when the payment is inside the 14-day window.
When the server returns LIMIT_EXCEEDED with needs_human true, create a human-support ticket with the payment details and a suggested action.
Do not split a payment into smaller refunds to bypass the automatic limit or claim that an escalated refund has been completed.

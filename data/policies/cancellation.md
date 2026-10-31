---
doc_id: cancellation
title: Subscription cancellation
version: 1.0
---

## 1.1 Right to cancel and one alternative
A customer may request cancellation without accepting a retention offer or explaining personal circumstances.
After identifying the reason, the agent may offer one relevant alternative, but a refusal or repeated cancellation request ends further persuasion.
Cancellation always requires explicit confirmation after the agent explains the proposed action and its consequences.
Call confirm_action only after a new user message explicitly confirms the pending action; otherwise reject the action or clarify the response.
Never treat the customer's original cancellation request as confirmation of a proposal created afterward.

## 1.2 Cancellation at the end of the period
The default cancellation mode is end_of_period, which preserves access until next_billing_date and prevents further renewal charges.
After confirmation, the subscription remains active until its scheduled cancel_at timestamp.
Use immediate cancellation only when the customer requests it and confirms the loss of access.
Neither cancellation mode grants a refund automatically; evaluate any refund request under the refund policy.

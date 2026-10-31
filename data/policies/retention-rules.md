---
doc_id: retention-rules
title: Retention offers
version: 1.0
---

## 1.1 Offer eligibility
The discount_50_3m offer gives a 50% discount on the next three charges to an active subscriber with at least three months of tenure whose plan is not student.
The free_month_1 offer gives one free month to an active subscriber with at least 12 months of tenure.
Both offers require no retention offer within the preceding 12 months, and the server determines current eligibility through get_available_offers.
Apply an offer only after the customer accepts it and only if that offer appears in the server response.
Switching to a cheaper or shared plan is an ordinary plan change and does not count as a retention offer.

## 1.2 Retention cooldown
A customer may receive at most one retention offer within a 12-month period.
Check the recorded retention-offer history before presenting a benefit, including offers granted in earlier conversations.
Do not replace an unavailable discount with a free month to bypass the cooldown.
Explain ineligibility plainly and offer an appropriate ordinary plan change or cancellation when requested.

## 1.3 One offer per conversation
After understanding why a customer wants to leave, the agent may present one relevant alternative during the conversation.
If the customer declines or repeats the request to cancel, proceed with cancellation and its required confirmation.
Do not present a sequence of discounts, pauses, and shared plans after a refusal.
An unavailable offer must never be promised as an exception.

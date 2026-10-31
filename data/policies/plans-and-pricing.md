---
doc_id: plans-and-pricing
title: Plans and pricing
version: 1.0
---

## 1.1 Monthly prices and seats
The individual plan costs 9.99 USD per month for one seat, and duo costs 12.99 USD per month for two seats.
The family plan costs 15.99 USD per month for six seats, and student costs 4.99 USD per month for one seat.
At full occupancy, family costs approximately 2.67 USD per person per month; the account is still charged the full 15.99 USD.
Explain the total price and seat count before recommending a shared plan rather than promising savings without enough participants.

## 1.2 Student eligibility
The student plan is available only when the account has verified student status, represented by is_student equal to 1 in stored customer data.
Check the current account profile before recommending or applying student pricing.
A customer saying they are a student does not authorize changing the verification flag or bypassing eligibility checks.
If verification is unresolved, explain the requirement and escalate when the customer needs assistance outside the available tools.

## 1.3 Plan changes
Use change_plan with an allowed plan code after the customer agrees to the change.
An upgrade takes effect immediately, while a downgrade takes effect at the next billing date and is recorded as pending_plan.
Report the effective timing returned by the server rather than promising immediate access or savings for every change.
A change to a cheaper or shared plan is not a retention offer and does not consume a retention-offer allowance.

"""Generate deterministic, fictional retrieval examples using only the standard library."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OPENINGS = (
    "Could you help me?",
    "I need some help with my account.",
    "I would like to understand my options.",
    "Please check this for me.",
    "I have a question about my subscription.",
)
PLANS = (("individual", "4.99"), ("duo", "6.49"), ("family", "7.99"), ("student", "2.49"))


def action(tool, **args):
    return {"tool": tool, "args": args}


def build_cases():
    cases = []

    def add(title, intent, reason, plan, message, summary, actions, resolution, refs, tags):
        cases.append({
            "case_id": f"case_{len(cases) + 1:04d}",
            "title": title,
            "intent": intent,
            "reason": reason,
            "plan": plan,
            "customer_message": message,
            "summary": summary,
            "actions": actions,
            "resolution": resolution,
            "policy_refs": refs,
            "tags": tags,
        })

    # Six cancellation paths, with different tenure, usage, and customer wording.
    for i in range(60):
        scenario, variant = i % 6, i // 6
        opening = OPENINGS[variant % len(OPENINGS)]
        tenure, hours = 6 + variant, 22 + variant * 3
        reads = [action("get_user_profile")]
        if scenario in (0, 1):
            offer = "discount_50_3m" if scenario == 0 else "free_month_1"
            tenure = tenure if scenario == 0 else 14 + variant
            benefit = "50% off the next three charges" if scenario == 0 else "one free month"
            add(
                f"Price concern after {tenure} months, accepted {offer}",
                "cancel_subscription", "price_too_high", "individual",
                f"{opening} I have subscribed for {tenure} months and listen about {hours} hours a month, "
                "but the price is becoming difficult. I am thinking of canceling.",
                f"The active individual subscriber had {tenure} months of tenure, {hours} listening hours, "
                f"and no retention offer in the preceding 12 months. get_available_offers included {offer}; "
                f"the agent presented only that alternative, the customer accepted {benefit}, and the tool succeeded.",
                reads + [action("get_available_offers"), action("apply_retention_offer", offer_code=offer,
                                                              reason_code="price_too_high")],
                "retained", ["retention-rules#1.1", "retention-rules#1.2", "retention-rules#1.3"],
                ["cancellation", "price", "eligible", offer],
            )
        elif scenario == 2:
            months = 1 + variant % 3
            add(
                f"Temporary {months}-month break accepted instead of cancellation",
                "cancel_subscription", "temporary_break", "individual",
                f"{opening} I will be away for {months} months and want to cancel while I cannot listen.",
                f"The customer wanted a temporary break of {months} months. The agent offered a pause as the "
                f"only alternative; the customer accepted and pause_subscription succeeded with no charges during the pause.",
                reads + [action("pause_subscription", months=months, reason_code="temporary_break")],
                "retained", ["pause-policy#1.1", "cancellation#1.1"],
                ["cancellation", "pause", "temporary_break"],
            )
        else:
            reason = {3: "low_usage", 4: "switching_competitor", 5: "technical_problems"}[scenario]
            explanation = {
                3: f"I listened for only {0.2 + variant / 10:.1f} hours this month",
                4: f"I have used this service for {tenure} months but am moving to another service",
                5: f"playback has failed on {1 + variant % 3} of my devices",
            }[scenario]
            pending_id = f"pa_case_{len(cases) + 1:04d}"
            add(
                f"Confirmed cancellation for {reason}, customer example {variant + 1}",
                "cancel_subscription", reason, "individual",
                f"{opening} Please cancel my subscription because {explanation}. I do not want another offer.",
                "The customer declined an alternative and repeated the request to cancel. The agent explained "
                "end-of-period access and no further renewal charges, created a pending cancellation, and received "
                "explicit confirmation in a later user message before confirm_action succeeded; no refund was implied.",
                reads + [action("cancel_subscription", reason_code=reason, effective="end_of_period"),
                         action("confirm_action", pending_action_id=pending_id)],
                "canceled", ["cancellation#1.1", "cancellation#1.2", "agent-conduct#1.2"],
                ["cancellation", "confirmed", reason],
            )

    # Billing explanations do not imply a refund or a new account mutation.
    for i in range(50):
        scenario, variant = i % 5, i // 5
        plan, price = PLANS[variant % len(PLANS)]
        day = 1 + variant
        templates = (
            ("Regular renewal explained", f"Why was I charged {price} USD on October {day}?",
             f"The {price} USD payment was one successful renewal for the {plan} plan. The agent explained "
             "the monthly price and billing date; the customer accepted the explanation and no refund was issued.",
             ["plans-and-pricing#1.1"], ["renewal", "billing_date"]),
            ("Failed payment distinguished from a charge", f"My {plan} renewal on October {day} says failed. Did you take the money?",
             "get_payments showed a failed payment rather than a succeeded charge. The agent explained the "
             "recorded status without issuing a refund or claiming to retry the payment; the customer understood.",
             ["refund-policy#2.1", "agent-conduct#1.3"], ["failed_payment", "explanation"]),
            ("Pending downgrade billing explained", f"I requested a cheaper plan on October {day}, but my current plan still shows {plan}.",
             "The profile showed a pending downgrade with a future next_billing_date. The agent explained "
             "that the current plan remains until the next billing date and did not apply a second plan change.",
             ["plans-and-pricing#1.3"], ["pending_plan", "downgrade"]),
            ("Shared-plan total explained", f"We have {2 + variant % 5} people sharing family. Why is the October {day} bill 7.99 USD?",
             "The customer confused the approximate per-person cost with the account total. The agent explained "
             "that family costs 7.99 USD for up to six seats and approximately 1.33 USD each only with six participants.",
             ["plans-and-pricing#1.1"], ["shared_plan", "total_price"]),
            ("Previously refunded charge explained", f"Can you check the refund for my {price} USD charge from October {day}?",
             "The payment record already had status refunded and a refund timestamp. The agent reported "
             "the recorded refund without promising a bank arrival date or creating a second refund.",
             ["refund-policy#2.2", "agent-conduct#1.3"], ["already_refunded", "idempotency"]),
        )
        title, message, summary, refs, tags = templates[scenario]
        if scenario == 2:
            plan = "family" if variant % 2 else "duo"
            message = f"I requested individual on October {day}, but my current plan still shows {plan}."
        elif scenario == 3:
            plan = "family"
        add(title + f" (billing example {variant + 1})", "billing_issue", "billing_confusion", plan,
            OPENINGS[variant % 5] + " " + message, summary,
            [action("get_user_profile"), action("get_payments", limit=10)], "resolved_auto", refs,
            ["billing"] + tags)

    # Cover ordinary refunds, duplicates, the time boundary, and human-only amounts.
    for i in range(30):
        scenario, variant = i % 5, i // 5
        plan, price = PLANS[variant % len(PLANS)]
        payment_id = f"pay_case_{len(cases) + 1:04d}"
        reads = [action("get_payments", limit=10)]
        if scenario in (0, 1, 4):
            duplicate = scenario == 1
            age = 14 if scenario == 4 else 1 + variant
            amount = "20.00" if scenario == 4 else price
            reason, ref = ("double_charge", "refund-policy#2.2") if duplicate else ("other", "refund-policy#2.1")
            message = (f"I see two {amount} USD charges {2 + variant} minutes apart. Please refund the duplicate."
                       if duplicate else f"Please refund the {amount} USD payment made {age} days ago.")
            evidence = (f"Two succeeded {amount} USD payments belonged to the same customer and were "
                        f"{2 + variant} minutes apart; the second payment was {age} days old."
                        if duplicate else f"The succeeded, unrefunded payment was exactly {age} days old and worth {amount} USD.")
            add(
                f"{'Duplicate' if duplicate else 'Eligible'} refund of {amount} USD after {age} days",
                "refund_request", reason, plan, OPENINGS[variant % 5] + " " + message + f" Payment reference: {payment_id}.",
                evidence + " The amount was at or below 20.00 USD and inside the inclusive 14-day window. "
                "issue_refund succeeded; the agent cited the applicable policy and reported the refund.",
                reads + [action("issue_refund", payment_id=payment_id, reason_code=reason, policy_ref=ref)],
                "refunded", list(dict.fromkeys([ref, "refund-policy#2.1", "refund-policy#2.3"])),
                ["refund", "duplicate_charge" if duplicate else "eligible", "boundary" if scenario == 4 else "automatic"],
            )
        elif scenario == 2:
            age = 15 + variant * 3
            add(
                f"Refund window explained for a {age}-day-old charge", "refund_request", "other", plan,
                f"Please refund my {price} USD payment from {age} days ago.",
                f"The successful payment was {age} days old, outside the 14-day window. The agent explained "
                "that the automatic refund was unavailable and cited the policy; the customer accepted the explanation "
                "without a refund or escalation.",
                reads, "resolved_auto", ["refund-policy#2.1"], ["refund", "outside_window", "policy_explained"],
            )
        else:
            amount = ("20.01", "24.99", "29.99", "39.99", "47.97", "59.99")[variant]
            ref = "refund-policy#2.3"
            suggested = {"tool": "issue_refund", "args": {"payment_id": payment_id, "reason_code": "other",
                         "policy_ref": ref}, "rationale": "Payment is eligible by age but exceeds the automatic limit.",
                         "policy_ref": ref}
            add(
                f"Human review for a {amount} USD refund", "refund_request", "other", plan,
                f"I was charged {amount} USD {variant + 1} days ago. Can you refund this payment?",
                f"The succeeded, unrefunded other-kind payment was {variant + 1} days old. issue_refund returned "
                "LIMIT_EXCEEDED with needs_human true because the amount exceeded 20.00 USD. A high-priority ticket "
                "was created with a refund recommendation; the agent explained that the refund awaited human review.",
                reads + [action("issue_refund", payment_id=payment_id, reason_code="other", policy_ref=ref),
                         action("escalate_to_human", priority="high", category="refund_request",
                                summary=f"Review eligible {amount} USD payment {payment_id}; automatic limit exceeded.",
                                suggested_action=suggested)],
                "escalated", [ref, "escalation-matrix#1.1", "escalation-matrix#1.2"],
                ["refund", "over_limit", "human_review"],
            )

    for i in range(30):
        scenario, variant = i % 3, i // 3
        plan, _ = PLANS[variant % 4]
        device = ("iPhone", "Android phone", "tablet", "second phone", "replacement phone")[variant % 5]
        ref = f"known-issues#1.{scenario + 1}"
        if scenario == 0:
            message = f"My {2 + variant} downloaded albums will not play offline on my {device}."
            summary = ("The customer checked the signed-in account and free storage, reconnected, and downloaded a small "
                       "sample. The customer confirmed that the sample played offline; no account mutation was needed.")
            title, resolution, actions, tags = "Offline playback restored after download checks", "resolved_auto", [], ["offline", "downloads"]
        elif scenario == 1:
            message = f"Playback stops after about {variant + 1} minutes when my iPhone connects through CarPlay."
            title, tags = "CarPlay connection investigation", ["carplay", "playback"]
            if variant % 2 == 0:
                summary = ("While parked, the customer confirmed phone playback worked and reconnected the car link. "
                           "The customer confirmed CarPlay playback resumed; the agent made no outage claim.")
                resolution, actions = "resolved_auto", []
            else:
                summary = ("While parked, the customer confirmed phone playback worked but CarPlay still failed after "
                           "reconnection. The agent created a normal-priority technical ticket with connection details; repair remained pending.")
                resolution = "escalated"
                actions = [action("escalate_to_human", priority="normal", category="technical_issue",
                                  summary="Phone playback works; CarPlay interruptions persist after parked reconnection.",
                                  suggested_action=None)]
        else:
            message = f"I cannot find {variant + 1} playlists after signing in on my {device}."
            title, tags = "Missing playlists investigated", ["playlists", "library"]
            if variant % 2 == 0:
                summary = ("The customer confirmed the intended account and removed library filters. The playlists "
                           "became visible and the customer confirmed recovery of the view; no restoration tool was claimed.")
                resolution, actions = "resolved_auto", []
            else:
                summary = ("The account and library filters were correct, but playlists remained missing. The agent "
                           "recorded playlist names and disappearance details in a normal-priority ticket without promising restoration.")
                resolution = "escalated"
                actions = [action("escalate_to_human", priority="normal", category="technical_issue",
                                  summary="Playlists remain missing on the intended account with library filters cleared.",
                                  suggested_action=None)]
        refs = [ref] + (["escalation-matrix#1.1", "escalation-matrix#1.2"] if resolution == "escalated" else [])
        add(title + f" (device example {variant + 1})", "technical_issue", "technical_problems", plan,
            OPENINGS[variant % 5] + " " + message, summary, [action("get_user_profile")] + actions,
            resolution, refs, ["technical"] + tags)

    for i in range(20):
        scenario, variant = i % 4, i // 4
        old_plan, new_plan = (("individual", "duo"), ("duo", "family"),
                              ("family", "individual"), ("individual", "student"))[scenario]
        reason = "price_too_high" if scenario in (2, 3) else "other"
        eligibility = "The profile confirmed is_student equal to 1. " if scenario == 3 else ""
        timing = "at the next billing date as pending_plan" if scenario in (2, 3) else "immediately"
        add(
            f"Agreed change from {old_plan} to {new_plan}, request {variant + 1}", "plan_change", reason, old_plan,
            OPENINGS[variant] + f" I have been on {old_plan} for {variant + 2} months and want to switch to {new_plan}.",
            eligibility + f"After explaining the new price and seats, the agent obtained agreement to change plans. "
            f"change_plan succeeded and the agent reported that the change takes effect {timing}; no retention offer was consumed.",
            [action("get_user_profile"), action("change_plan", new_plan=new_plan, reason_code=reason)],
            "resolved_auto", ["plans-and-pricing#1.1", "plans-and-pricing#1.3"]
            + (["plans-and-pricing#1.2"] if scenario == 3 else []),
            ["plan_change", "downgrade" if scenario in (2, 3) else "upgrade", new_plan],
        )

    for i in range(10):
        if i < 5:
            add(
                f"Persistent login error after {i + 1} attempts", "account_access", "technical_problems", "individual",
                f"I have tried signing in {i + 1} times using my normal sign-in method, but the login error remains.",
                "The customer checked connectivity and the intended sign-in method but still could not sign in. "
                "The agent asked for the visible error, never requested passwords or codes, and created a high-priority "
                "account-access ticket; access restoration remained pending.",
                [action("escalate_to_human", priority="high", category="account_access",
                        summary="Persistent login error after basic connection and sign-in-method checks.", suggested_action=None)],
                "escalated", ["known-issues#1.4", "escalation-matrix#1.1", "escalation-matrix#1.2"],
                ["account_access", "login", "human_review"],
            )
        else:
            feature = ("playlist folders", "sleep timers", "larger text", "keyboard shortcuts", "collaborative playlists")[i - 5]
            add(
                f"Feature request for {feature}", "other", "other", "individual",
                f"Could you pass on my request for {feature}? I do not need to change my subscription.",
                f"The agent recorded feedback about {feature} in a low-priority ticket and explained that this was "
                "a handoff rather than a feature commitment. No release date or unsupported capability was promised.",
                [action("escalate_to_human", priority="low", category="other",
                        summary=f"Customer feedback: request for {feature}; no account change requested.", suggested_action=None)],
                "escalated", ["escalation-matrix#1.2", "agent-conduct#1.3"], ["other", "feedback", "feature_request"],
            )
    return cases


def main():
    cases = build_cases()
    output = ROOT / "cases.json"
    output.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {len(cases)} synthetic cases in {output}")


if __name__ == "__main__":
    main()

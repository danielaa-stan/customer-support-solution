"""Generate repeatable starting customer records for the fixed demo clock."""

import calendar
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEMO_NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
PRICES = {"individual": 4.99, "duo": 6.49, "family": 7.99, "student": 2.49}
BACKGROUND_USERS = 40
RANDOM_SEED = 20261031
ROOT = Path(__file__).resolve().parent


def iso(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def months_after(value, months):
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    return value.replace(year=year, month=month + 1,
                         day=min(value.day, calendar.monthrange(year, month + 1)[1]))


def payment(payment_id, user_id, amount, charged_at, status="succeeded"):
    return {"id": payment_id, "user_id": user_id, "amount": amount, "currency": "USD",
            "kind": "renewal", "status": status, "charged_at": iso(charged_at),
            "refunded_at": None, "refund_reason": None}


def customer(user_id, name, email, country, plan, started_at, next_billing_date,
             hours, last_active_at, devices, downloads, status="active"):
    return (
        {"id": user_id, "name": name, "email": email, "country": country,
         "is_student": int(plan == "student"), "created_at": iso(started_at)},
        {"id": "sub_" + user_id.removeprefix("u_"), "user_id": user_id,
         "plan": plan, "pending_plan": None, "status": status,
         "price_amount": PRICES[plan], "price_currency": "USD", "started_at": iso(started_at),
         "next_billing_date": iso(next_billing_date) if next_billing_date else None,
         "paused_until": None, "cancel_at": None, "discount_percent": 0, "discount_payments_left": 0},
        {"user_id": user_id, "listening_hours_30d": hours, "last_active_at": iso(last_active_at),
         "devices_count": devices, "offline_downloads": downloads},
    )


def build_seed():
    rng = random.Random(RANDOM_SEED)
    seed = {table: [] for table in ("users", "subscriptions", "payments", "usage_stats",
                                    "retention_offers_used", "tickets", "pending_actions", "audit_log")}

    def add_customer(*args, **kwargs):
        user, subscription, usage = customer(*args, **kwargs)
        seed["users"].append(user)
        seed["subscriptions"].append(subscription)
        seed["usage_stats"].append(usage)
        return subscription, usage

    add_customer("u_demo_family", "Olena Koval", "olena@example.com", "UA", "individual",
                 datetime(2026, 2, 10, 9, tzinfo=timezone.utc), datetime(2026, 11, 10, 9, tzinfo=timezone.utc),
                 41.5, datetime(2026, 10, 30, 20, 10, tzinfo=timezone.utc), 2, 120)
    for month in (8, 9, 10):
        payment_id = "pay_0001" if month == 10 else f"pay_demo_family_{month:02d}"
        seed["payments"].append(payment(payment_id, "u_demo_family", PRICES["individual"],
                                        datetime(2026, month, 10, 9, tzinfo=timezone.utc)))

    add_customer("u_demo_double", "Daniel Reed", "daniel.reed@example.com", "GB", "individual",
                 datetime(2026, 5, 29, 8, tzinfo=timezone.utc), datetime(2026, 11, 29, 8, tzinfo=timezone.utc),
                 18.3, datetime(2026, 10, 30, 16, tzinfo=timezone.utc), 1, 24)
    for payment_id, charged_at in (
        ("pay_demo_dbl_prev", datetime(2026, 9, 29, 8, tzinfo=timezone.utc)),
        ("pay_demo_dbl_1", datetime(2026, 10, 29, 8, tzinfo=timezone.utc)),
        ("pay_demo_dbl_2", datetime(2026, 10, 29, 8, 2, tzinfo=timezone.utc)),
    ):
        seed["payments"].append(payment(payment_id, "u_demo_double", PRICES["individual"], charged_at))

    add_customer("u_demo_cancel", "Maya Brooks", "maya.brooks@example.com", "US", "individual",
                 datetime(2025, 9, 1, 9, tzinfo=timezone.utc), datetime(2026, 11, 1, 9, tzinfo=timezone.utc),
                 1.2, datetime(2026, 9, 20, 18, tzinfo=timezone.utc), 1, 0)
    for month in (8, 9, 10):
        seed["payments"].append(payment(f"pay_demo_cancel_{month:02d}", "u_demo_cancel", PRICES["individual"],
                                        datetime(2026, month, 1, 9, tzinfo=timezone.utc)))

    first_names = ("Alex", "Jordan", "Taylor", "Morgan", "Casey", "Robin", "Jamie", "Sam")
    last_names = ("Parker", "Evans", "Chen", "Patel", "Rivera")
    countries = ("UA", "GB", "US", "DE", "PL", "CA")
    plans = tuple(PRICES)
    statuses = ("active", "paused", "canceled", "past_due")
    for index in range(BACKGROUND_USERS):
        number = index + 1
        user_id = f"u_background_{number:03d}"
        plan, status = plans[index % 4], statuses[(index // 4) % 4]
        tenure = rng.randint(1, 24)
        charged_at = DEMO_NOW.replace(day=1 + index % 28, hour=9)
        started_at = months_after(charged_at, -tenure)
        latest_activity = DEMO_NOW - timedelta(days=rng.randint(0, 29), hours=rng.randint(0, 12))
        name = f"{first_names[index % len(first_names)]} {last_names[index // len(first_names)]}"
        subscription, usage = add_customer(
            user_id, name, f"customer{number:03d}@example.com", countries[index % len(countries)], plan,
            started_at, months_after(charged_at, 1) if status != "canceled" else None,
            round(rng.uniform(0.2, 75), 1), latest_activity, rng.randint(1, 4), rng.randint(0, 150), status,
        )
        if status == "paused":
            subscription["paused_until"] = iso(months_after(DEMO_NOW, 2))
            subscription["next_billing_date"] = subscription["paused_until"]
        elif status == "canceled":
            subscription["cancel_at"] = iso(charged_at + timedelta(days=1))
            usage["last_active_at"] = iso(min(latest_activity, charged_at))
            if DEMO_NOW - min(latest_activity, charged_at) > timedelta(days=30):
                usage["listening_hours_30d"] = 0
        elif status == "active" and plan == "family" and index % 3 == 0:
            subscription["pending_plan"] = "individual"

        for back in reversed(range(min(3, tenure + 1))):
            current = payment(f"pay_background_{number:03d}_{back}", user_id, PRICES[plan],
                              months_after(charged_at, -back),
                              "failed" if status == "past_due" and back == 0 else "succeeded")
            # Historical refunds provide variety without changing demo starting states.
            if status == "canceled" and back == 0 and index % 2 == 0:
                current.update(status="refunded", refunded_at=iso(charged_at + timedelta(hours=2)),
                               refund_reason="other")
            seed["payments"].append(current)

        if status == "active" and plan != "student" and tenure >= 3 and index % 5 == 0:
            seed["retention_offers_used"].append({"user_id": user_id, "offer_code": "discount_50_3m",
                                                   "applied_at": iso(DEMO_NOW - timedelta(days=1))})
            subscription.update(discount_percent=50, discount_payments_left=3)
        elif tenure >= 14 and index % 7 == 0:
            seed["retention_offers_used"].append({"user_id": user_id, "offer_code": "free_month_1",
                                                   "applied_at": iso(DEMO_NOW - timedelta(days=400))})
    return seed


def main():
    seed = build_seed()
    output = ROOT / "seed" / "seed.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {len(seed['users'])} customers and {len(seed['payments'])} payments in {output}")


if __name__ == "__main__":
    main()

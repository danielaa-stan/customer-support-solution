using System.Text.Json;
using SupportServer.Tools;

namespace SupportServer.Tests;

/// <summary>End-to-end tests for demo scenarios 1 and 3, pause, plan changes, confirmation flow and escalation.</summary>
public sealed class SubscriptionFlowTests : IDisposable
{
    private readonly TestHarness _h = new();
    private readonly SessionTools _session;
    private readonly OfferTools _offers;
    private readonly SubscriptionTools _subscriptions;
    private readonly ActionTools _actions;
    private readonly EscalationTools _escalation;
    private readonly PaymentTools _payments;
    private readonly AccountTools _account;

    public SubscriptionFlowTests()
    {
        _session = _h.Tools<SessionTools>();
        _offers = _h.Tools<OfferTools>();
        _subscriptions = _h.Tools<SubscriptionTools>();
        _actions = _h.Tools<ActionTools>();
        _escalation = _h.Tools<EscalationTools>();
        _payments = _h.Tools<PaymentTools>();
        _account = _h.Tools<AccountTools>();
    }

    public void Dispose() => _h.Dispose();

    public record AuditRow(string tool, string result_status, string autonomy_level);

    private void Use(string userId, int turn = 1)
    {
        var result = TestHarness.Parse(_session.SetContext("ses_test", userId, turn));
        Assert.True(result.GetProperty("ok").GetBoolean(), result.ToString());
    }

    private static string ErrorCode(JsonElement response) => response.GetProperty("error").GetProperty("code").GetString()!;

    private static JsonElement Parse(string json) => TestHarness.Parse(json);

    private static string[] OfferCodes(JsonElement response) =>
        response.GetProperty("data").GetProperty("offers").EnumerateArray()
            .Select(o => o.GetProperty("code").GetString()!).ToArray();

    // ---- Scenario 1: price objection, retention offer

    [Fact]
    public void Scenario1_discount_is_applied_once_and_then_blocked_by_cooldown()
    {
        Use("u_demo_family");
        Assert.Equal(new[] { "discount_50_3m" }, OfferCodes(Parse(_offers.GetAvailableOffers())));

        var applied = Parse(_offers.ApplyRetentionOffer("discount_50_3m", "price_too_high"));
        Assert.True(applied.GetProperty("ok").GetBoolean(), applied.ToString());
        Assert.Equal(50, applied.GetProperty("data").GetProperty("discount_percent").GetInt32());

        Assert.Equal(50, _h.Query<long>("SELECT discount_percent FROM subscriptions WHERE user_id = 'u_demo_family'").Single());
        Assert.Equal(3, _h.Query<long>("SELECT discount_payments_left FROM subscriptions WHERE user_id = 'u_demo_family'").Single());

        var profile = Parse(_account.GetUserProfile()).GetProperty("data");
        Assert.True(profile.GetProperty("flags").GetProperty("retention_offer_used_in_cooldown").GetBoolean());

        var second = Parse(_offers.ApplyRetentionOffer("discount_50_3m", "price_too_high"));
        Assert.Equal("NOT_ELIGIBLE", ErrorCode(second));
        Assert.Equal("retention-rules#1.2", second.GetProperty("error").GetProperty("policy_ref").GetString());
        Assert.Empty(OfferCodes(Parse(_offers.GetAvailableOffers())));
    }

    [Fact]
    public void Offer_the_customer_is_not_eligible_for_is_rejected()
    {
        Use("u_demo_family"); // 8 months of tenure: no free month yet
        var result = Parse(_offers.ApplyRetentionOffer("free_month_1", "price_too_high"));

        Assert.Equal("denied", result.GetProperty("status").GetString());
        Assert.Equal("NOT_ELIGIBLE", ErrorCode(result));
    }

    [Fact]
    public void Free_month_moves_the_next_billing_date_by_one_month()
    {
        Use("u_demo_cancel");
        var result = Parse(_offers.ApplyRetentionOffer("free_month_1", "price_too_high"));

        Assert.True(result.GetProperty("ok").GetBoolean(), result.ToString());
        Assert.Equal("2026-12-25T10:00:00Z", _h.Query<string>("SELECT next_billing_date FROM subscriptions WHERE user_id = 'u_demo_cancel'").Single());
    }

    // ---- Pause

    [Fact]
    public void Pause_sets_the_paused_state_and_cannot_be_repeated()
    {
        Use("u_demo_cancel");
        var paused = Parse(_subscriptions.PauseSubscription(3, "low_usage"));

        Assert.True(paused.GetProperty("ok").GetBoolean(), paused.ToString());
        Assert.Equal("2027-01-31T12:00:00Z", paused.GetProperty("data").GetProperty("paused_until").GetString());
        Assert.Equal("paused", _h.Query<string>("SELECT status FROM subscriptions WHERE user_id = 'u_demo_cancel'").Single());

        Assert.Equal("ALREADY_DONE", ErrorCode(Parse(_subscriptions.PauseSubscription(1, "low_usage"))));
    }

    [Fact]
    public void Pause_length_is_validated()
    {
        Use("u_demo_family");

        var tooLong = Parse(_subscriptions.PauseSubscription(4, "temporary_break"));
        Assert.Equal("POLICY_DENIED", ErrorCode(tooLong));
        Assert.Equal("pause-policy#1.1", tooLong.GetProperty("error").GetProperty("policy_ref").GetString());

        Assert.Equal("INVALID_ARGUMENT", ErrorCode(Parse(_subscriptions.PauseSubscription(0, "temporary_break"))));
    }

    // ---- Plan changes

    [Fact]
    public void Upgrade_is_immediate_and_downgrade_is_scheduled()
    {
        Use("u_demo_family");

        var upgrade = Parse(_subscriptions.ChangePlan("family", "price_too_high"));
        Assert.Equal("immediately", upgrade.GetProperty("data").GetProperty("effective").GetString());
        Assert.Equal(15.99, upgrade.GetProperty("data").GetProperty("new_price_amount").GetDouble());
        Assert.Equal("family", _h.Query<string>("SELECT plan FROM subscriptions WHERE user_id = 'u_demo_family'").Single());

        var downgrade = Parse(_subscriptions.ChangePlan("duo", "price_too_high"));
        Assert.Equal("next_billing_date", downgrade.GetProperty("data").GetProperty("effective").GetString());
        Assert.Equal("duo", _h.Query<string>("SELECT pending_plan FROM subscriptions WHERE user_id = 'u_demo_family'").Single());
        Assert.Equal("family", _h.Query<string>("SELECT plan FROM subscriptions WHERE user_id = 'u_demo_family'").Single());

        Assert.Equal("ALREADY_DONE", ErrorCode(Parse(_subscriptions.ChangePlan("duo", "price_too_high"))));

        // Going back to the current plan cancels the scheduled downgrade.
        var back = Parse(_subscriptions.ChangePlan("family", "price_too_high"));
        Assert.True(back.GetProperty("ok").GetBoolean(), back.ToString());
        Assert.Null(_h.Query<string?>("SELECT pending_plan FROM subscriptions WHERE user_id = 'u_demo_family'").Single());
    }

    [Fact]
    public void Student_plan_requires_student_status()
    {
        Use("u_demo_family");
        var result = Parse(_subscriptions.ChangePlan("student", "price_too_high"));

        Assert.Equal("POLICY_DENIED", ErrorCode(result));
        Assert.Equal("plans-and-pricing#1.2", result.GetProperty("error").GetProperty("policy_ref").GetString());
    }

    // ---- Scenario 3: honest cancellation with confirmation

    [Fact]
    public void Scenario3_cancellation_needs_confirmation_in_a_new_customer_turn()
    {
        Use("u_demo_cancel", 1);

        var proposal = Parse(_subscriptions.CancelSubscription("low_usage"));
        Assert.True(proposal.GetProperty("ok").GetBoolean(), proposal.ToString());
        Assert.Equal("pending_confirmation", proposal.GetProperty("status").GetString());
        var pendingId = proposal.GetProperty("data").GetProperty("pending_action_id").GetString()!;
        Assert.Null(_h.Query<string?>("SELECT cancel_at FROM subscriptions WHERE user_id = 'u_demo_cancel'").Single());

        // Same customer turn: the agent cannot confirm its own proposal.
        var tooEarly = Parse(_actions.ConfirmAction(pendingId));
        Assert.Equal("CONFIRMATION_INVALID", ErrorCode(tooEarly));

        // The customer answers "yes" in a new message.
        Use("u_demo_cancel", 2);
        var confirmed = Parse(_actions.ConfirmAction(pendingId));
        Assert.True(confirmed.GetProperty("ok").GetBoolean(), confirmed.ToString());
        Assert.Equal("active", confirmed.GetProperty("data").GetProperty("status").GetString());
        Assert.Equal("2026-11-25T10:00:00Z", confirmed.GetProperty("data").GetProperty("cancel_at").GetString());
        Assert.Equal("2026-11-25T10:00:00Z", _h.Query<string>("SELECT cancel_at FROM subscriptions WHERE user_id = 'u_demo_cancel'").Single());
        Assert.Null(_h.Query<string?>("SELECT next_billing_date FROM subscriptions WHERE user_id = 'u_demo_cancel'").Single());

        Assert.Equal("ALREADY_DONE", ErrorCode(Parse(_actions.ConfirmAction(pendingId))));
        Assert.Equal("ALREADY_DONE", ErrorCode(Parse(_subscriptions.CancelSubscription("low_usage"))));

        var audit = _h.Query<AuditRow>("SELECT tool, result_status, autonomy_level FROM audit_log ORDER BY id");
        Assert.Equal(
            new[]
            {
                "cancel_subscription:pending_confirmation:confirm",
                "confirm_action:denied:confirm",
                "confirm_action:done:confirm",
                "confirm_action:denied:confirm",
                "cancel_subscription:denied:confirm",
            },
            audit.Select(a => $"{a.tool}:{a.result_status}:{a.autonomy_level}").ToArray());
    }

    [Fact]
    public void Repeating_the_same_proposal_returns_the_same_pending_action()
    {
        Use("u_demo_cancel");
        var first = Parse(_subscriptions.CancelSubscription("low_usage")).GetProperty("data").GetProperty("pending_action_id").GetString();
        var second = Parse(_subscriptions.CancelSubscription("low_usage")).GetProperty("data").GetProperty("pending_action_id").GetString();

        Assert.Equal(first, second);
        Assert.Equal(1, _h.Query<long>("SELECT COUNT(1) FROM pending_actions").Single());
    }

    [Fact]
    public void Rejected_proposal_cannot_be_confirmed_later()
    {
        Use("u_demo_cancel", 1);
        var pendingId = Parse(_subscriptions.CancelSubscription("low_usage")).GetProperty("data").GetProperty("pending_action_id").GetString()!;

        var rejected = Parse(_actions.RejectAction(pendingId));
        Assert.True(rejected.GetProperty("ok").GetBoolean(), rejected.ToString());

        Use("u_demo_cancel", 2);
        Assert.Equal("CONFIRMATION_INVALID", ErrorCode(Parse(_actions.ConfirmAction(pendingId))));
        Assert.Null(_h.Query<string?>("SELECT cancel_at FROM subscriptions WHERE user_id = 'u_demo_cancel'").Single());
    }

    [Fact]
    public void Immediate_cancellation_ends_the_subscription_now()
    {
        Use("u_demo_cancel", 1);
        var pendingId = Parse(_subscriptions.CancelSubscription("low_usage", "immediate")).GetProperty("data").GetProperty("pending_action_id").GetString()!;

        Use("u_demo_cancel", 2);
        var confirmed = Parse(_actions.ConfirmAction(pendingId));

        Assert.Equal("canceled", confirmed.GetProperty("data").GetProperty("status").GetString());
        Assert.Equal("canceled", _h.Query<string>("SELECT status FROM subscriptions WHERE user_id = 'u_demo_cancel'").Single());
    }

    [Fact]
    public void Unknown_pending_action_is_not_found()
    {
        Use("u_demo_cancel", 2);
        Assert.Equal("NOT_FOUND", ErrorCode(Parse(_actions.ConfirmAction("pa_nope"))));
    }

    // ---- Bonus scenario: refund above the limit is escalated with a recommendation

    [Fact]
    public void Large_refund_is_escalated_with_a_suggested_action()
    {
        Use("u_demo_escalate");
        var refund = Parse(_payments.IssueRefund("pay_demo_big", "other", "refund-policy#2.3"));
        Assert.True(refund.GetProperty("needs_human").GetBoolean());

        using var suggestion = JsonDocument.Parse(
            """{"tool":"issue_refund","args":{"payment_id":"pay_demo_big"},"rationale":"Charged 3 months by mistake","policy_ref":"refund-policy#2.3"}""");
        var escalated = Parse(_escalation.EscalateToHuman("high", "refund_request", "Customer was charged for 3 months by mistake.", suggestion.RootElement.Clone()));

        Assert.True(escalated.GetProperty("ok").GetBoolean(), escalated.ToString());
        var ticketId = escalated.GetProperty("data").GetProperty("ticket_id").GetString()!;
        Assert.Equal("refund_request", _h.Query<string>("SELECT category FROM tickets WHERE id = @ticketId", new { ticketId }).Single());
        Assert.Contains("issue_refund", _h.Query<string>("SELECT suggested_action_json FROM tickets WHERE id = @ticketId", new { ticketId }).Single());
    }

    [Fact]
    public void Escalation_works_without_a_suggestion_and_validates_input()
    {
        Use("u_demo_escalate");

        Assert.True(Parse(_escalation.EscalateToHuman("normal", "technical_issue", "Offline mode does not work.")).GetProperty("ok").GetBoolean());
        Assert.Equal("INVALID_ARGUMENT", ErrorCode(Parse(_escalation.EscalateToHuman("whenever", "technical_issue", "x"))));
        Assert.Equal("INVALID_ARGUMENT", ErrorCode(Parse(_escalation.EscalateToHuman("normal", "gossip", "x"))));

        using var bad = JsonDocument.Parse("""{"tool":"delete_everything"}""");
        Assert.Equal("INVALID_ARGUMENT", ErrorCode(Parse(_escalation.EscalateToHuman("normal", "other", "x", bad.RootElement.Clone()))));
    }
}

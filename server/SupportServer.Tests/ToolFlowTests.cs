using System.Text.Json;
using SupportServer.Tools;

namespace SupportServer.Tests;

/// <summary>Наскрізні тести: інструмент MCP -> guard -> сервіс -> БД -> audit_log (на dev-seed).</summary>
public sealed class ToolFlowTests : IDisposable
{
    private readonly TestHarness _h = new();
    private readonly SessionTools _session;
    private readonly AccountTools _account;
    private readonly PaymentTools _payments;

    public ToolFlowTests()
    {
        _session = _h.Tools<SessionTools>();
        _account = _h.Tools<AccountTools>();
        _payments = _h.Tools<PaymentTools>();
    }

    public void Dispose() => _h.Dispose();

    private void Use(string userId)
    {
        var result = TestHarness.Parse(_session.SetContext("ses_test", userId, 1));
        Assert.True(result.GetProperty("ok").GetBoolean());
    }

    private record AuditRow(string tool, string result_status, string autonomy_level, string? error_code, string? policy_ref, string? user_id);

    [Fact]
    public void Tool_without_context_returns_NO_CONTEXT()
    {
        var result = TestHarness.Parse(_account.GetUserProfile());
        Assert.False(result.GetProperty("ok").GetBoolean());
        Assert.Equal("error", result.GetProperty("status").GetString());
        Assert.Equal("NO_CONTEXT", result.GetProperty("error").GetProperty("code").GetString());
    }

    [Fact]
    public void Set_context_for_unknown_user_returns_NOT_FOUND()
    {
        var result = TestHarness.Parse(_session.SetContext("ses_test", "u_nobody", 1));
        Assert.False(result.GetProperty("ok").GetBoolean());
        Assert.Equal("NOT_FOUND", result.GetProperty("error").GetProperty("code").GetString());
    }

    [Fact]
    public void Profile_returns_subscription_usage_and_tenure()
    {
        Use("u_demo_family");
        var data = TestHarness.Parse(_account.GetUserProfile()).GetProperty("data");

        Assert.Equal("individual", data.GetProperty("subscription").GetProperty("plan").GetString());
        Assert.Equal(8, data.GetProperty("subscription").GetProperty("tenure_months").GetInt32());
        Assert.Equal(41.5, data.GetProperty("usage").GetProperty("listening_hours_30d").GetDouble());
        Assert.False(data.GetProperty("flags").GetProperty("retention_offer_used_in_cooldown").GetBoolean());
    }

    [Fact]
    public void Payments_flag_the_duplicate_charge()
    {
        Use("u_demo_double");
        var data = TestHarness.Parse(_payments.GetPayments()).GetProperty("data");

        var duplicate = Assert.Single(data.GetProperty("duplicate_charge_candidates").EnumerateArray());
        Assert.Equal("pay_demo_dbl_2", duplicate.GetProperty("payment_id").GetString());
        Assert.Equal("pay_demo_dbl_1", duplicate.GetProperty("duplicate_of").GetString());
    }

    [Fact]
    public void Scenario2_double_charge_is_refunded_once_and_audited()
    {
        Use("u_demo_double");

        var first = TestHarness.Parse(_payments.IssueRefund("pay_demo_dbl_2", "double_charge", "refund-policy#2.2"));
        Assert.True(first.GetProperty("ok").GetBoolean());
        Assert.Equal("done", first.GetProperty("status").GetString());
        Assert.Equal(9.99, first.GetProperty("data").GetProperty("refunded_amount").GetDouble());
        Assert.True(first.GetProperty("audit_id").GetInt64() > 0);

        var second = TestHarness.Parse(_payments.IssueRefund("pay_demo_dbl_2", "double_charge", "refund-policy#2.2"));
        Assert.False(second.GetProperty("ok").GetBoolean());
        Assert.Equal("denied", second.GetProperty("status").GetString());
        Assert.Equal("ALREADY_DONE", second.GetProperty("error").GetProperty("code").GetString());

        var audit = _h.Query<AuditRow>("SELECT tool, result_status, autonomy_level, error_code, policy_ref, user_id FROM audit_log WHERE tool = 'issue_refund' ORDER BY id");
        Assert.Equal(new[] { "done", "denied" }, audit.Select(a => a.result_status).ToArray());
        Assert.All(audit, a => Assert.Equal("u_demo_double", a.user_id));
        Assert.Equal("refunded", _h.Query<string>("SELECT status FROM payments WHERE id = 'pay_demo_dbl_2'").Single());
    }

    [Fact]
    public void Cannot_refund_another_users_payment()
    {
        Use("u_demo_family");
        var result = TestHarness.Parse(_payments.IssueRefund("pay_demo_dbl_2", "double_charge", "refund-policy#2.2"));

        Assert.Equal("NOT_FOUND", result.GetProperty("error").GetProperty("code").GetString());
        Assert.Equal("succeeded", _h.Query<string>("SELECT status FROM payments WHERE id = 'pay_demo_dbl_2'").Single());
    }

    [Fact]
    public void Refund_above_auto_limit_needs_human()
    {
        Use("u_demo_escalate");
        var result = TestHarness.Parse(_payments.IssueRefund("pay_demo_big", "other", "refund-policy#2.3"));

        Assert.Equal("needs_human", result.GetProperty("status").GetString());
        Assert.True(result.GetProperty("needs_human").GetBoolean());
        Assert.Equal("LIMIT_EXCEEDED", result.GetProperty("error").GetProperty("code").GetString());

        var audit = _h.Query<AuditRow>("SELECT tool, result_status, autonomy_level, error_code, policy_ref, user_id FROM audit_log").Single();
        Assert.Equal("human_only", audit.autonomy_level);
        Assert.Equal("succeeded", _h.Query<string>("SELECT status FROM payments WHERE id = 'pay_demo_big'").Single());
    }

    [Fact]
    public void Refund_outside_14_day_window_is_denied()
    {
        Use("u_demo_family");
        var result = TestHarness.Parse(_payments.IssueRefund("pay_f_1", "price_too_high", "refund-policy#2.1"));

        Assert.Equal("denied", result.GetProperty("status").GetString());
        Assert.Equal("POLICY_DENIED", result.GetProperty("error").GetProperty("code").GetString());
        Assert.Equal("refund-policy#2.1", result.GetProperty("error").GetProperty("policy_ref").GetString());
    }

    [Fact]
    public void False_double_charge_claim_is_rejected()
    {
        Use("u_demo_cancel");
        var result = TestHarness.Parse(_payments.IssueRefund("pay_c_1", "double_charge", "refund-policy#2.2"));

        Assert.Equal("POLICY_DENIED", result.GetProperty("error").GetProperty("code").GetString());
        Assert.Equal("succeeded", _h.Query<string>("SELECT status FROM payments WHERE id = 'pay_c_1'").Single());
    }

    [Fact]
    public void Malformed_policy_ref_is_rejected()
    {
        Use("u_demo_double");
        var result = TestHarness.Parse(_payments.IssueRefund("pay_demo_dbl_2", "double_charge", "the policy says so"));

        Assert.Equal("error", result.GetProperty("status").GetString());
        Assert.Equal("INVALID_ARGUMENT", result.GetProperty("error").GetProperty("code").GetString());
    }
}

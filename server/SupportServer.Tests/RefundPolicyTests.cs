using SupportServer.Config;
using SupportServer.Domain;
using SupportServer.Domain.Policies;

namespace SupportServer.Tests;

public class RefundPolicyTests
{
    private static readonly DateTimeOffset Now = BusinessRules.DefaultDemoNow; // 2026-10-31T12:00:00Z

    private static Payment Pay(double amount = 9.99, string status = "succeeded", string chargedAt = "2026-10-25T12:00:00Z") =>
        new() { Id = "pay_x", UserId = "u", Amount = amount, Currency = "USD", Kind = "renewal", Status = status, ChargedAt = chargedAt };

    [Fact]
    public void Recent_small_payment_is_allowed() =>
        Assert.Equal(RefundVerdict.Allowed, RefundPolicy.Evaluate(Pay(), Now).Verdict);

    [Fact]
    public void Exactly_14_days_old_is_still_allowed() =>
        Assert.Equal(RefundVerdict.Allowed, RefundPolicy.Evaluate(Pay(chargedAt: "2026-10-17T12:00:00Z"), Now).Verdict);

    [Fact]
    public void Older_than_14_days_is_denied_with_policy_ref()
    {
        var decision = RefundPolicy.Evaluate(Pay(chargedAt: "2026-10-17T11:59:59Z"), Now);
        Assert.Equal(RefundVerdict.WindowExpired, decision.Verdict);
        Assert.Equal("refund-policy#2.1", decision.PolicyRef);
    }

    [Fact]
    public void Exactly_at_auto_limit_is_allowed() =>
        Assert.Equal(RefundVerdict.Allowed, RefundPolicy.Evaluate(Pay(amount: 20.00), Now).Verdict);

    [Fact]
    public void Above_auto_limit_requires_human()
    {
        var decision = RefundPolicy.Evaluate(Pay(amount: 20.01), Now);
        Assert.Equal(RefundVerdict.OverAutoLimit, decision.Verdict);
        Assert.Equal("refund-policy#2.3", decision.PolicyRef);
    }

    [Fact]
    public void Already_refunded_payment_is_reported() =>
        Assert.Equal(RefundVerdict.AlreadyRefunded, RefundPolicy.Evaluate(Pay(status: "refunded"), Now).Verdict);

    [Fact]
    public void Failed_payment_is_not_refundable() =>
        Assert.Equal(RefundVerdict.NotRefundable, RefundPolicy.Evaluate(Pay(status: "failed"), Now).Verdict);
}

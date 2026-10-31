using SupportServer.Config;
using SupportServer.Domain;
using SupportServer.Domain.Policies;

namespace SupportServer.Tests;

public class OfferEligibilityTests
{
    private static readonly DateTimeOffset Now = BusinessRules.DefaultDemoNow; // 2026-10-31

    private static UserAccount Account(string startedAt, string plan = "individual", string status = "active",
        string? cancelAt = null, string? nextBilling = "2026-11-10T09:00:00Z") =>
        new(new User { Id = "u" },
            new Subscription
            {
                Id = "s", UserId = "u", Plan = plan, Status = status, StartedAt = startedAt,
                CancelAt = cancelAt, NextBillingDate = nextBilling,
            },
            new UsageStats { UserId = "u" });

    private static string[] Codes(UserAccount account, bool usedInCooldown = false) =>
        OfferEligibility.GetEligible(account, usedInCooldown, Now).Select(o => o.Code).ToArray();

    [Fact]
    public void Eight_months_of_tenure_gets_only_the_discount() =>
        Assert.Equal(new[] { "discount_50_3m" }, Codes(Account("2026-02-10T09:00:00Z")));

    [Fact]
    public void Fourteen_months_of_tenure_gets_both_offers() =>
        Assert.Equal(new[] { "discount_50_3m", "free_month_1" }, Codes(Account("2025-08-25T10:00:00Z")));

    [Fact]
    public void Two_months_of_tenure_gets_nothing() =>
        Assert.Empty(Codes(Account("2026-08-31T09:00:00Z")));

    [Fact]
    public void Student_plan_cannot_get_the_discount() =>
        Assert.Equal(new[] { "free_month_1" }, Codes(Account("2025-08-25T10:00:00Z", plan: "student")));

    [Fact]
    public void Offer_used_in_cooldown_blocks_everything() =>
        Assert.Empty(Codes(Account("2025-08-25T10:00:00Z"), usedInCooldown: true));

    [Fact]
    public void Scheduled_cancellation_or_pause_blocks_offers()
    {
        Assert.Empty(Codes(Account("2025-08-25T10:00:00Z", cancelAt: "2026-11-10T09:00:00Z")));
        Assert.Empty(Codes(Account("2025-08-25T10:00:00Z", status: "paused")));
    }
}

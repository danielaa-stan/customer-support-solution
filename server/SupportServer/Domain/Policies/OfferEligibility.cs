using SupportServer.Config;

namespace SupportServer.Domain.Policies;

public sealed record Offer(string Code, string Title, string Description, object Details);

public static class OfferCatalog
{
    public const string Discount50For3Months = "discount_50_3m";
    public const string FreeMonth = "free_month_1";

    public static bool IsKnown(string? code) => code is Discount50For3Months or FreeMonth;
}

/// <summary>
/// Pure eligibility rules for retention offers (contracts/04-business-rules.md).
/// The server decides who may get an offer; the agent never invents one.
/// </summary>
public static class OfferEligibility
{
    public static IReadOnlyList<Offer> GetEligible(UserAccount account, bool offerUsedInCooldown, DateTimeOffset now)
    {
        var sub = account.Subscription;
        var offers = new List<Offer>();

        var isActive = sub.Status == "active" && sub.CancelAt is null;
        if (!isActive || offerUsedInCooldown || sub.NextBillingDate is null)
            return offers;

        var tenureMonths = Iso.WholeMonthsBetween(Iso.Parse(sub.StartedAt), now);

        if (tenureMonths >= 3 && sub.Plan != "student")
        {
            offers.Add(new Offer(
                OfferCatalog.Discount50For3Months,
                "50% off for 3 months",
                "Half price on the next 3 payments.",
                new { discount_percent = 50, payments = 3 }));
        }

        if (tenureMonths >= 12)
        {
            offers.Add(new Offer(
                OfferCatalog.FreeMonth,
                "One free month",
                "The next billing date moves forward by one month.",
                new { free_months = 1 }));
        }

        return offers;
    }

    public static string DenialRef(bool offerUsedInCooldown) =>
        offerUsedInCooldown ? PolicyRefs.OfferCooldown : PolicyRefs.OfferEligibility;
}

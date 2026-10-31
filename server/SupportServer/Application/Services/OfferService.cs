using SupportServer.Application.Ports;
using SupportServer.Config;
using SupportServer.Domain;
using SupportServer.Domain.Policies;

namespace SupportServer.Application.Services;

public sealed class OfferService(IBillingProvider billing, IClock clock)
{
    public ToolOutcome GetAvailableOffers(ToolContext ctx)
    {
        var account = billing.GetAccount(ctx.UserId);
        if (account is null) return Validation.AccountNotFound();

        var now = clock.UtcNow;
        var offers = OfferEligibility.GetEligible(account, OfferUsedInCooldown(ctx.UserId, now), now);

        return ToolOutcome.Done(new
        {
            offers = offers.Select(o => new { code = o.Code, title = o.Title, description = o.Description, details = o.Details }).ToList(),
        });
    }

    public ToolOutcome ApplyRetentionOffer(ToolContext ctx, string offerCode, string reasonCode)
    {
        if (Validation.CheckReason(reasonCode) is { } invalid) return invalid;
        if (string.IsNullOrWhiteSpace(offerCode))
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument, "offer_code is required.", reasonCode);

        var account = billing.GetAccount(ctx.UserId);
        if (account is null) return Validation.AccountNotFound();

        var now = clock.UtcNow;
        var usedInCooldown = OfferUsedInCooldown(ctx.UserId, now);
        var eligible = OfferEligibility.GetEligible(account, usedInCooldown, now);

        if (eligible.All(o => o.Code != offerCode))
        {
            return ToolOutcome.Denied(ErrorCodes.NotEligible,
                "This offer is not available to the customer. Use only offers returned by get_available_offers.",
                OfferEligibility.DenialRef(usedInCooldown), reasonCode);
        }

        switch (offerCode)
        {
            case OfferCatalog.Discount50For3Months:
                if (!billing.ApplyDiscountOffer(ctx.UserId, offerCode, 50, 3, now)) return StateChanged(reasonCode);
                return ToolOutcome.Done(
                    new { offer_code = offerCode, discount_percent = 50, discount_payments_left = 3 },
                    reasonCode, PolicyRefs.OfferEligibility);

            case OfferCatalog.FreeMonth:
                // Eligibility guarantees a next billing date exists.
                var newDate = Iso.Parse(account.Subscription.NextBillingDate!).AddMonths(1);
                if (!billing.GrantFreeMonth(ctx.UserId, offerCode, newDate, now)) return StateChanged(reasonCode);
                return ToolOutcome.Done(
                    new { offer_code = offerCode, free_months = 1, next_billing_date = Iso.Format(newDate) },
                    reasonCode, PolicyRefs.OfferEligibility);

            default:
                return ToolOutcome.Fail(ErrorCodes.Internal, "Unhandled offer code.", reasonCode);
        }
    }

    private bool OfferUsedInCooldown(string userId, DateTimeOffset now) =>
        billing.HasRetentionOfferSince(userId, now.AddMonths(-BusinessRules.RetentionCooldownMonths));

    private static ToolOutcome StateChanged(string reasonCode) =>
        ToolOutcome.Denied(ErrorCodes.PolicyDenied, "The subscription state changed, the offer cannot be applied.", reasonCode: reasonCode);
}

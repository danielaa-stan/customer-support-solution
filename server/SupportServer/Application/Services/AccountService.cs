using SupportServer.Application.Ports;
using SupportServer.Config;
using SupportServer.Domain;

namespace SupportServer.Application.Services;

public sealed class AccountService(IBillingProvider billing, IClock clock)
{
    public ToolOutcome GetProfile(ToolContext ctx)
    {
        var account = billing.GetAccount(ctx.UserId);
        if (account is null)
            return ToolOutcome.Fail(ErrorCodes.NotFound, "Акаунт користувача не знайдено.");

        var now = clock.UtcNow;
        var sub = account.Subscription;
        var tenureMonths = Iso.WholeMonthsBetween(Iso.Parse(sub.StartedAt), now);
        var offerUsed = billing.HasRetentionOfferSince(
            ctx.UserId, now.AddMonths(-BusinessRules.RetentionCooldownMonths));

        return ToolOutcome.Done(new
        {
            user = new
            {
                id = account.User.Id,
                name = account.User.Name,
                country = account.User.Country,
                is_student = account.User.IsStudent == 1,
            },
            subscription = new
            {
                plan = sub.Plan,
                status = sub.Status,
                price_amount = sub.PriceAmount,
                price_currency = sub.PriceCurrency,
                next_billing_date = sub.NextBillingDate,
                tenure_months = tenureMonths,
                pending_plan = sub.PendingPlan,
                paused_until = sub.PausedUntil,
                cancel_at = sub.CancelAt,
                discount_percent = sub.DiscountPercent,
            },
            usage = new
            {
                listening_hours_30d = account.Usage.ListeningHours30d,
                last_active_at = account.Usage.LastActiveAt,
                devices_count = account.Usage.DevicesCount,
            },
            flags = new
            {
                retention_offer_used_in_cooldown = offerUsed,
            },
        });
    }
}

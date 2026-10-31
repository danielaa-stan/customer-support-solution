using Dapper;
using SupportServer.Application.Ports;
using SupportServer.Domain;
using SupportServer.Infrastructure.Db;

namespace SupportServer.Infrastructure.Billing;

/// <summary>Billing simulation (Spotify does not expose such APIs publicly). Data lives in SQLite.</summary>
public sealed class MockBillingProvider(SqliteConnectionFactory db) : IBillingProvider
{
    public UserAccount? GetAccount(string userId)
    {
        using var c = db.Open();
        var user = c.QuerySingleOrDefault<User>("SELECT * FROM users WHERE id = @userId", new { userId });
        var sub = c.QuerySingleOrDefault<Subscription>("SELECT * FROM subscriptions WHERE user_id = @userId", new { userId });
        if (user is null || sub is null) return null;

        var usage = c.QuerySingleOrDefault<UsageStats>("SELECT * FROM usage_stats WHERE user_id = @userId", new { userId })
                    ?? new UsageStats { UserId = userId };
        return new UserAccount(user, sub, usage);
    }

    public IReadOnlyList<Payment> GetPayments(string userId, int limit)
    {
        using var c = db.Open();
        return c.Query<Payment>(
            "SELECT * FROM payments WHERE user_id = @userId ORDER BY charged_at DESC LIMIT @limit",
            new { userId, limit }).ToList();
    }

    public Payment? GetPayment(string userId, string paymentId)
    {
        using var c = db.Open();
        return c.QuerySingleOrDefault<Payment>(
            "SELECT * FROM payments WHERE id = @paymentId AND user_id = @userId",
            new { paymentId, userId });
    }

    public bool RefundPayment(string paymentId, string reasonCode, DateTimeOffset now)
    {
        using var c = db.Open();
        var changed = c.Execute(
            "UPDATE payments SET status = 'refunded', refunded_at = @at, refund_reason = @reasonCode " +
            "WHERE id = @paymentId AND status = 'succeeded'",
            new { at = Iso.Format(now), reasonCode, paymentId });
        return changed == 1;
    }

    public bool HasRetentionOfferSince(string userId, DateTimeOffset since)
    {
        using var c = db.Open();
        return c.ExecuteScalar<long>(
            "SELECT COUNT(1) FROM retention_offers_used WHERE user_id = @userId AND applied_at >= @since",
            new { userId, since = Iso.Format(since) }) > 0;
    }

    public bool PauseSubscription(string userId, DateTimeOffset until)
    {
        using var c = db.Open();
        return c.Execute(
            "UPDATE subscriptions SET status = 'paused', paused_until = @until, next_billing_date = @until " +
            "WHERE user_id = @userId AND status = 'active' AND cancel_at IS NULL",
            new { until = Iso.Format(until), userId }) == 1;
    }

    public bool ChangePlanNow(string userId, string plan, double price)
    {
        using var c = db.Open();
        return c.Execute(
            "UPDATE subscriptions SET plan = @plan, pending_plan = NULL, price_amount = @price " +
            "WHERE user_id = @userId AND status = 'active'",
            new { plan, price, userId }) == 1;
    }

    public bool SetPendingPlan(string userId, string plan)
    {
        using var c = db.Open();
        return c.Execute(
            "UPDATE subscriptions SET pending_plan = @plan WHERE user_id = @userId AND status = 'active'",
            new { plan, userId }) == 1;
    }

    public bool ApplyDiscountOffer(string userId, string offerCode, int percent, int payments, DateTimeOffset now)
    {
        using var c = db.Open();
        using var tx = c.BeginTransaction();
        var changed = c.Execute(
            "UPDATE subscriptions SET discount_percent = @percent, discount_payments_left = @payments " +
            "WHERE user_id = @userId AND status = 'active'",
            new { percent, payments, userId }, tx);
        if (changed != 1) return false;

        RecordOfferUsed(c, tx, userId, offerCode, now);
        tx.Commit();
        return true;
    }

    public bool GrantFreeMonth(string userId, string offerCode, DateTimeOffset newNextBillingDate, DateTimeOffset now)
    {
        using var c = db.Open();
        using var tx = c.BeginTransaction();
        var changed = c.Execute(
            "UPDATE subscriptions SET next_billing_date = @next WHERE user_id = @userId AND status = 'active'",
            new { next = Iso.Format(newNextBillingDate), userId }, tx);
        if (changed != 1) return false;

        RecordOfferUsed(c, tx, userId, offerCode, now);
        tx.Commit();
        return true;
    }

    public bool ScheduleCancellation(string userId, DateTimeOffset cancelAt)
    {
        using var c = db.Open();
        return c.Execute(
            "UPDATE subscriptions SET cancel_at = @cancelAt, next_billing_date = NULL " +
            "WHERE user_id = @userId AND status IN ('active', 'paused') AND cancel_at IS NULL",
            new { cancelAt = Iso.Format(cancelAt), userId }) == 1;
    }

    public bool CancelNow(string userId, DateTimeOffset now)
    {
        using var c = db.Open();
        return c.Execute(
            "UPDATE subscriptions SET status = 'canceled', cancel_at = @now, next_billing_date = NULL, paused_until = NULL " +
            "WHERE user_id = @userId AND status IN ('active', 'paused')",
            new { now = Iso.Format(now), userId }) == 1;
    }

    private static void RecordOfferUsed(Microsoft.Data.Sqlite.SqliteConnection c, Microsoft.Data.Sqlite.SqliteTransaction tx,
        string userId, string offerCode, DateTimeOffset now) =>
        c.Execute(
            "INSERT INTO retention_offers_used (user_id, offer_code, applied_at) VALUES (@userId, @offerCode, @at)",
            new { userId, offerCode, at = Iso.Format(now) }, tx);
}

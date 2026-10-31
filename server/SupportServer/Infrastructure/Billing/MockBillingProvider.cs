using Dapper;
using SupportServer.Application.Ports;
using SupportServer.Domain;
using SupportServer.Infrastructure.Db;

namespace SupportServer.Infrastructure.Billing;

/// <summary>Імітація білінгу (Spotify не відкриває такі API назовні). Дані лежать у SQLite.</summary>
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
}

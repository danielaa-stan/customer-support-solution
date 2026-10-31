using SupportServer.Domain;

namespace SupportServer.Application.Ports;

/// <summary>
/// Port to the billing system. There is one implementation for now: MockBillingProvider.
/// To connect a real billing system, implement this interface in one more class.
/// All methods work only within the given user (data isolation).
/// </summary>
public interface IBillingProvider
{
    UserAccount? GetAccount(string userId);

    IReadOnlyList<Payment> GetPayments(string userId, int limit);

    /// <summary>Returns the payment only if it belongs to the user.</summary>
    Payment? GetPayment(string userId, string paymentId);

    /// <summary>true if the refund was performed; false if the payment was already refunded (guards against races).</summary>
    bool RefundPayment(string paymentId, string reasonCode, DateTimeOffset now);

    bool HasRetentionOfferSince(string userId, DateTimeOffset since);

    // Subscription changes. Each returns true if a row was changed; false if the state no longer allowed it.

    bool PauseSubscription(string userId, DateTimeOffset until);

    bool ChangePlanNow(string userId, string plan, double price);

    bool SetPendingPlan(string userId, string plan);

    bool ApplyDiscountOffer(string userId, string offerCode, int percent, int payments, DateTimeOffset now);

    bool GrantFreeMonth(string userId, string offerCode, DateTimeOffset newNextBillingDate, DateTimeOffset now);

    bool ScheduleCancellation(string userId, DateTimeOffset cancelAt);

    bool CancelNow(string userId, DateTimeOffset now);
}

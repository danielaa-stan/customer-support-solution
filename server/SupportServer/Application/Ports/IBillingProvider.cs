using SupportServer.Domain;

namespace SupportServer.Application.Ports;

/// <summary>
/// Порт до системи білінгу. Зараз є одна реалізація: MockBillingProvider.
/// Щоб підключити реальний білінг, достатньо написати ще один клас, що реалізує цей інтерфейс.
/// Усі методи працюють лише в межах користувача, якого передано (ізоляція даних).
/// </summary>
public interface IBillingProvider
{
    UserAccount? GetAccount(string userId);

    IReadOnlyList<Payment> GetPayments(string userId, int limit);

    /// <summary>Повертає платіж, лише якщо він належить користувачу.</summary>
    Payment? GetPayment(string userId, string paymentId);

    /// <summary>true, якщо повернення виконано; false, якщо платіж уже повернений (захист від гонок).</summary>
    bool RefundPayment(string paymentId, string reasonCode, DateTimeOffset now);

    bool HasRetentionOfferSince(string userId, DateTimeOffset since);
}

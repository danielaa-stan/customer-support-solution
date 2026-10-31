using SupportServer.Config;

namespace SupportServer.Domain.Policies;

public enum RefundVerdict { Allowed, AlreadyRefunded, NotRefundable, WindowExpired, OverAutoLimit }

public sealed record RefundDecision(RefundVerdict Verdict, string? PolicyRef, string Message);

/// <summary>
/// Pure, deterministic refund rules (contracts/04-business-rules.md).
/// This is the safety guard: the model cannot "talk it into" anything, because the rules do not depend on the prompt.
/// </summary>
public static class RefundPolicy
{
    public static RefundDecision Evaluate(Payment payment, DateTimeOffset now)
    {
        if (payment.Status == "refunded")
            return new(RefundVerdict.AlreadyRefunded, null, $"Платіж {payment.Id} уже повернено раніше.");

        if (payment.Status != "succeeded")
            return new(RefundVerdict.NotRefundable, PolicyRefs.RefundWindow,
                "Повернути можна лише успішно проведений платіж.");

        var age = now - Iso.Parse(payment.ChargedAt);
        if (age > TimeSpan.FromDays(BusinessRules.RefundWindowDays))
            return new(RefundVerdict.WindowExpired, PolicyRefs.RefundWindow,
                $"Платіж старший за {BusinessRules.RefundWindowDays} днів, повернення за політикою неможливе.");

        if (payment.Amount > BusinessRules.AutoRefundLimit + 1e-9)
            return new(RefundVerdict.OverAutoLimit, PolicyRefs.RefundAutoLimit,
                $"Сума {payment.Amount:0.00} {payment.Currency} перевищує ліміт автоматичного повернення " +
                $"({BusinessRules.AutoRefundLimit:0.00}). Потрібен агент-людина.");

        return new(RefundVerdict.Allowed, null, "Повернення дозволено.");
    }
}

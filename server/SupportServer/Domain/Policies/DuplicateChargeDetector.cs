using SupportServer.Config;

namespace SupportServer.Domain.Policies;

/// <param name="PaymentId">The later payment that looks like a duplicate.</param>
/// <param name="DuplicateOf">The earlier payment it appears to duplicate.</param>
public sealed record DuplicatePair(string PaymentId, string DuplicateOf);

/// <summary>Two successful payments with the same amount, currency and kind, at most 24 hours apart.</summary>
public static class DuplicateChargeDetector
{
    public static IReadOnlyList<DuplicatePair> Find(IEnumerable<Payment> payments)
    {
        var ordered = payments
            .Where(p => p.Status == "succeeded")
            .OrderBy(p => Iso.Parse(p.ChargedAt))
            .ToList();

        var result = new List<DuplicatePair>();
        var window = TimeSpan.FromHours(BusinessRules.DuplicateChargeWindowHours);

        for (var later = 1; later < ordered.Count; later++)
        {
            for (var earlier = 0; earlier < later; earlier++)
            {
                var a = ordered[earlier];
                var b = ordered[later];
                var sameCharge = Math.Abs(a.Amount - b.Amount) < 0.005
                                 && a.Currency == b.Currency
                                 && a.Kind == b.Kind;
                if (sameCharge && Iso.Parse(b.ChargedAt) - Iso.Parse(a.ChargedAt) <= window)
                {
                    result.Add(new DuplicatePair(b.Id, a.Id));
                    break;
                }
            }
        }
        return result;
    }
}

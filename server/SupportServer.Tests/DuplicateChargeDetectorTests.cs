using SupportServer.Domain;
using SupportServer.Domain.Policies;

namespace SupportServer.Tests;

public class DuplicateChargeDetectorTests
{
    private static Payment Pay(string id, string chargedAt, double amount = 4.99, string status = "succeeded") =>
        new() { Id = id, UserId = "u", Amount = amount, Currency = "USD", Kind = "renewal", Status = status, ChargedAt = chargedAt };

    [Fact]
    public void Two_identical_charges_minutes_apart_are_a_duplicate()
    {
        var result = DuplicateChargeDetector.Find([Pay("a", "2026-10-29T08:00:00Z"), Pay("b", "2026-10-29T08:02:00Z")]);
        var pair = Assert.Single(result);
        Assert.Equal("b", pair.PaymentId);
        Assert.Equal("a", pair.DuplicateOf);
    }

    [Fact]
    public void Monthly_renewals_are_not_duplicates() =>
        Assert.Empty(DuplicateChargeDetector.Find([Pay("a", "2026-09-29T08:00:00Z"), Pay("b", "2026-10-29T08:00:00Z")]));

    [Fact]
    public void Charges_more_than_24_hours_apart_are_not_duplicates() =>
        Assert.Empty(DuplicateChargeDetector.Find([Pay("a", "2026-10-28T08:00:00Z"), Pay("b", "2026-10-29T08:01:00Z")]));

    [Fact]
    public void Different_amounts_are_not_duplicates() =>
        Assert.Empty(DuplicateChargeDetector.Find([Pay("a", "2026-10-29T08:00:00Z"), Pay("b", "2026-10-29T08:02:00Z", amount: 6.49)]));

    [Fact]
    public void Refunded_payment_is_ignored() =>
        Assert.Empty(DuplicateChargeDetector.Find([Pay("a", "2026-10-29T08:00:00Z"), Pay("b", "2026-10-29T08:02:00Z", status: "refunded")]));
}

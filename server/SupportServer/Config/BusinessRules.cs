namespace SupportServer.Config;

/// <summary>
/// Business constants. Single source of truth: contracts/04-business-rules.md.
/// If you change a number here, change it in the contract and in the policies (data/policies) too.
/// </summary>
public static class BusinessRules
{
    public const int RefundWindowDays = 14;
    public const double AutoRefundLimit = 20.00;
    public const int PauseMaxMonths = 3;
    public const int RetentionCooldownMonths = 12;
    public const int DuplicateChargeWindowHours = 24;

    public static readonly DateTimeOffset DefaultDemoNow = new(2026, 10, 31, 12, 0, 0, TimeSpan.Zero);
}

/// <summary>Policy anchors for citation (format doc_id#section).</summary>
public static class PolicyRefs
{
    public const string RefundWindow = "refund-policy#2.1";
    public const string DuplicateCharge = "refund-policy#2.2";
    public const string RefundAutoLimit = "refund-policy#2.3";
}

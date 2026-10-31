namespace SupportServer.Config;

/// <summary>
/// Бізнес-константи. Єдине джерело правди: contracts/04-business-rules.md.
/// Змінюєш число тут: зміни і в контракті та в політиках (data/policies).
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

/// <summary>Якорі політик для цитування (формат doc_id#розділ).</summary>
public static class PolicyRefs
{
    public const string RefundWindow = "refund-policy#2.1";
    public const string DuplicateCharge = "refund-policy#2.2";
    public const string RefundAutoLimit = "refund-policy#2.3";
}

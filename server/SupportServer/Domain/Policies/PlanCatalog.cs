namespace SupportServer.Domain.Policies;

/// <summary>Plans and prices (contracts/04-business-rules.md).</summary>
public static class PlanCatalog
{
    private static readonly Dictionary<string, double> Prices = new()
    {
        ["individual"] = 9.99,
        ["duo"] = 12.99,
        ["family"] = 15.99,
        ["student"] = 4.99,
    };

    public static bool IsKnown(string? plan) => plan is not null && Prices.ContainsKey(plan);

    public static double PriceOf(string plan) => Prices[plan];

    public static bool IsUpgrade(string from, string to) => Prices[to] > Prices[from] + 1e-9;

    public static string Allowed => string.Join(", ", Prices.Keys);
}

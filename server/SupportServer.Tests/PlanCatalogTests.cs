using SupportServer.Domain.Policies;

namespace SupportServer.Tests;

public sealed class PlanCatalogTests
{
    [Theory]
    [InlineData("individual", 4.99)]
    [InlineData("duo", 6.49)]
    [InlineData("family", 7.99)]
    [InlineData("student", 2.49)]
    public void Regular_monthly_prices_match_the_Ukraine_catalog(string plan, double expected)
    {
        Assert.Equal(expected, PlanCatalog.PriceOf(plan));
    }
}

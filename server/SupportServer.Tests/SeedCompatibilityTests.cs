using System.Text.Json;
using Microsoft.Data.Sqlite;
using SupportServer.Config;
using SupportServer.Infrastructure.Db;
using SupportServer.Tools;

namespace SupportServer.Tests;

public sealed class SeedCompatibilityTests
{
    [Fact]
    public void Generated_customer_seed_supports_the_bonus_escalation_flow()
    {
        using var harness = new TestHarness(Path.Combine(AppContext.BaseDirectory, "customer-seed.json"));
        var context = TestHarness.Parse(harness.Tools<SessionTools>().SetContext("ses_bonus_seed", "u_demo_escalate", 1));
        Assert.True(context.GetProperty("ok").GetBoolean(), context.ToString());

        var refund = TestHarness.Parse(harness.Tools<PaymentTools>().IssueRefund("pay_demo_big", "other", "refund-policy#2.3"));
        Assert.Equal("needs_human", refund.GetProperty("status").GetString());
        Assert.True(refund.GetProperty("needs_human").GetBoolean());
        Assert.Equal("LIMIT_EXCEEDED", refund.GetProperty("error").GetProperty("code").GetString());
        Assert.Equal(23.97, harness.Query<double>("SELECT amount FROM payments WHERE id = 'pay_demo_big'").Single());
        Assert.Equal("succeeded", harness.Query<string>("SELECT status FROM payments WHERE id = 'pay_demo_big'").Single());

        using var suggestion = JsonDocument.Parse(
            """{"tool":"issue_refund","args":{"payment_id":"pay_demo_big","reason_code":"other","policy_ref":"refund-policy#2.3"},"rationale":"Payment exceeds the automatic refund limit","policy_ref":"refund-policy#2.3"}""");
        var escalated = TestHarness.Parse(harness.Tools<EscalationTools>().EscalateToHuman(
            "high", "refund_request", "Review the 23.97 USD charge; automatic refund limit exceeded.", suggestion.RootElement.Clone()));
        Assert.True(escalated.GetProperty("ok").GetBoolean(), escalated.ToString());
        Assert.Single(harness.Query<string>("SELECT id FROM tickets WHERE user_id = 'u_demo_escalate'"));
    }

    [Fact]
    public void Generated_customer_seed_loads_with_empty_runtime_arrays()
    {
        var database = Path.Combine(Path.GetTempPath(), $"seed-compatibility-{Guid.NewGuid():N}.db");
        try
        {
            var seed = Path.Combine(AppContext.BaseDirectory, "customer-seed.json");
            DbInitializer.EnsureCreated(new SupportOptions(database, seed, BusinessRules.DefaultDemoNow));
            using var connection = new SqliteConnection($"Data Source={database};Pooling=False");
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT count(*) FROM users";
            using var document = JsonDocument.Parse(File.ReadAllText(seed));
            Assert.Equal(document.RootElement.GetProperty("users").GetArrayLength(), Convert.ToInt32(command.ExecuteScalar()));
            command.CommandText = "SELECT amount FROM payments WHERE id = 'pay_demo_dbl_2'";
            Assert.Equal(4.99, Convert.ToDouble(command.ExecuteScalar()));
            command.CommandText = "SELECT count(*) FROM audit_log";
            Assert.Equal(0L, command.ExecuteScalar());
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            if (File.Exists(database)) File.Delete(database);
        }
    }

    [Theory]
    [InlineData("tickets", "[{}]")]
    [InlineData("pending_actions", "[{}]")]
    [InlineData("audit_log", "[{}]")]
    [InlineData("audit_log", "null")]
    public void Runtime_history_is_rejected_without_loading_customers(string table, string value)
    {
        using var connection = new SqliteConnection("Data Source=:memory:");
        connection.Open();
        var seedPath = Path.Combine(Path.GetTempPath(), $"invalid-seed-{Guid.NewGuid():N}.json");
        try
        {
            File.WriteAllText(seedPath, $$"""{"users":[{"id":"u_must_not_load"}],"{{table}}":{{value}}}""");
            var error = Assert.Throws<InvalidDataException>(() =>
                SeedLoader.Load(connection, seedPath, new SqlDialect(DbProvider.Sqlite)));
            Assert.Contains("must be an empty array", error.Message);
        }
        finally
        {
            File.Delete(seedPath);
        }
    }
}

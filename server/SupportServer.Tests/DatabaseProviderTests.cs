using Npgsql;
using SupportServer.Infrastructure.Db;

namespace SupportServer.Tests;

/// <summary>Pure tests for the PostgreSQL support code (no database needed).</summary>
public class DatabaseProviderTests
{
    [Fact]
    public void Url_is_converted_to_an_Npgsql_connection_string()
    {
        var builder = new NpgsqlConnectionStringBuilder(
            PostgresConnection.FromUrl("postgresql://support_app:p%40ss%3Aword@localhost:5433/support"));

        Assert.Equal("localhost", builder.Host);
        Assert.Equal(5433, builder.Port);
        Assert.Equal("support_app", builder.Username);
        Assert.Equal("p@ss:word", builder.Password);
        Assert.Equal("support", builder.Database);
    }

    [Fact]
    public void Url_without_a_port_uses_the_default_port()
    {
        var builder = new NpgsqlConnectionStringBuilder(PostgresConnection.FromUrl("postgresql://u:p@db.local/support"));
        Assert.Equal(5432, builder.Port);
    }

    [Fact]
    public void Describing_a_url_never_leaks_the_password()
    {
        var text = PostgresConnection.Describe("postgresql://support_app:topsecret@localhost:5432/support");

        Assert.Equal("localhost:5432/support", text);
        Assert.DoesNotContain("topsecret", text);
    }

    [Fact]
    public void Postgres_dialect_casts_and_formats_dates()
    {
        var postgres = new SqlDialect(DbProvider.Postgres);

        Assert.Equal("CAST(@at AS timestamptz)", postgres.Ts("@at"));
        Assert.Contains("to_char(charged_at AT TIME ZONE 'UTC'", postgres.DateText("charged_at"));
        Assert.EndsWith("AS charged_at", postgres.DateText("charged_at"));
    }

    [Fact]
    public void Sqlite_dialect_leaves_dates_as_text()
    {
        var sqlite = new SqlDialect(DbProvider.Sqlite);

        Assert.Equal("@at", sqlite.Ts("@at"));
        Assert.Equal("charged_at", sqlite.DateText("charged_at"));
    }
}

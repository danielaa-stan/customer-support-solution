using System.Text.Json;
using Dapper;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.DependencyInjection;
using SupportServer.Config;
using SupportServer.Infrastructure.Db;

namespace SupportServer.Tests;

/// <summary>Піднімає сервер у пам'яті процесу: тимчасова БД + dev-seed + фіксований час DEMO_NOW.</summary>
public sealed class TestHarness : IDisposable
{
    private readonly string _dbPath = Path.Combine(Path.GetTempPath(), $"support-test-{Guid.NewGuid():N}.db");

    public ServiceProvider Services { get; }

    public TestHarness()
    {
        var seed = Path.Combine(AppContext.BaseDirectory, "dev-seed.json");
        var options = new SupportOptions(_dbPath, seed, BusinessRules.DefaultDemoNow);
        DbInitializer.EnsureCreated(options);

        var services = new ServiceCollection();
        services.AddLogging();
        services.AddSupportServer(options);
        Services = services.BuildServiceProvider();
    }

    public T Tools<T>() where T : class => ActivatorUtilities.CreateInstance<T>(Services);

    public static JsonElement Parse(string json) => JsonDocument.Parse(json).RootElement;

    public List<T> Query<T>(string sql, object? param = null)
    {
        using var connection = Services.GetRequiredService<SqliteConnectionFactory>().Open();
        return connection.Query<T>(sql, param).ToList();
    }

    public void Dispose()
    {
        Services.Dispose();
        SqliteConnection.ClearAllPools();
        try { File.Delete(_dbPath); } catch (IOException) { /* тимчасовий файл */ }
    }
}

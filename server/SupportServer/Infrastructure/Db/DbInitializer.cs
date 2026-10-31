using System.Data.Common;
using Dapper;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using SupportServer.Config;

namespace SupportServer.Infrastructure.Db;

public static class DbInitializer
{
    // Children first, so the list can be used for truncation.
    private const string AllTables =
        "audit_log, pending_actions, tickets, retention_offers_used, usage_stats, payments, subscriptions, users";

    /// <summary>
    /// Makes sure the schema exists and the seed is loaded.
    /// SQLite: creates the file from the embedded schema when it does not exist yet.
    /// PostgreSQL: creates the schema if missing (Docker normally does it) and loads the seed when the users table is empty.
    /// </summary>
    public static void EnsureCreated(SupportOptions options, ILogger? logger = null)
    {
        logger ??= NullLogger.Instance;

        if (options.DatabaseUrl is null) EnsureSqlite(options, logger);
        else EnsurePostgres(options, logger, reset: false);
    }

    /// <summary>Wipes all support data and loads the seed again (clean start for a demo).</summary>
    public static void Reset(SupportOptions options, ILogger? logger = null)
    {
        logger ??= NullLogger.Instance;

        if (options.DatabaseUrl is null)
        {
            SqliteConnection.ClearAllPools();
            if (File.Exists(options.DbPath)) File.Delete(options.DbPath);
            EnsureSqlite(options, logger);
        }
        else
        {
            EnsurePostgres(options, logger, reset: true);
        }
    }

    private static void EnsureSqlite(SupportOptions options, ILogger logger)
    {
        if (File.Exists(options.DbPath))
        {
            logger.LogInformation("Using existing SQLite database {DbPath}", options.DbPath);
            return;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(options.DbPath)!);

        var factory = new DbConnectionFactory(options);
        using var connection = factory.Open();
        connection.Execute(ReadEmbedded("schema.sqlite.sql"));

        LoadSeed(connection, options, factory.Dialect, logger, "SQLite " + options.DbPath);
    }

    private static void EnsurePostgres(SupportOptions options, ILogger logger, bool reset)
    {
        var factory = new DbConnectionFactory(options);
        using var connection = factory.Open();
        logger.LogInformation("Connected to PostgreSQL {Target}", PostgresConnection.Describe(options.DatabaseUrl!));

        var schemaExists = connection.ExecuteScalar<string?>("SELECT to_regclass('public.users')::text") is not null;
        if (!schemaExists)
        {
            connection.Execute(ReadEmbedded("schema.sql"));
            logger.LogInformation("Created the support schema");
        }
        else if (reset)
        {
            connection.Execute($"TRUNCATE TABLE {AllTables} RESTART IDENTITY CASCADE");
            logger.LogInformation("Truncated all support tables");
        }

        var users = connection.ExecuteScalar<long>("SELECT COUNT(1) FROM users");
        if (users == 0)
            LoadSeed(connection, options, factory.Dialect, logger, "PostgreSQL");
        else
            logger.LogInformation("Using existing PostgreSQL data ({Users} users)", users);
    }

    private static void LoadSeed(DbConnection connection, SupportOptions options, SqlDialect dialect, ILogger logger, string target)
    {
        if (File.Exists(options.SeedPath))
        {
            var rows = SeedLoader.Load(connection, options.SeedPath, dialect);
            logger.LogInformation("Loaded {Rows} seed rows into {Target} from {SeedPath}", rows, target, options.SeedPath);
        }
        else
        {
            logger.LogWarning("No seed loaded into {Target}: file not found {SeedPath}", target, options.SeedPath);
        }
    }

    private static string ReadEmbedded(string name)
    {
        using var stream = typeof(DbInitializer).Assembly.GetManifestResourceStream(name)
            ?? throw new InvalidOperationException($"Embedded resource {name} not found (see SupportServer.csproj).");
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd();
    }
}

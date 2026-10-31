using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using SupportServer.Config;

namespace SupportServer.Infrastructure.Db;

public static class DbInitializer
{
    /// <summary>Creates the DB from contracts/schema.sql and loads the seed, if the DB file does not exist yet.</summary>
    public static void EnsureCreated(SupportOptions options, ILogger? logger = null)
    {
        logger ??= NullLogger.Instance;

        if (File.Exists(options.DbPath))
        {
            logger.LogInformation("Using existing database {DbPath}", options.DbPath);
            return;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(options.DbPath)!);

        var connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = options.DbPath,
            Mode = SqliteOpenMode.ReadWriteCreate,
            Pooling = false,
        }.ToString();

        using var connection = new SqliteConnection(connectionString);
        connection.Open();

        using (var command = connection.CreateCommand())
        {
            command.CommandText = ReadEmbeddedSchema();
            command.ExecuteNonQuery();
        }

        if (File.Exists(options.SeedPath))
        {
            var rows = SeedLoader.Load(connection, options.SeedPath);
            logger.LogInformation("Created database {DbPath}, loaded {Rows} seed rows from {SeedPath}",
                options.DbPath, rows, options.SeedPath);
        }
        else
        {
            logger.LogWarning("Created database {DbPath} without seed: file not found {SeedPath}",
                options.DbPath, options.SeedPath);
        }
    }

    /// <summary>Deletes the DB and creates it again (clean start for a demo).</summary>
    public static void Reset(SupportOptions options, ILogger? logger = null)
    {
        SqliteConnection.ClearAllPools();
        if (File.Exists(options.DbPath)) File.Delete(options.DbPath);
        EnsureCreated(options, logger);
    }

    private static string ReadEmbeddedSchema()
    {
        using var stream = typeof(DbInitializer).Assembly.GetManifestResourceStream("schema.sql")
            ?? throw new InvalidOperationException("Embedded resource schema.sql not found (see SupportServer.csproj).");
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd();
    }
}

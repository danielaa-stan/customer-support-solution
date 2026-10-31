using Microsoft.Data.Sqlite;
using SupportServer.Config;

namespace SupportServer.Infrastructure.Db;

public static class DbInitializer
{
    /// <summary>Створює БД зі схеми contracts/schema.sql і завантажує seed, якщо файлу БД ще немає.</summary>
    public static void EnsureCreated(SupportOptions options)
    {
        if (File.Exists(options.DbPath)) return;

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
            Console.Error.WriteLine($"[db] Створено {options.DbPath}, seed: {rows} рядків з {options.SeedPath}");
        }
        else
        {
            Console.Error.WriteLine($"[db] Створено {options.DbPath}. Seed не знайдено: {options.SeedPath}");
        }
    }

    /// <summary>Видаляє БД і створює заново (для чистого старту демо).</summary>
    public static void Reset(SupportOptions options)
    {
        SqliteConnection.ClearAllPools();
        if (File.Exists(options.DbPath)) File.Delete(options.DbPath);
        EnsureCreated(options);
    }

    private static string ReadEmbeddedSchema()
    {
        using var stream = typeof(DbInitializer).Assembly.GetManifestResourceStream("schema.sql")
            ?? throw new InvalidOperationException("Вбудований ресурс schema.sql не знайдено (див. SupportServer.csproj).");
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd();
    }
}

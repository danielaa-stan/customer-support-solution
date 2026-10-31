using Dapper;
using Microsoft.Data.Sqlite;

namespace SupportServer.Infrastructure.Db;

/// <summary>Фабрика з'єднань. Одне нове з'єднання на операцію, без пулу (простіше й безпечніше для файлу БД).</summary>
public sealed class SqliteConnectionFactory
{
    private readonly string _connectionString;

    static SqliteConnectionFactory()
    {
        // Мапить колонки snake_case на властивості PascalCase (charged_at -> ChargedAt).
        DefaultTypeMap.MatchNamesWithUnderscores = true;
    }

    public SqliteConnectionFactory(string dbPath)
    {
        _connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = dbPath,
            Mode = SqliteOpenMode.ReadWriteCreate,
            Pooling = false,
        }.ToString();
    }

    public SqliteConnection Open()
    {
        var connection = new SqliteConnection(_connectionString);
        connection.Open();
        connection.Execute("PRAGMA foreign_keys = ON;");
        return connection;
    }
}

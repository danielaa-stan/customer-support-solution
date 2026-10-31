using Dapper;
using Microsoft.Data.Sqlite;

namespace SupportServer.Infrastructure.Db;

/// <summary>Connection factory. One new connection per operation, no pooling (simpler and safer for a file DB).</summary>
public sealed class SqliteConnectionFactory
{
    private readonly string _connectionString;

    static SqliteConnectionFactory()
    {
        // Maps snake_case columns to PascalCase properties (charged_at -> ChargedAt).
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

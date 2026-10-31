using System.Data.Common;
using Dapper;
using Microsoft.Data.Sqlite;
using Npgsql;
using SupportServer.Config;

namespace SupportServer.Infrastructure.Db;

/// <summary>Opens connections to the configured database: PostgreSQL if SUPPORT_DATABASE_URL is set, otherwise SQLite.</summary>
public sealed class DbConnectionFactory
{
    private readonly string _connectionString;

    static DbConnectionFactory()
    {
        // Maps snake_case columns to PascalCase properties (charged_at -> ChargedAt).
        DefaultTypeMap.MatchNamesWithUnderscores = true;
    }

    public DbConnectionFactory(SupportOptions options)
    {
        if (options.DatabaseUrl is { } url)
        {
            Dialect = new SqlDialect(DbProvider.Postgres);
            _connectionString = PostgresConnection.FromUrl(url);
        }
        else
        {
            Dialect = new SqlDialect(DbProvider.Sqlite);
            _connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = options.DbPath,
                Mode = SqliteOpenMode.ReadWriteCreate,
                Pooling = false,
            }.ToString();
        }
    }

    public SqlDialect Dialect { get; }

    public DbConnection Open()
    {
        DbConnection connection = Dialect.IsPostgres
            ? new NpgsqlConnection(_connectionString)
            : new SqliteConnection(_connectionString);

        connection.Open();
        if (!Dialect.IsPostgres) connection.Execute("PRAGMA foreign_keys = ON;");
        return connection;
    }
}

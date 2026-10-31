namespace SupportServer.Infrastructure.Db;

public enum DbProvider { Sqlite, Postgres }

/// <summary>
/// The few SQL differences between the two supported databases. The domain models carry dates as ISO 8601 text.
/// SQLite stores that text as is; PostgreSQL stores TIMESTAMPTZ, so the text is cast on the way in and formatted on the way out.
/// </summary>
public sealed class SqlDialect(DbProvider provider)
{
    public DbProvider Provider => provider;

    public bool IsPostgres => provider == DbProvider.Postgres;

    /// <summary>Wraps an ISO text parameter so it can be stored in, or compared with, a date column.</summary>
    public string Ts(string parameter) => IsPostgres ? $"CAST({parameter} AS timestamptz)" : parameter;

    /// <summary>Selects a date column as ISO 8601 UTC text, keeping the column name.</summary>
    public string DateText(string column) => IsPostgres
        ? $"to_char({column} AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS {column}"
        : column;
}

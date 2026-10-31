using System.Data.Common;
using System.Text.Json;
using SupportServer.Domain;

namespace SupportServer.Infrastructure.Db;

/// <summary>
/// Loads seed.json (format: contracts/02-data-model.md). Top-level keys are table names,
/// fields are column names. Names are checked against the schema, so a mistake in the seed gives a clear message.
/// Works with both databases: for PostgreSQL, ISO date strings are converted for TIMESTAMPTZ columns.
/// </summary>
public static class SeedLoader
{
    private static readonly string[] Tables =
        ["users", "subscriptions", "payments", "usage_stats", "retention_offers_used"];

    private const string PostgresTimestamp = "timestamp with time zone";

    public static int Load(DbConnection connection, string seedPath, SqlDialect dialect)
    {
        using var document = JsonDocument.Parse(File.ReadAllText(seedPath));
        var root = document.RootElement;

        if (root.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException($"{seedPath}: expected a JSON object whose keys are table names.");

        foreach (var property in root.EnumerateObject())
        {
            if (!Tables.Contains(property.Name))
                throw new InvalidDataException(
                    $"{seedPath}: unknown table '{property.Name}'. Allowed: {string.Join(", ", Tables)}.");
        }

        using var transaction = connection.BeginTransaction();
        var inserted = 0;

        foreach (var table in Tables)
        {
            if (!root.TryGetProperty(table, out var rows)) continue;
            if (rows.ValueKind != JsonValueKind.Array)
                throw new InvalidDataException($"{seedPath}: '{table}' must be an array.");

            var columns = GetColumns(connection, transaction, table, dialect);
            var index = 0;

            foreach (var row in rows.EnumerateArray())
            {
                var fields = row.EnumerateObject().ToList();
                foreach (var field in fields)
                {
                    if (!columns.ContainsKey(field.Name))
                        throw new InvalidDataException(
                            $"seed.{table}[{index}]: unknown field '{field.Name}'. Columns: {string.Join(", ", columns.Keys)}.");
                }

                using var command = connection.CreateCommand();
                command.Transaction = transaction;
                var names = string.Join(", ", fields.Select(f => f.Name));
                var placeholders = string.Join(", ", fields.Select((_, i) => $"@p{i}"));
                command.CommandText = $"INSERT INTO {table} ({names}) VALUES ({placeholders})";

                for (var i = 0; i < fields.Count; i++)
                {
                    var parameter = command.CreateParameter();
                    parameter.ParameterName = $"@p{i}";
                    parameter.Value = ToDbValue(fields[i].Value, columns[fields[i].Name], dialect, table, index, fields[i].Name);
                    command.Parameters.Add(parameter);
                }

                try
                {
                    command.ExecuteNonQuery();
                }
                catch (DbException ex)
                {
                    throw new InvalidDataException($"seed.{table}[{index}]: {ex.Message}", ex);
                }

                index++;
                inserted++;
            }
        }

        transaction.Commit();
        return inserted;
    }

    /// <summary>Column name to declared type (lower case).</summary>
    private static Dictionary<string, string> GetColumns(DbConnection connection, DbTransaction transaction, string table, SqlDialect dialect)
    {
        var columns = new Dictionary<string, string>();
        using var command = connection.CreateCommand();
        command.Transaction = transaction;

        if (dialect.IsPostgres)
        {
            command.CommandText =
                $"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{table}'";
        }
        else
        {
            command.CommandText = $"PRAGMA table_info({table})";
        }

        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            var name = dialect.IsPostgres ? reader.GetString(0) : reader.GetString(1);
            var type = dialect.IsPostgres ? reader.GetString(1) : reader.GetString(2);
            columns[name] = type.ToLowerInvariant();
        }

        return columns;
    }

    private static object ToDbValue(JsonElement value, string columnType, SqlDialect dialect, string table, int index, string field) =>
        value.ValueKind switch
        {
            JsonValueKind.Null => DBNull.Value,
            JsonValueKind.String when dialect.IsPostgres && columnType == PostgresTimestamp => Iso.Parse(value.GetString()!),
            JsonValueKind.String => value.GetString()!,
            JsonValueKind.True => 1L,
            JsonValueKind.False => 0L,
            JsonValueKind.Number => value.TryGetInt64(out var l) ? (object)l : value.GetDouble(),
            _ => throw new InvalidDataException($"seed.{table}[{index}].{field}: only strings, numbers, true/false and null are supported."),
        };
}

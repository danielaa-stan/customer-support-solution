using System.Text.Json;
using Microsoft.Data.Sqlite;

namespace SupportServer.Infrastructure.Db;

/// <summary>
/// Loads seed.json (format: contracts/02-data-model.md). Top-level keys are table names,
/// fields are column names. Names are checked against the schema, so a mistake in the seed gives a clear message.
/// </summary>
public static class SeedLoader
{
    private static readonly string[] Tables =
        ["users", "subscriptions", "payments", "usage_stats", "retention_offers_used"];

    public static int Load(SqliteConnection connection, string seedPath)
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

            var columns = GetColumns(connection, transaction, table);
            var index = 0;

            foreach (var row in rows.EnumerateArray())
            {
                var fields = row.EnumerateObject().ToList();
                foreach (var field in fields)
                {
                    if (!columns.Contains(field.Name))
                        throw new InvalidDataException(
                            $"seed.{table}[{index}]: unknown field '{field.Name}'. Columns: {string.Join(", ", columns)}.");
                }

                using var command = connection.CreateCommand();
                command.Transaction = transaction;
                var names = string.Join(", ", fields.Select(f => f.Name));
                var placeholders = string.Join(", ", fields.Select((_, i) => $"@p{i}"));
                command.CommandText = $"INSERT INTO {table} ({names}) VALUES ({placeholders})";
                for (var i = 0; i < fields.Count; i++)
                    command.Parameters.AddWithValue($"@p{i}", ToDbValue(fields[i].Value, table, index, fields[i].Name));

                try
                {
                    command.ExecuteNonQuery();
                }
                catch (SqliteException ex)
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

    private static HashSet<string> GetColumns(SqliteConnection connection, SqliteTransaction transaction, string table)
    {
        var columns = new HashSet<string>();
        using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = $"PRAGMA table_info({table})";
        using var reader = command.ExecuteReader();
        while (reader.Read()) columns.Add(reader.GetString(1));
        return columns;
    }

    private static object ToDbValue(JsonElement value, string table, int index, string field) => value.ValueKind switch
    {
        JsonValueKind.Null => DBNull.Value,
        JsonValueKind.String => value.GetString()!,
        JsonValueKind.True => 1L,
        JsonValueKind.False => 0L,
        JsonValueKind.Number => value.TryGetInt64(out var l) ? l : value.GetDouble(),
        _ => throw new InvalidDataException($"seed.{table}[{index}].{field}: only strings, numbers, true/false and null are supported."),
    };
}

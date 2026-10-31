using Npgsql;

namespace SupportServer.Infrastructure.Db;

public static class PostgresConnection
{
    /// <summary>Turns postgresql://user:password@host:port/database into an Npgsql connection string.</summary>
    public static string FromUrl(string url)
    {
        if (!url.Contains("://")) return url; // already a connection string

        var uri = new Uri(url);
        var credentials = uri.UserInfo.Split(':', 2);

        var builder = new NpgsqlConnectionStringBuilder
        {
            Host = uri.Host,
            Port = uri.Port > 0 ? uri.Port : 5432,
            Username = Uri.UnescapeDataString(credentials[0]),
            Database = Uri.UnescapeDataString(uri.AbsolutePath.TrimStart('/')),
        };
        if (credentials.Length > 1) builder.Password = Uri.UnescapeDataString(credentials[1]);

        return builder.ConnectionString;
    }

    /// <summary>Host and database only. Never contains the password, so it is safe to log.</summary>
    public static string Describe(string url)
    {
        if (!url.Contains("://")) return "(connection string)";
        var uri = new Uri(url);
        return $"{uri.Host}:{(uri.Port > 0 ? uri.Port : 5432)}{uri.AbsolutePath}";
    }
}

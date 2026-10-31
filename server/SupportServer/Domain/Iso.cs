using System.Globalization;

namespace SupportServer.Domain;

/// <summary>Усі дати в БД і контрактах: ISO 8601 UTC, напр. 2026-10-31T12:00:00Z.</summary>
public static class Iso
{
    public static DateTimeOffset Parse(string value) =>
        DateTimeOffset.Parse(value, CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);

    public static string Format(DateTimeOffset value) =>
        value.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture);

    /// <summary>Повних місяців між start та now (не менше 0).</summary>
    public static int WholeMonthsBetween(DateTimeOffset start, DateTimeOffset now)
    {
        var months = (now.Year - start.Year) * 12 + now.Month - start.Month;
        if (now.Day < start.Day) months--;
        return Math.Max(0, months);
    }
}

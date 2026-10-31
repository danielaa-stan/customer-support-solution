namespace SupportServer.Application;

public interface IClock
{
    DateTimeOffset UtcNow { get; }
}

public sealed class SystemClock : IClock
{
    public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;
}

/// <summary>Фіксований «поточний час» (DEMO_NOW), щоб демо й тести були детермінованими.</summary>
public sealed class FixedClock(DateTimeOffset now) : IClock
{
    public DateTimeOffset UtcNow => now;
}

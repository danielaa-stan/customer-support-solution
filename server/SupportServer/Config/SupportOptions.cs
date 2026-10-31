namespace SupportServer.Config;

/// <summary>Server settings, read from environment variables (see contracts/01-ownership.md).</summary>
/// <param name="AllowSessionSwitch">Local development only: lets sys_set_context change the user within one process.</param>
public sealed record SupportOptions(
    string DbPath,
    string SeedPath,
    DateTimeOffset? DemoNow,
    bool AllowSessionSwitch = false)
{
    public static SupportOptions FromEnvironment()
    {
        var db = RepoPaths.Resolve(Environment.GetEnvironmentVariable("SUPPORT_DB_PATH") ?? "runtime/support.db");

        var seedEnv = Environment.GetEnvironmentVariable("SEED_PATH");
        string seed;
        if (!string.IsNullOrWhiteSpace(seedEnv))
        {
            seed = RepoPaths.Resolve(seedEnv);
        }
        else
        {
            // Prefer the team seed (from zone C); fall back to the small dev seed.
            var teamSeed = RepoPaths.Resolve("data/seed/seed.json");
            seed = File.Exists(teamSeed) ? teamSeed : RepoPaths.Resolve("server/dev-seed.json");
        }

        // DEMO_NOW: an ISO date, or "real" for the real clock. Defaults to the fixed demo date.
        var demo = Environment.GetEnvironmentVariable("DEMO_NOW");
        DateTimeOffset? now = BusinessRules.DefaultDemoNow;
        if (!string.IsNullOrWhiteSpace(demo))
        {
            now = demo.Equals("real", StringComparison.OrdinalIgnoreCase)
                ? null
                : Domain.Iso.Parse(demo);
        }

        var allowSwitch = string.Equals(
            Environment.GetEnvironmentVariable("ALLOW_SESSION_SWITCH"), "true", StringComparison.OrdinalIgnoreCase);

        return new SupportOptions(db, seed, now, allowSwitch);
    }
}

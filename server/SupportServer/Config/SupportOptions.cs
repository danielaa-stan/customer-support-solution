namespace SupportServer.Config;

/// <summary>Налаштування сервера. Читаються зі змінних оточення (див. contracts/01-ownership.md).</summary>
public sealed record SupportOptions(string DbPath, string SeedPath, DateTimeOffset? DemoNow)
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
            var teamSeed = RepoPaths.Resolve("data/seed/seed.json");
            seed = File.Exists(teamSeed) ? teamSeed : RepoPaths.Resolve("server/dev-seed.json");
        }

        // DEMO_NOW: ISO-дата, або "real" для справжнього часу. За замовчуванням фіксована демо-дата.
        var demo = Environment.GetEnvironmentVariable("DEMO_NOW");
        DateTimeOffset? now = BusinessRules.DefaultDemoNow;
        if (!string.IsNullOrWhiteSpace(demo))
        {
            now = demo.Equals("real", StringComparison.OrdinalIgnoreCase)
                ? null
                : Domain.Iso.Parse(demo);
        }

        return new SupportOptions(db, seed, now);
    }
}

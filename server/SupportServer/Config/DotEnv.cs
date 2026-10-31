namespace SupportServer.Config;

/// <summary>
/// Minimal .env loader. The agent starts this server as a subprocess and may not forward its environment,
/// so the server reads the repository's .env itself. Variables that are already set are never overridden.
/// </summary>
public static class DotEnv
{
    public static void Load()
    {
        var path = Path.Combine(RepoPaths.RepoRoot, ".env");
        if (!File.Exists(path)) return;

        foreach (var raw in File.ReadAllLines(path))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#')) continue;

            var separator = line.IndexOf('=');
            if (separator <= 0) continue;

            var key = line[..separator].Trim();
            var value = line[(separator + 1)..].Trim();
            if (value.Length >= 2 && value[0] == value[^1] && value[0] is '"' or '\'')
                value = value[1..^1];

            if (value.Length == 0 || Environment.GetEnvironmentVariable(key) is not null) continue;
            Environment.SetEnvironmentVariable(key, value);
        }
    }
}

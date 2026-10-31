namespace SupportServer.Config;

/// <summary>Знаходить корінь репозиторію (папка з contracts/), щоб відносні шляхи не залежали від cwd.</summary>
public static class RepoPaths
{
    private static readonly Lazy<string> Root = new(FindRoot);

    public static string RepoRoot => Root.Value;

    public static string Resolve(string path) =>
        Path.IsPathRooted(path) ? path : Path.GetFullPath(Path.Combine(RepoRoot, path));

    private static string FindRoot()
    {
        foreach (var start in new[] { AppContext.BaseDirectory, Directory.GetCurrentDirectory() })
        {
            var dir = new DirectoryInfo(start);
            while (dir is not null)
            {
                if (Directory.Exists(Path.Combine(dir.FullName, "contracts")))
                    return dir.FullName;
                dir = dir.Parent;
            }
        }
        return Directory.GetCurrentDirectory();
    }
}

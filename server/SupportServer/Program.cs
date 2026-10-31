using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Serilog;
using Serilog.Events;
using Serilog.Extensions.Logging;
using SupportServer;
using SupportServer.Config;
using SupportServer.Infrastructure.Db;

// Logging is configured first so that startup problems are captured as well.
// stdout is reserved for the MCP protocol, so the console sink writes to stderr only.
// Diagnostic logs (this file) are separate from the business audit trail (audit_log table).
DotEnv.Load(); // read the repository .env (the agent may not forward its environment to this process)

var logDir = RepoPaths.Resolve(Environment.GetEnvironmentVariable("LOG_DIR") ?? "runtime/logs");
var minimumLevel = Enum.TryParse<LogEventLevel>(Environment.GetEnvironmentVariable("LOG_LEVEL"), ignoreCase: true, out var parsedLevel)
    ? parsedLevel
    : LogEventLevel.Information;

const string consoleTemplate = "{Timestamp:HH:mm:ss} [{Level:u3}] {Message:lj}{NewLine}{Exception}";
const string fileTemplate = "{Timestamp:yyyy-MM-dd HH:mm:ss.fff} [{Level:u3}] {Message:lj} {Properties:j}{NewLine}{Exception}";

Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Is(minimumLevel)
    .MinimumLevel.Override("Microsoft", LogEventLevel.Warning)
    .MinimumLevel.Override("System", LogEventLevel.Warning)
    .MinimumLevel.Override("ModelContextProtocol", LogEventLevel.Warning)
    .Enrich.FromLogContext()
    .WriteTo.Console(outputTemplate: consoleTemplate, standardErrorFromLevel: LogEventLevel.Verbose)
    .WriteTo.File(
        Path.Combine(logDir, "server-.log"),
        outputTemplate: fileTemplate,
        rollingInterval: RollingInterval.Day,
        retainedFileCountLimit: 7,
        shared: true)
    .CreateLogger();

try
{
    var options = SupportOptions.FromEnvironment();
    var startupLog = new SerilogLoggerFactory(Log.Logger).CreateLogger("Startup");

    // dotnet run --project server/SupportServer -- reset-db
    if (args.Contains("reset-db"))
    {
        DbInitializer.Reset(options, startupLog);
        return;
    }

    DbInitializer.EnsureCreated(options, startupLog);

    var builder = Host.CreateApplicationBuilder(args);
    builder.Logging.ClearProviders();
    builder.Logging.AddSerilog(Log.Logger, dispose: false);

    builder.Services.AddSupportServer(options);
    builder.Services
        .AddMcpServer()
        .WithStdioServerTransport()
        .WithToolsFromAssembly();

    Log.Information("Support MCP server starting (database: {Database}, clock: {Clock}, logs: {LogDir})",
        options.DatabaseUrl is { } url ? "PostgreSQL " + PostgresConnection.Describe(url) : "SQLite " + options.DbPath,
        options.DemoNow?.ToString("u") ?? "system", logDir);

    await builder.Build().RunAsync();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Server terminated unexpectedly");
    throw;
}
finally
{
    await Log.CloseAndFlushAsync();
}

using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using SupportServer;
using SupportServer.Config;
using SupportServer.Infrastructure.Db;

var options = SupportOptions.FromEnvironment();

// dotnet run --project server/SupportServer -- reset-db
if (args.Contains("reset-db"))
{
    DbInitializer.Reset(options);
    return;
}

DbInitializer.EnsureCreated(options);

var builder = Host.CreateApplicationBuilder(args);

// stdout зарезервовано під протокол MCP, тому всі логи йдуть у stderr.
builder.Logging.ClearProviders();
builder.Logging.AddConsole(o => o.LogToStandardErrorThreshold = LogLevel.Trace);

builder.Services.AddSupportServer(options);
builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithToolsFromAssembly();

await builder.Build().RunAsync();

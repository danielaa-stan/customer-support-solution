using Microsoft.Extensions.DependencyInjection;
using SupportServer.Application;
using SupportServer.Application.Ports;
using SupportServer.Application.Services;
using SupportServer.Config;
using SupportServer.Infrastructure.Audit;
using SupportServer.Infrastructure.Billing;
using SupportServer.Infrastructure.Db;

namespace SupportServer;

public static class ServiceCollectionExtensions
{
    /// <summary>Dependency wiring (composition root). Used by both Program and the tests.</summary>
    public static IServiceCollection AddSupportServer(this IServiceCollection services, SupportOptions options)
    {
        services.AddSingleton(options);
        services.AddSingleton<IClock>(options.DemoNow is { } now ? new FixedClock(now) : new SystemClock());
        services.AddSingleton(new SqliteConnectionFactory(options.DbPath));

        // Ports and adapters: swapping an implementation does not touch the rest of the code.
        services.AddSingleton<IBillingProvider, MockBillingProvider>();
        services.AddSingleton<IAuditLog, SqliteAuditLog>();

        services.AddSingleton(new SessionState(options.AllowSessionSwitch));
        services.AddSingleton<ToolRunner>();
        services.AddSingleton<AccountService>();
        services.AddSingleton<PaymentService>();
        return services;
    }
}

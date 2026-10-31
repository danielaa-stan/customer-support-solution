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
    /// <summary>Складання залежностей (composition root). Використовують і Program, і тести.</summary>
    public static IServiceCollection AddSupportServer(this IServiceCollection services, SupportOptions options)
    {
        services.AddSingleton(options);
        services.AddSingleton<IClock>(options.DemoNow is { } now ? new FixedClock(now) : new SystemClock());
        services.AddSingleton(new SqliteConnectionFactory(options.DbPath));

        // Порти й адаптери: заміна реалізації не чіпає решту коду.
        services.AddSingleton<IBillingProvider, MockBillingProvider>();
        services.AddSingleton<IAuditLog, SqliteAuditLog>();

        services.AddSingleton<SessionState>();
        services.AddSingleton<ToolRunner>();
        services.AddSingleton<AccountService>();
        services.AddSingleton<PaymentService>();
        return services;
    }
}

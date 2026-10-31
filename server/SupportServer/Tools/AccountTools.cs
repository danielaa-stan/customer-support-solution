using System.ComponentModel;
using ModelContextProtocol.Server;
using SupportServer.Application;
using SupportServer.Application.Services;
using SupportServer.Domain;

namespace SupportServer.Tools;

/// <summary>Thin MCP layer: tool description plus delegation. All logic lives in the services.</summary>
[McpServerToolType]
public sealed class AccountTools(ToolRunner runner, AccountService account)
{
    [McpServerTool(Name = "get_user_profile"),
     Description("Профіль поточного клієнта: підписка (план, статус, ціна, дата списання, стаж), " +
                 "активність за 30 днів і чи вже була пропозиція утримання. Лише читання.")]
    public string GetUserProfile() =>
        runner.Run("get_user_profile", AutonomyLevel.Read, new { }, ctx => account.GetProfile(ctx));
}

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
     Description("Profile of the current customer: subscription (plan, status, price, next billing date, tenure), " +
                 "30-day activity and whether a retention offer was already used. Read-only.")]
    public string GetUserProfile() =>
        runner.Run("get_user_profile", AutonomyLevel.Read, new { }, ctx => account.GetProfile(ctx));
}

using System.ComponentModel;
using System.Text.Json;
using ModelContextProtocol.Server;
using SupportServer.Application;
using SupportServer.Application.Services;
using SupportServer.Domain;

namespace SupportServer.Tools;

[McpServerToolType]
public sealed class EscalationTools(ToolRunner runner, EscalationService escalation)
{
    [McpServerTool(Name = "escalate_to_human"),
     Description("Hand the case over to a human agent: creates a ticket. Use it when a tool returns needs_human, " +
                 "or when you cannot resolve the issue. Include what was already done and, if you can, a recommended action.")]
    public string EscalateToHuman(
        [Description("low, normal, high or urgent")] string priority,
        [Description("Intent category: cancel_subscription, billing_issue, refund_request, plan_change, technical_issue, account_access, other")] string category,
        [Description("Short summary for the human agent: the problem, what was done, what is left")] string summary,
        [Description("Optional recommendation for the human: {tool, args, rationale, policy_ref}, or null")] JsonElement? suggested_action = null) =>
        runner.Run("escalate_to_human", AutonomyLevel.Auto, new { priority, category, summary, suggested_action },
            ctx => escalation.Escalate(ctx, priority, category, summary, suggested_action));
}

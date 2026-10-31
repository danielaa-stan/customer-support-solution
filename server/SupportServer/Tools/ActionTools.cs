using System.ComponentModel;
using ModelContextProtocol.Server;
using SupportServer.Application;
using SupportServer.Application.Services;
using SupportServer.Domain;

namespace SupportServer.Tools;

[McpServerToolType]
public sealed class ActionTools(ToolRunner runner, PendingActionService pending)
{
    [McpServerTool(Name = "confirm_action"),
     Description("Execute an action that was proposed earlier (pending_confirmation), after the customer explicitly " +
                 "agreed in a NEW message. Fails with CONFIRMATION_INVALID if no new customer message arrived.")]
    public string ConfirmAction(
        [Description("pending_action_id returned by the proposing tool")] string pending_action_id) =>
        runner.Run("confirm_action", AutonomyLevel.Confirm, new { pending_action_id },
            ctx => pending.Confirm(ctx, pending_action_id));

    [McpServerTool(Name = "reject_action"),
     Description("Discard a proposed action because the customer declined or changed their mind.")]
    public string RejectAction(
        [Description("pending_action_id returned by the proposing tool")] string pending_action_id) =>
        runner.Run("reject_action", AutonomyLevel.Auto, new { pending_action_id },
            ctx => pending.Reject(ctx, pending_action_id));
}

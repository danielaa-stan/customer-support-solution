using System.Text.Json;
using SupportServer.Application.Ports;
using SupportServer.Domain;

namespace SupportServer.Application.Services;

/// <summary>
/// Human-in-the-loop for risky actions: confirm or reject a proposal made earlier in the same session.
/// Confirmation is accepted only after a NEW customer message (user_turn is greater than at proposal time),
/// so the agent cannot propose and confirm inside one turn.
/// </summary>
public sealed class PendingActionService
{
    private readonly ISupportStore _store;
    private readonly IClock _clock;
    private readonly Dictionary<string, Func<ToolContext, JsonElement, ToolOutcome>> _executors;

    public PendingActionService(ISupportStore store, IClock clock, SubscriptionService subscriptions)
    {
        _store = store;
        _clock = clock;
        _executors = new()
        {
            [SubscriptionService.CancelTool] = (ctx, args) => subscriptions.ExecuteCancel(
                ctx, args.GetProperty("reason_code").GetString()!, args.GetProperty("effective").GetString()!),
        };
    }

    public ToolOutcome Confirm(ToolContext ctx, string pendingActionId)
    {
        var action = Find(ctx, pendingActionId);
        if (action is null) return NotFound();

        switch (action.Status)
        {
            case "confirmed":
                return ToolOutcome.Denied(ErrorCodes.AlreadyDone, "This action has already been confirmed and executed.");
            case "rejected" or "expired":
                return ToolOutcome.Denied(ErrorCodes.ConfirmationInvalid, $"This action was {action.Status} and can no longer be confirmed.");
        }

        if (ctx.UserTurn <= action.ProposedAtTurn)
        {
            return ToolOutcome.Denied(ErrorCodes.ConfirmationInvalid,
                "Confirmation requires a new customer message after the proposal. Ask the customer to confirm first.");
        }

        if (!_executors.TryGetValue(action.Tool, out var execute))
            return ToolOutcome.Fail(ErrorCodes.Internal, $"No executor for {action.Tool}.");

        using var args = JsonDocument.Parse(action.ArgsJson);
        var outcome = execute(ctx, args.RootElement.Clone());

        if (outcome.Ok) _store.ResolvePendingAction(action.Id, "confirmed", _clock.UtcNow);

        return outcome.AtLevel(AutonomyLevel.Confirm);
    }

    public ToolOutcome Reject(ToolContext ctx, string pendingActionId)
    {
        var action = Find(ctx, pendingActionId);
        if (action is null) return NotFound();

        switch (action.Status)
        {
            case "rejected":
                return ToolOutcome.Denied(ErrorCodes.AlreadyDone, "This action has already been rejected.");
            case "confirmed" or "expired":
                return ToolOutcome.Denied(ErrorCodes.ConfirmationInvalid, $"This action was {action.Status} and cannot be rejected.");
        }

        _store.ResolvePendingAction(action.Id, "rejected", _clock.UtcNow);
        return ToolOutcome.Done(new { pending_action_id = action.Id, status = "rejected" });
    }

    /// <summary>A customer can only reach pending actions from their own session.</summary>
    private PendingAction? Find(ToolContext ctx, string id)
    {
        var action = string.IsNullOrWhiteSpace(id) ? null : _store.GetPendingAction(id);
        return action is not null && action.UserId == ctx.UserId && action.SessionId == ctx.SessionId ? action : null;
    }

    private static ToolOutcome NotFound() =>
        ToolOutcome.Fail(ErrorCodes.NotFound, "Pending action not found in this session.");
}

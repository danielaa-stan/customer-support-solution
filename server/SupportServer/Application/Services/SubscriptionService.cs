using SupportServer.Application.Ports;
using SupportServer.Config;
using SupportServer.Domain;
using SupportServer.Domain.Policies;

namespace SupportServer.Application.Services;

/// <summary>Pause, plan changes and cancellation (proposal and execution).</summary>
public sealed class SubscriptionService(IBillingProvider billing, ISupportStore store, IClock clock)
{
    public const string CancelTool = "cancel_subscription";
    private const string EndOfPeriod = "end_of_period";
    private const string Immediate = "immediate";

    public ToolOutcome Pause(ToolContext ctx, int months, string reasonCode)
    {
        if (Validation.CheckReason(reasonCode) is { } invalid) return invalid;
        if (months < 1)
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument, "months must be at least 1.", reasonCode);
        if (months > BusinessRules.PauseMaxMonths)
            return ToolOutcome.Denied(ErrorCodes.PolicyDenied,
                $"A pause can last at most {BusinessRules.PauseMaxMonths} months.", PolicyRefs.Pause, reasonCode);

        var account = billing.GetAccount(ctx.UserId);
        if (account is null) return Validation.AccountNotFound();

        var sub = account.Subscription;
        if (sub.Status == "paused")
            return ToolOutcome.Denied(ErrorCodes.AlreadyDone, $"The subscription is already paused until {sub.PausedUntil}.", reasonCode: reasonCode);
        if (sub.Status != "active" || sub.CancelAt is not null)
            return ToolOutcome.Denied(ErrorCodes.PolicyDenied,
                "Only an active subscription without a scheduled cancellation can be paused.", PolicyRefs.Pause, reasonCode);

        var until = clock.UtcNow.AddMonths(months);
        if (!billing.PauseSubscription(ctx.UserId, until)) return StateChanged(reasonCode);

        return ToolOutcome.Done(new { paused_until = Iso.Format(until) }, reasonCode, PolicyRefs.Pause);
    }

    public ToolOutcome ChangePlan(ToolContext ctx, string newPlan, string reasonCode)
    {
        if (Validation.CheckReason(reasonCode) is { } invalid) return invalid;
        if (!PlanCatalog.IsKnown(newPlan))
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument, $"Unknown plan. Allowed values: {PlanCatalog.Allowed}.", reasonCode);

        var account = billing.GetAccount(ctx.UserId);
        if (account is null) return Validation.AccountNotFound();

        var sub = account.Subscription;
        if (sub.Status != "active")
            return ToolOutcome.Denied(ErrorCodes.PolicyDenied,
                "The plan can be changed only on an active subscription.", PolicyRefs.PlanChange, reasonCode);
        if (newPlan == sub.Plan && sub.PendingPlan is null)
            return ToolOutcome.Denied(ErrorCodes.AlreadyDone, $"The customer is already on the {newPlan} plan.", reasonCode: reasonCode);
        if (newPlan == sub.PendingPlan)
            return ToolOutcome.Denied(ErrorCodes.AlreadyDone, $"The change to {newPlan} is already scheduled.", reasonCode: reasonCode);
        if (newPlan == "student" && account.User.IsStudent != 1)
            return ToolOutcome.Denied(ErrorCodes.PolicyDenied, "The student plan requires verified student status.",
                PolicyRefs.StudentPlan, reasonCode);

        var price = PlanCatalog.PriceOf(newPlan);

        // Switching back to the current plan cancels a scheduled downgrade.
        if (newPlan == sub.Plan)
        {
            if (!billing.ChangePlanNow(ctx.UserId, newPlan, price)) return StateChanged(reasonCode);
            return ToolOutcome.Done(
                new { plan = newPlan, pending_plan = (string?)null, effective = "immediately", new_price_amount = price },
                reasonCode, PolicyRefs.PlanChange);
        }

        if (PlanCatalog.IsUpgrade(sub.Plan, newPlan))
        {
            if (!billing.ChangePlanNow(ctx.UserId, newPlan, price)) return StateChanged(reasonCode);
            return ToolOutcome.Done(
                new { plan = newPlan, pending_plan = (string?)null, effective = "immediately", new_price_amount = price },
                reasonCode, PolicyRefs.PlanChange);
        }

        if (!billing.SetPendingPlan(ctx.UserId, newPlan)) return StateChanged(reasonCode);
        return ToolOutcome.Done(
            new { plan = sub.Plan, pending_plan = newPlan, effective = "next_billing_date", effective_date = sub.NextBillingDate, new_price_amount = price },
            reasonCode, PolicyRefs.PlanChange);
    }

    /// <summary>Step 1 of cancellation: records a pending action and asks the agent to get explicit confirmation.</summary>
    public ToolOutcome ProposeCancel(ToolContext ctx, string reasonCode, string effective)
    {
        if (Validation.CheckReason(reasonCode) is { } invalid) return invalid;
        if (effective is not (EndOfPeriod or Immediate))
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument, "effective must be end_of_period or immediate.", reasonCode);

        var account = billing.GetAccount(ctx.UserId);
        if (account is null) return Validation.AccountNotFound();

        var sub = account.Subscription;
        if (sub.Status == "canceled")
            return ToolOutcome.Denied(ErrorCodes.AlreadyDone, "The subscription is already canceled.", reasonCode: reasonCode);
        if (sub.CancelAt is not null && effective == EndOfPeriod)
            return ToolOutcome.Denied(ErrorCodes.AlreadyDone, $"Cancellation is already scheduled for {sub.CancelAt}.", reasonCode: reasonCode);

        var argsJson = Json.Serialize(new { reason_code = reasonCode, effective });

        // The same proposal repeated in the same session returns the existing one.
        var action = store.FindPendingAction(ctx.SessionId, CancelTool, argsJson);
        if (action is null)
        {
            action = new PendingAction
            {
                Id = "pa_" + Guid.NewGuid().ToString("N")[..8],
                SessionId = ctx.SessionId,
                UserId = ctx.UserId,
                Tool = CancelTool,
                ArgsJson = argsJson,
                Summary = DescribeCancel(sub, effective),
                ProposedAtTurn = ctx.UserTurn,
                Status = "pending",
                CreatedAt = Iso.Format(clock.UtcNow),
            };
            store.CreatePendingAction(action);
        }

        return ToolOutcome.PendingConfirmation(
            new { pending_action_id = action.Id, summary = action.Summary, requires_user_confirmation = true },
            reasonCode, PolicyRefs.CancelRight);
    }

    /// <summary>Step 2 of cancellation, called only from confirm_action after the customer agreed.</summary>
    public ToolOutcome ExecuteCancel(ToolContext ctx, string reasonCode, string effective)
    {
        var account = billing.GetAccount(ctx.UserId);
        if (account is null) return Validation.AccountNotFound();

        var sub = account.Subscription;
        if (sub.Status == "canceled")
            return ToolOutcome.Denied(ErrorCodes.AlreadyDone, "The subscription is already canceled.", reasonCode: reasonCode);

        var now = clock.UtcNow;

        if (effective == Immediate)
        {
            if (!billing.CancelNow(ctx.UserId, now)) return StateChanged(reasonCode);
            return ToolOutcome.Done(new { status = "canceled", cancel_at = Iso.Format(now) }, reasonCode, PolicyRefs.CancelEndOfPeriod);
        }

        if (sub.CancelAt is not null)
            return ToolOutcome.Denied(ErrorCodes.AlreadyDone, $"Cancellation is already scheduled for {sub.CancelAt}.", reasonCode: reasonCode);

        var cancelAt = sub.NextBillingDate is { } next ? Iso.Parse(next) : now;
        if (!billing.ScheduleCancellation(ctx.UserId, cancelAt)) return StateChanged(reasonCode);

        // Access continues until cancel_at, so the status stays active.
        return ToolOutcome.Done(new { status = "active", cancel_at = Iso.Format(cancelAt) }, reasonCode, PolicyRefs.CancelEndOfPeriod);
    }

    private static string DescribeCancel(Subscription sub, string effective) =>
        effective == Immediate
            ? $"Cancel the {sub.Plan} subscription immediately. Access ends now and no further charges are made."
            : $"Cancel the {sub.Plan} subscription at the end of the paid period" +
              (sub.NextBillingDate is null ? "." : $" ({sub.NextBillingDate}). Access continues until then and no further charges are made.");

    private static ToolOutcome StateChanged(string reasonCode) =>
        ToolOutcome.Denied(ErrorCodes.PolicyDenied, "The subscription state changed, the action cannot be applied.", reasonCode: reasonCode);
}

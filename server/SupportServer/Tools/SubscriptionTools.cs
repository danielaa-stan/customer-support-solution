using System.ComponentModel;
using ModelContextProtocol.Server;
using SupportServer.Application;
using SupportServer.Application.Services;
using SupportServer.Domain;

namespace SupportServer.Tools;

[McpServerToolType]
public sealed class SubscriptionTools(ToolRunner runner, SubscriptionService subscriptions)
{
    [McpServerTool(Name = "pause_subscription"),
     Description("Pause the subscription for 1 to 3 months. No charges during the pause; it resumes automatically.")]
    public string PauseSubscription(
        [Description("Number of months, from 1 to 3")] int months,
        [Description("Reason: price_too_high, low_usage, technical_problems, switching_competitor, double_charge, billing_confusion, temporary_break, other, unknown")] string reason_code) =>
        runner.Run("pause_subscription", AutonomyLevel.Auto, new { months, reason_code },
            ctx => subscriptions.Pause(ctx, months, reason_code));

    [McpServerTool(Name = "change_plan"),
     Description("Change the plan: individual, duo, family or student (student needs verified student status). " +
                 "Upgrades apply immediately, downgrades at the next billing date.")]
    public string ChangePlan(
        [Description("Target plan: individual, duo, family or student")] string new_plan,
        [Description("Reason: price_too_high, low_usage, technical_problems, switching_competitor, double_charge, billing_confusion, temporary_break, other, unknown")] string reason_code) =>
        runner.Run("change_plan", AutonomyLevel.Auto, new { new_plan, reason_code },
            ctx => subscriptions.ChangePlan(ctx, new_plan, reason_code));

    [McpServerTool(Name = "cancel_subscription"),
     Description("Propose cancelling the subscription. Does NOT cancel yet: it returns pending_confirmation with a " +
                 "summary. Explain the consequences to the customer, wait for their explicit confirmation in a new message, " +
                 "then call confirm_action. Offer at most one alternative before this, and never pressure a customer who insists.")]
    public string CancelSubscription(
        [Description("Reason: price_too_high, low_usage, technical_problems, switching_competitor, double_charge, billing_confusion, temporary_break, other, unknown")] string reason_code,
        [Description("end_of_period (default, access continues until the paid period ends) or immediate")] string effective = "end_of_period") =>
        runner.Run("cancel_subscription", AutonomyLevel.Confirm, new { reason_code, effective },
            ctx => subscriptions.ProposeCancel(ctx, reason_code, effective));
}

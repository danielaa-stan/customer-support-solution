using System.ComponentModel;
using ModelContextProtocol.Server;
using SupportServer.Application;
using SupportServer.Application.Services;
using SupportServer.Domain;

namespace SupportServer.Tools;

[McpServerToolType]
public sealed class PaymentTools(ToolRunner runner, PaymentService payments)
{
    [McpServerTool(Name = "get_payments"),
     Description("Payment history of the current customer (newest first) and a list of payments " +
                 "that look like double charges. Read-only.")]
    public string GetPayments(
        [Description("How many payments to return, from 1 to 50")] int limit = 10) =>
        runner.Run("get_payments", AutonomyLevel.Read, new { limit }, ctx => payments.GetPayments(ctx, limit));

    [McpServerTool(Name = "issue_refund"),
     Description("Refund a payment if the policy allows it (14-day window, automatic limit). " +
                 "If the amount exceeds the limit it returns needs_human: then hand the case to a human.")]
    public string IssueRefund(
        [Description("Payment id from get_payments")] string payment_id,
        [Description("Reason: price_too_high, low_usage, technical_problems, switching_competitor, double_charge, billing_confusion, temporary_break, other, unknown")] string reason_code,
        [Description("Policy clause you rely on, format doc_id#section, e.g. refund-policy#2.2")] string policy_ref) =>
        runner.Run("issue_refund", AutonomyLevel.Auto, new { payment_id, reason_code, policy_ref },
            ctx => payments.IssueRefund(ctx, payment_id, reason_code, policy_ref));
}

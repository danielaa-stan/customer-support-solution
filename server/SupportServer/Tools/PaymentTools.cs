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
     Description("Історія платежів поточного клієнта (від нових до старих) і список платежів, " +
                 "схожих на подвійне списання. Лише читання.")]
    public string GetPayments(
        [Description("Скільки платежів повернути, від 1 до 50")] int limit = 10) =>
        runner.Run("get_payments", AutonomyLevel.Read, new { limit }, ctx => payments.GetPayments(ctx, limit));

    [McpServerTool(Name = "issue_refund"),
     Description("Повернути гроші за платіж, якщо це дозволяє політика (вікно 14 днів, автоматичний ліміт). " +
                 "Якщо сума перевищує ліміт, поверне needs_human: тоді передайте кейс людині.")]
    public string IssueRefund(
        [Description("Ідентифікатор платежу з get_payments")] string payment_id,
        [Description("Причина: price_too_high, low_usage, technical_problems, switching_competitor, double_charge, billing_confusion, temporary_break, other, unknown")] string reason_code,
        [Description("Пункт політики, на який спираєтесь, формат doc_id#розділ, напр. refund-policy#2.2")] string policy_ref) =>
        runner.Run("issue_refund", AutonomyLevel.Auto, new { payment_id, reason_code, policy_ref },
            ctx => payments.IssueRefund(ctx, payment_id, reason_code, policy_ref));
}

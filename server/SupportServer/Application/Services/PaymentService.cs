using System.Text.RegularExpressions;
using SupportServer.Application.Ports;
using SupportServer.Config;
using SupportServer.Domain;
using SupportServer.Domain.Policies;

namespace SupportServer.Application.Services;

public sealed partial class PaymentService(IBillingProvider billing, IClock clock)
{
    private const int MaxPayments = 50;

    [GeneratedRegex(@"^[a-z0-9-]+#\d+(\.\d+)*$")]
    private static partial Regex PolicyRefFormat();

    public ToolOutcome GetPayments(ToolContext ctx, int limit)
    {
        var payments = billing.GetPayments(ctx.UserId, Math.Clamp(limit, 1, MaxPayments));
        var duplicates = DuplicateChargeDetector.Find(payments);

        return ToolOutcome.Done(new
        {
            payments = payments.Select(p => new
            {
                id = p.Id,
                amount = p.Amount,
                currency = p.Currency,
                kind = p.Kind,
                status = p.Status,
                charged_at = p.ChargedAt,
                refunded_at = p.RefundedAt,
                refund_reason = p.RefundReason,
            }).ToList(),
            duplicate_charge_candidates = duplicates
                .Select(d => new { payment_id = d.PaymentId, duplicate_of = d.DuplicateOf })
                .ToList(),
        });
    }

    public ToolOutcome IssueRefund(ToolContext ctx, string paymentId, string reasonCode, string policyRef)
    {
        if (string.IsNullOrWhiteSpace(paymentId))
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument, "payment_id is required.");

        if (!ReasonCodes.IsValid(reasonCode))
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument,
                $"Unknown reason_code. Allowed values: {ReasonCodes.Allowed}.");

        if (string.IsNullOrWhiteSpace(policyRef) || !PolicyRefFormat().IsMatch(policyRef))
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument,
                "policy_ref is required and must look like doc_id#section, e.g. refund-policy#2.1.", reasonCode);

        var payment = billing.GetPayment(ctx.UserId, paymentId);
        if (payment is null)
            return ToolOutcome.Fail(ErrorCodes.NotFound,
                "Payment not found among this user's payments.", reasonCode);

        var decision = RefundPolicy.Evaluate(payment, clock.UtcNow);
        switch (decision.Verdict)
        {
            case RefundVerdict.AlreadyRefunded:
                return ToolOutcome.Denied(ErrorCodes.AlreadyDone, decision.Message, reasonCode: reasonCode);
            case RefundVerdict.NotRefundable:
            case RefundVerdict.WindowExpired:
                return ToolOutcome.Denied(ErrorCodes.PolicyDenied, decision.Message, decision.PolicyRef, reasonCode);
            case RefundVerdict.OverAutoLimit:
                return ToolOutcome.HumanRequired(ErrorCodes.LimitExceeded, decision.Message, decision.PolicyRef, reasonCode);
        }

        // The "double charge" claim is verified against the data instead of trusting the model.
        if (reasonCode == ReasonCodes.DoubleCharge)
        {
            var isDuplicate = DuplicateChargeDetector
                .Find(billing.GetPayments(ctx.UserId, MaxPayments))
                .Any(d => d.PaymentId == payment.Id);
            if (!isDuplicate)
                return ToolOutcome.Denied(ErrorCodes.PolicyDenied,
                    "No double charge was found for this payment.", PolicyRefs.DuplicateCharge, reasonCode);
        }

        if (!billing.RefundPayment(payment.Id, reasonCode, clock.UtcNow))
            return ToolOutcome.Denied(ErrorCodes.AlreadyDone, $"Payment {payment.Id} has already been refunded.",
                reasonCode: reasonCode);

        return ToolOutcome.Done(new
        {
            payment_id = payment.Id,
            refunded_amount = payment.Amount,
            currency = payment.Currency,
        }, reasonCode, policyRef);
    }
}

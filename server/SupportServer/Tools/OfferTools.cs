using System.ComponentModel;
using ModelContextProtocol.Server;
using SupportServer.Application;
using SupportServer.Application.Services;
using SupportServer.Domain;

namespace SupportServer.Tools;

[McpServerToolType]
public sealed class OfferTools(ToolRunner runner, OfferService offers)
{
    [McpServerTool(Name = "get_available_offers"),
     Description("Retention offers the current customer is eligible for right now. The server checks eligibility; " +
                 "never offer anything that is not in this list. Read-only.")]
    public string GetAvailableOffers() =>
        runner.Run("get_available_offers", AutonomyLevel.Read, new { }, ctx => offers.GetAvailableOffers(ctx));

    [McpServerTool(Name = "apply_retention_offer"),
     Description("Apply a retention offer from get_available_offers. Use it at most once per conversation, " +
                 "after you understood why the customer wants to leave.")]
    public string ApplyRetentionOffer(
        [Description("Offer code from get_available_offers, e.g. discount_50_3m")] string offer_code,
        [Description("Reason: price_too_high, low_usage, technical_problems, switching_competitor, double_charge, billing_confusion, temporary_break, other, unknown")] string reason_code) =>
        runner.Run("apply_retention_offer", AutonomyLevel.Auto, new { offer_code, reason_code },
            ctx => offers.ApplyRetentionOffer(ctx, offer_code, reason_code));
}

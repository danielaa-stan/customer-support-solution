using System.Text.Json;
using System.Text.RegularExpressions;
using SupportServer.Application.Ports;
using SupportServer.Config;
using SupportServer.Domain;

namespace SupportServer.Application.Services;

/// <summary>Hands a case over to a human agent with a summary and an optional recommended action (copilot).</summary>
public sealed partial class EscalationService(ISupportStore store, IClock clock)
{
    private const int MaxSummaryLength = 2000;

    private static readonly HashSet<string> Priorities = ["low", "normal", "high", "urgent"];

    private static readonly HashSet<string> SuggestableTools =
        ["issue_refund", "cancel_subscription", "change_plan", "pause_subscription", "apply_retention_offer"];

    [GeneratedRegex(@"^[a-z0-9-]+#\d+(\.\d+)*$")]
    private static partial Regex PolicyRefFormat();

    public ToolOutcome Escalate(ToolContext ctx, string priority, string category, string summary, JsonElement? suggestedAction)
    {
        if (!Priorities.Contains(priority))
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument, $"Unknown priority. Allowed values: {string.Join(", ", Priorities)}.");
        if (!Intents.IsValid(category))
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument, $"Unknown category. Allowed values: {Intents.Allowed}.");
        if (string.IsNullOrWhiteSpace(summary) || summary.Length > MaxSummaryLength)
            return ToolOutcome.Fail(ErrorCodes.InvalidArgument, $"summary is required and must be at most {MaxSummaryLength} characters.");

        string? suggestedJson = null;
        if (suggestedAction is { } suggestion && suggestion.ValueKind is not (JsonValueKind.Null or JsonValueKind.Undefined))
        {
            var problem = ValidateSuggestion(suggestion);
            if (problem is not null) return ToolOutcome.Fail(ErrorCodes.InvalidArgument, problem);
            suggestedJson = suggestion.GetRawText();
        }

        var ticket = new Ticket
        {
            Id = "tkt_" + Guid.NewGuid().ToString("N")[..8],
            UserId = ctx.UserId,
            SessionId = ctx.SessionId,
            Priority = priority,
            Category = category,
            Summary = summary.Trim(),
            SuggestedActionJson = suggestedJson,
            Status = "open",
            CreatedAt = Iso.Format(clock.UtcNow),
        };
        store.CreateTicket(ticket);

        return ToolOutcome.Done(new { ticket_id = ticket.Id }, policyRef: PolicyRefs.Escalation);
    }

    private static string? ValidateSuggestion(JsonElement suggestion)
    {
        if (suggestion.ValueKind != JsonValueKind.Object)
            return "suggested_action must be an object {tool, args, rationale, policy_ref} or null.";

        if (!suggestion.TryGetProperty("tool", out var tool) || tool.ValueKind != JsonValueKind.String
            || !SuggestableTools.Contains(tool.GetString()!))
            return $"suggested_action.tool must be one of: {string.Join(", ", SuggestableTools)}.";

        if (suggestion.TryGetProperty("policy_ref", out var policyRef) && policyRef.ValueKind == JsonValueKind.String
            && !PolicyRefFormat().IsMatch(policyRef.GetString()!))
            return "suggested_action.policy_ref must look like doc_id#section, e.g. refund-policy#2.3.";

        return null;
    }
}

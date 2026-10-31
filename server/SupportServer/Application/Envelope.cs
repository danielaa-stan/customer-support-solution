using System.Text.Json;
using System.Text.Json.Serialization;
using SupportServer.Domain;

namespace SupportServer.Application;

/// <summary>The common response format of every tool (contracts/03-mcp-tools.md).</summary>
public sealed record ToolEnvelope(
    bool Ok,
    ResultStatus Status,
    object? Data,
    ToolError? Error,
    bool NeedsHuman,
    long? AuditId);

public static class Json
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DictionaryKeyPolicy = JsonNamingPolicy.SnakeCaseLower,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower) },
    };

    public static string Serialize(object? value) => JsonSerializer.Serialize(value, Options);

    public static string ToEnvelopeJson(ToolOutcome outcome, long? auditId) =>
        Serialize(new ToolEnvelope(outcome.Ok, outcome.Status, outcome.Data, outcome.Error, outcome.NeedsHuman, auditId));
}

using SupportServer.Domain;

namespace SupportServer.Application;

/// <summary>Shared argument checks. A returned outcome means "stop and answer with this".</summary>
public static class Validation
{
    public static ToolOutcome? CheckReason(string? reasonCode) =>
        ReasonCodes.IsValid(reasonCode)
            ? null
            : ToolOutcome.Fail(ErrorCodes.InvalidArgument, $"Unknown reason_code. Allowed values: {ReasonCodes.Allowed}.");

    public static ToolOutcome AccountNotFound() =>
        ToolOutcome.Fail(ErrorCodes.NotFound, "User account not found.");
}

using SupportServer.Domain;

namespace SupportServer.Application;

/// <summary>Коди помилок (contracts/03-mcp-tools.md).</summary>
public static class ErrorCodes
{
    public const string NoContext = "NO_CONTEXT";
    public const string NotFound = "NOT_FOUND";
    public const string InvalidArgument = "INVALID_ARGUMENT";
    public const string PolicyDenied = "POLICY_DENIED";
    public const string NotEligible = "NOT_ELIGIBLE";
    public const string AlreadyDone = "ALREADY_DONE";
    public const string LimitExceeded = "LIMIT_EXCEEDED";
    public const string ConfirmationRequired = "CONFIRMATION_REQUIRED";
    public const string ConfirmationInvalid = "CONFIRMATION_INVALID";
    public const string Internal = "INTERNAL";
}

public sealed record ToolError(string Code, string Message, string? PolicyRef = null);

/// <summary>
/// Результат роботи сервісу. Сервіси повертають його, а не кидають винятки для бізнес-відмов.
/// ToolRunner перетворює його на відповідь MCP та запис в audit_log.
/// </summary>
public sealed class ToolOutcome
{
    public ResultStatus Status { get; private init; }
    public object? Data { get; private init; }
    public ToolError? Error { get; private init; }
    public bool NeedsHuman { get; private init; }
    public string? ReasonCode { get; private init; }
    public string? PolicyRef { get; private init; }

    /// <summary>Якщо задано, перекриває рівень автономності, оголошений інструментом (для audit_log).</summary>
    public AutonomyLevel? LevelOverride { get; private init; }

    public bool Ok => Status is ResultStatus.Done or ResultStatus.PendingConfirmation;

    public static ToolOutcome Done(object? data, string? reasonCode = null, string? policyRef = null) =>
        new() { Status = ResultStatus.Done, Data = data, ReasonCode = reasonCode, PolicyRef = policyRef };

    public static ToolOutcome PendingConfirmation(object data, string? reasonCode = null, string? policyRef = null) =>
        new() { Status = ResultStatus.PendingConfirmation, Data = data, ReasonCode = reasonCode, PolicyRef = policyRef,
                LevelOverride = AutonomyLevel.Confirm };

    /// <summary>Політика або стан забороняє дію (status = denied).</summary>
    public static ToolOutcome Denied(string code, string message, string? policyRef = null, string? reasonCode = null) =>
        new() { Status = ResultStatus.Denied, Error = new ToolError(code, message, policyRef),
                ReasonCode = reasonCode, PolicyRef = policyRef };

    /// <summary>Дію можна виконати лише людині (status = needs_human).</summary>
    public static ToolOutcome HumanRequired(string code, string message, string? policyRef = null, string? reasonCode = null) =>
        new() { Status = ResultStatus.NeedsHuman, Error = new ToolError(code, message, policyRef),
                NeedsHuman = true, ReasonCode = reasonCode, PolicyRef = policyRef,
                LevelOverride = AutonomyLevel.HumanOnly };

    /// <summary>Неправильні дані або збій (status = error).</summary>
    public static ToolOutcome Fail(string code, string message, string? reasonCode = null) =>
        new() { Status = ResultStatus.Error, Error = new ToolError(code, message), ReasonCode = reasonCode };
}

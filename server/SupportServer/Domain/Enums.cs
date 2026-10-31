using System.Text.Json;

namespace SupportServer.Domain;

/// <summary>Autonomy levels (contracts/03-mcp-tools.md).</summary>
public enum AutonomyLevel { Read, Auto, Confirm, HumanOnly }

/// <summary>The status field of a tool response.</summary>
public enum ResultStatus { Done, PendingConfirmation, Denied, NeedsHuman, Error }

public static class EnumExtensions
{
    /// <summary>HumanOnly -> "human_only", PendingConfirmation -> "pending_confirmation".</summary>
    public static string ToSnake<T>(this T value) where T : struct, Enum =>
        JsonNamingPolicy.SnakeCaseLower.ConvertName(value.ToString());
}

/// <summary>Enum reason_code (contracts/06-transcript-and-analysis.md).</summary>
public static class ReasonCodes
{
    public const string DoubleCharge = "double_charge";

    private static readonly HashSet<string> All =
    [
        "price_too_high", "low_usage", "technical_problems", "switching_competitor",
        "double_charge", "billing_confusion", "temporary_break", "other", "unknown",
    ];

    public static bool IsValid(string? code) => code is not null && All.Contains(code);

    public static string Allowed => string.Join(", ", All.Order());
}

namespace SupportServer.Domain;

// Models mirror the tables in contracts/schema.sql. Dapper maps snake_case columns to PascalCase properties.

public sealed class User
{
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";
    public string Email { get; set; } = "";
    public string Country { get; set; } = "";
    public long IsStudent { get; set; }
    public string CreatedAt { get; set; } = "";
}

public sealed class Subscription
{
    public string Id { get; set; } = "";
    public string UserId { get; set; } = "";
    public string Plan { get; set; } = "";
    public string? PendingPlan { get; set; }
    public string Status { get; set; } = "";
    public double PriceAmount { get; set; }
    public string PriceCurrency { get; set; } = "USD";
    public string StartedAt { get; set; } = "";
    public string? NextBillingDate { get; set; }
    public string? PausedUntil { get; set; }
    public string? CancelAt { get; set; }
    public long DiscountPercent { get; set; }
    public long DiscountPaymentsLeft { get; set; }
}

public sealed class Payment
{
    public string Id { get; set; } = "";
    public string UserId { get; set; } = "";
    public double Amount { get; set; }
    public string Currency { get; set; } = "USD";
    public string Kind { get; set; } = "";
    public string Status { get; set; } = "";
    public string ChargedAt { get; set; } = "";
    public string? RefundedAt { get; set; }
    public string? RefundReason { get; set; }
}

public sealed class UsageStats
{
    public string UserId { get; set; } = "";
    public double ListeningHours30d { get; set; }
    public string? LastActiveAt { get; set; }
    public long DevicesCount { get; set; } = 1;
    public long OfflineDownloads { get; set; }
}

public sealed record UserAccount(User User, Subscription Subscription, UsageStats Usage);

public sealed class PendingAction
{
    public string Id { get; set; } = "";
    public string SessionId { get; set; } = "";
    public string UserId { get; set; } = "";
    public string Tool { get; set; } = "";
    public string ArgsJson { get; set; } = "";
    public string Summary { get; set; } = "";
    public long ProposedAtTurn { get; set; }
    public string Status { get; set; } = "pending";
    public string CreatedAt { get; set; } = "";
    public string? ResolvedAt { get; set; }
}

public sealed class Ticket
{
    public string Id { get; set; } = "";
    public string UserId { get; set; } = "";
    public string SessionId { get; set; } = "";
    public string Priority { get; set; } = "";
    public string Category { get; set; } = "";
    public string Summary { get; set; } = "";
    public string? SuggestedActionJson { get; set; }
    public string Status { get; set; } = "open";
    public string CreatedAt { get; set; } = "";
}

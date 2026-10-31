namespace SupportServer.Application.Ports;

public sealed record AuditEntry(
    string Ts,
    string SessionId,
    string? UserId,
    string Tool,
    string ArgsJson,
    string ResultStatus,
    string? ErrorCode,
    string AutonomyLevel,
    string? ReasonCode,
    string? PolicyRef,
    string Actor);

public interface IAuditLog
{
    /// <summary>Записує подію й повертає її id.</summary>
    long Write(AuditEntry entry);
}

using Dapper;
using SupportServer.Application.Ports;
using SupportServer.Infrastructure.Db;

namespace SupportServer.Infrastructure.Audit;

/// <summary>Append-only log: inserts only, no updates or deletes. Works on SQLite and PostgreSQL.</summary>
public sealed class SqlAuditLog(DbConnectionFactory db) : IAuditLog
{
    public long Write(AuditEntry entry)
    {
        using var c = db.Open();
        var d = db.Dialect;
        return c.ExecuteScalar<long>(
            $"""
            INSERT INTO audit_log
              (ts, session_id, user_id, tool, args_json, result_status, error_code,
               autonomy_level, reason_code, policy_ref, actor)
            VALUES
              ({d.Ts("@Ts")}, @SessionId, @UserId, @Tool, @ArgsJson, @ResultStatus, @ErrorCode,
               @AutonomyLevel, @ReasonCode, @PolicyRef, @Actor)
            RETURNING id
            """,
            entry);
    }
}

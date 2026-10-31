using Dapper;
using SupportServer.Application.Ports;
using SupportServer.Infrastructure.Db;

namespace SupportServer.Infrastructure.Audit;

/// <summary>Append-only журнал: лише вставка, жодних оновлень чи видалень.</summary>
public sealed class SqliteAuditLog(SqliteConnectionFactory db) : IAuditLog
{
    public long Write(AuditEntry entry)
    {
        using var c = db.Open();
        return c.ExecuteScalar<long>(
            """
            INSERT INTO audit_log
              (ts, session_id, user_id, tool, args_json, result_status, error_code,
               autonomy_level, reason_code, policy_ref, actor)
            VALUES
              (@Ts, @SessionId, @UserId, @Tool, @ArgsJson, @ResultStatus, @ErrorCode,
               @AutonomyLevel, @ReasonCode, @PolicyRef, @Actor);
            SELECT last_insert_rowid();
            """,
            entry);
    }
}

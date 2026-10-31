using Microsoft.Extensions.Logging;
using SupportServer.Application.Ports;
using SupportServer.Domain;

namespace SupportServer.Application;

/// <summary>
/// Єдина точка виконання будь-якого інструмента. Гарантує, що для КОЖНОГО виклику:
/// 1) є контекст сесії, 2) виняток не виходить назовні, 3) подію записано в audit_log
/// (також для відмов), 4) відповідь має єдиний формат.
/// Інструменти MCP лише викликають Run, тому «забути залогувати» неможливо.
/// </summary>
public sealed class ToolRunner(SessionState session, IAuditLog audit, IClock clock, ILogger<ToolRunner> log)
{
    public string Run(string tool, AutonomyLevel level, object args, Func<ToolContext, ToolOutcome> handler)
    {
        var ctx = session.Current;
        ToolOutcome outcome;

        if (ctx is null)
        {
            outcome = ToolOutcome.Fail(ErrorCodes.NoContext,
                "Контекст сесії не задано (службовий виклик sys_set_context не виконано).");
        }
        else
        {
            try
            {
                outcome = handler(ctx);
            }
            catch (Exception ex)
            {
                log.LogError(ex, "Tool {Tool} failed", tool);
                outcome = ToolOutcome.Fail(ErrorCodes.Internal, "Внутрішня помилка сервера. Спробуйте пізніше.");
            }
        }

        long? auditId = null;
        try
        {
            auditId = audit.Write(new AuditEntry(
                Ts: Iso.Format(clock.UtcNow),
                SessionId: ctx?.SessionId ?? "unknown",
                UserId: ctx?.UserId,
                Tool: tool,
                ArgsJson: Json.Serialize(args),
                ResultStatus: outcome.Status.ToSnake(),
                ErrorCode: outcome.Error?.Code,
                AutonomyLevel: (outcome.LevelOverride ?? level).ToSnake(),
                ReasonCode: outcome.ReasonCode,
                PolicyRef: outcome.PolicyRef,
                Actor: "agent"));
        }
        catch (Exception ex)
        {
            log.LogError(ex, "Audit write failed for {Tool}", tool);
        }

        return Json.ToEnvelopeJson(outcome, auditId);
    }
}

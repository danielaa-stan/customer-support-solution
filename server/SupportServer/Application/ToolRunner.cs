using System.Diagnostics;
using Microsoft.Extensions.Logging;
using SupportServer.Application.Ports;
using SupportServer.Domain;

namespace SupportServer.Application;

/// <summary>
/// The single execution point for every tool. For EVERY call it guarantees that:
/// 1) a session context exists, 2) no exception escapes, 3) the call is recorded in audit_log
/// (denials included), 4) the response has the common envelope format, 5) one diagnostic log line
/// with session, user, tool, outcome and duration is written.
/// MCP tools only call Run, so "forgetting to audit" is not possible.
/// </summary>
public sealed class ToolRunner(SessionState session, IAuditLog audit, IClock clock, ILogger<ToolRunner> log)
{
    public string Run(string tool, AutonomyLevel level, object args, Func<ToolContext, ToolOutcome> handler)
    {
        var ctx = session.Current;

        // Everything logged while the handler runs carries session, user and tool.
        using var scope = log.BeginScope(new Dictionary<string, object>
        {
            ["SessionId"] = ctx?.SessionId ?? "-",
            ["UserId"] = ctx?.UserId ?? "-",
            ["Tool"] = tool,
        });

        var argsJson = Json.Serialize(args);
        log.LogDebug("{Tool} called with {Args}", tool, argsJson);

        var watch = Stopwatch.StartNew();
        ToolOutcome outcome;

        if (ctx is null)
        {
            outcome = ToolOutcome.Fail(ErrorCodes.NoContext,
                "The session context is not set (the internal sys_set_context call has not been made).");
        }
        else
        {
            try
            {
                outcome = handler(ctx);
            }
            catch (Exception ex)
            {
                log.LogError(ex, "{Tool} failed with an unhandled exception", tool);
                outcome = ToolOutcome.Fail(ErrorCodes.Internal, "Internal server error. Please try again later.");
            }
        }

        watch.Stop();

        long? auditId = null;
        try
        {
            auditId = audit.Write(new AuditEntry(
                Ts: Iso.Format(clock.UtcNow),
                SessionId: ctx?.SessionId ?? "unknown",
                UserId: ctx?.UserId,
                Tool: tool,
                ArgsJson: argsJson,
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

        LogOutcome(tool, ctx, outcome, watch.ElapsedMilliseconds, auditId);
        return Json.ToEnvelopeJson(outcome, auditId);
    }

    private void LogOutcome(string tool, ToolContext? ctx, ToolOutcome outcome, long elapsedMs, long? auditId)
    {
        // Successful calls are routine (Information). Refusals are worth noticing (Warning).
        var level = outcome.Status switch
        {
            ResultStatus.Done or ResultStatus.PendingConfirmation => LogLevel.Information,
            _ when outcome.Error?.Code == ErrorCodes.Internal => LogLevel.Error,
            _ => LogLevel.Warning,
        };

        log.Log(level,
            "{Tool} -> {Status} {ErrorCode} {PolicyRef} | session={SessionId} user={UserId} | {ElapsedMs} ms, audit={AuditId}",
            tool,
            outcome.Status.ToSnake(),
            outcome.Error?.Code ?? "-",
            outcome.PolicyRef ?? "-",
            ctx?.SessionId ?? "-",
            ctx?.UserId ?? "-",
            elapsedMs,
            auditId);
    }
}

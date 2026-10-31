using System.ComponentModel;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;
using SupportServer.Application;
using SupportServer.Application.Ports;

namespace SupportServer.Tools;

[McpServerToolType]
public sealed class SessionTools(SessionState session, IBillingProvider billing, ILogger<SessionTools> log)
{
    [McpServerTool(Name = "sys_set_context"),
     Description("СЛУЖБОВИЙ інструмент для системи, не для моделі. Задає користувача й номер репліки поточної сесії.")]
    public string SetContext(
        [Description("Ідентифікатор сесії чату")] string session_id,
        [Description("Ідентифікатор користувача, з яким іде розмова")] string user_id,
        [Description("Лічильник повідомлень користувача, починаючи з 1")] int user_turn)
    {
        ToolOutcome outcome;

        if (string.IsNullOrWhiteSpace(session_id) || string.IsNullOrWhiteSpace(user_id) || user_turn < 1)
        {
            outcome = ToolOutcome.Fail(ErrorCodes.InvalidArgument,
                "session_id і user_id обов'язкові, user_turn має бути >= 1.");
        }
        else if (billing.GetAccount(user_id) is null)
        {
            outcome = ToolOutcome.Fail(ErrorCodes.NotFound, $"Користувача {user_id} не знайдено.");
        }
        else
        {
            var change = session.Set(session_id, user_id, user_turn);
            if (change.Ok)
            {
                log.LogInformation("Session context set: session={SessionId} user={UserId} turn={UserTurn}",
                    session_id, user_id, user_turn);
                outcome = ToolOutcome.Done(new { session_id, user_id, user_turn });
            }
            else
            {
                // Someone tried to switch the user or session mid-run: refuse and make noise.
                log.LogWarning("Rejected session context change: session={SessionId} user={UserId} turn={UserTurn}: {Reason}",
                    session_id, user_id, user_turn, change.Error);
                outcome = ToolOutcome.Denied(ErrorCodes.PolicyDenied, change.Error!);
            }
        }

        // Internal calls are not written to audit_log (see contracts/03-mcp-tools.md).
        return Json.ToEnvelopeJson(outcome, null);
    }
}

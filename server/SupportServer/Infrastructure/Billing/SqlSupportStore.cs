using Dapper;
using SupportServer.Application.Ports;
using SupportServer.Domain;
using SupportServer.Infrastructure.Db;

namespace SupportServer.Infrastructure.Billing;

public sealed class SqlSupportStore(DbConnectionFactory db) : ISupportStore
{
    private SqlDialect D => db.Dialect;

    private string PendingColumns =>
        $"id, session_id, user_id, tool, args_json, summary, proposed_at_turn, status, {D.DateText("created_at")}, {D.DateText("resolved_at")}";

    public PendingAction? GetPendingAction(string id)
    {
        using var c = db.Open();
        return c.QuerySingleOrDefault<PendingAction>(
            $"SELECT {PendingColumns} FROM pending_actions WHERE id = @id", new { id });
    }

    public PendingAction? FindPendingAction(string sessionId, string tool, string argsJson)
    {
        using var c = db.Open();
        return c.QueryFirstOrDefault<PendingAction>(
            $"SELECT {PendingColumns} FROM pending_actions WHERE session_id = @sessionId AND tool = @tool " +
            "AND args_json = @argsJson AND status = 'pending' ORDER BY created_at DESC",
            new { sessionId, tool, argsJson });
    }

    public void CreatePendingAction(PendingAction action)
    {
        using var c = db.Open();
        c.Execute(
            $"""
            INSERT INTO pending_actions
              (id, session_id, user_id, tool, args_json, summary, proposed_at_turn, status, created_at)
            VALUES
              (@Id, @SessionId, @UserId, @Tool, @ArgsJson, @Summary, @ProposedAtTurn, @Status, {D.Ts("@CreatedAt")})
            """,
            action);
    }

    public bool ResolvePendingAction(string id, string newStatus, DateTimeOffset now)
    {
        using var c = db.Open();
        return c.Execute(
            $"UPDATE pending_actions SET status = @newStatus, resolved_at = {D.Ts("@at")} WHERE id = @id AND status = 'pending'",
            new { newStatus, at = Iso.Format(now), id }) == 1;
    }

    public void CreateTicket(Ticket ticket)
    {
        using var c = db.Open();
        c.Execute(
            $"""
            INSERT INTO tickets
              (id, user_id, session_id, priority, category, summary, suggested_action_json, status, created_at)
            VALUES
              (@Id, @UserId, @SessionId, @Priority, @Category, @Summary, @SuggestedActionJson, @Status, {D.Ts("@CreatedAt")})
            """,
            ticket);
    }
}

namespace SupportServer.Application;

/// <summary>Snapshot of the session context passed to every tool handler.</summary>
public sealed record ToolContext(string SessionId, string UserId, int UserTurn);

public sealed record ContextChangeResult(bool Ok, string? Error = null);

/// <summary>
/// Context of the current chat session. It is set only by system code (the internal sys_set_context tool,
/// called by the agent runtime), never by the model, so the model cannot act on behalf of another user.
/// One running server process serves one chat session.
/// Defense in depth: once set, the session and user cannot change (unless explicitly allowed for local
/// development) and the turn counter can only grow.
/// </summary>
public sealed class SessionState(bool allowSwitch)
{
    private readonly object _lock = new();
    private ToolContext? _current;

    public ToolContext? Current
    {
        get { lock (_lock) return _current; }
    }

    public ContextChangeResult Set(string sessionId, string userId, int userTurn)
    {
        lock (_lock)
        {
            if (_current is not null && !allowSwitch)
            {
                if (_current.SessionId != sessionId || _current.UserId != userId)
                    return new ContextChangeResult(false,
                        "Контекст сесії вже задано й не може бути змінений. Для нової розмови запустіть сервер заново.");

                if (userTurn < _current.UserTurn)
                    return new ContextChangeResult(false, "user_turn не може зменшуватись.");
            }

            _current = new ToolContext(sessionId, userId, userTurn);
            return new ContextChangeResult(true);
        }
    }
}

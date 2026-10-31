namespace SupportServer.Application;

/// <summary>Знімок контексту сесії, який отримує кожен обробник інструмента.</summary>
public sealed record ToolContext(string SessionId, string UserId, int UserTurn);

/// <summary>
/// Контекст поточної сесії. Задає лише B (службовий sys_set_context), а не модель.
/// Завдяки цьому агент технічно не може діяти від імені іншого користувача.
/// Один запущений сервер обслуговує одну сесію чату.
/// </summary>
public sealed class SessionState
{
    private readonly object _lock = new();
    private ToolContext? _current;

    public void Set(string sessionId, string userId, int userTurn)
    {
        lock (_lock) _current = new ToolContext(sessionId, userId, userTurn);
    }

    public ToolContext? Current
    {
        get { lock (_lock) return _current; }
    }
}

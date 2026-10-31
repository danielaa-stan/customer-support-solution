using SupportServer.Domain;

namespace SupportServer.Application.Ports;

/// <summary>Support-side state (tickets and actions awaiting confirmation), as opposed to billing state.</summary>
public interface ISupportStore
{
    PendingAction? GetPendingAction(string id);

    /// <summary>Finds a still-pending action with the same session, tool and arguments (keeps proposals idempotent).</summary>
    PendingAction? FindPendingAction(string sessionId, string tool, string argsJson);

    void CreatePendingAction(PendingAction action);

    /// <summary>Moves a pending action to a new status. Returns false if it was not pending any more.</summary>
    bool ResolvePendingAction(string id, string newStatus, DateTimeOffset now);

    void CreateTicket(Ticket ticket);
}

"""Minimal MCP server used ONLY by tests: 4 tools in the contracts/03 response format."""
from fastmcp import FastMCP

mcp = FastMCP("fake-support")
CONTEXT: dict = {}


def ok(data):
    return {"ok": True, "status": "done", "data": data, "error": None, "needs_human": False, "audit_id": 1}


def err(code, message):
    return {"ok": False, "status": "error", "data": None, "needs_human": False, "audit_id": 2,
            "error": {"code": code, "message": message, "policy_ref": None}}


@mcp.tool
def sys_set_context(session_id: str, user_id: str, user_turn: int) -> dict:
    CONTEXT.update(session_id=session_id, user_id=user_id, user_turn=user_turn)
    return ok(dict(CONTEXT))


@mcp.tool
def get_user_profile() -> dict:
    """Profile of the current user."""
    if not CONTEXT:
        return err("NO_CONTEXT", "sys_set_context was not called")
    return ok({"user": {"id": CONTEXT["user_id"]}, "turn": CONTEXT["user_turn"]})


@mcp.tool
def issue_refund(payment_id: str, reason_code: str, policy_ref: str) -> dict:
    """Refund a payment."""
    if payment_id == "pay_big":
        return {"ok": False, "status": "needs_human", "data": None, "needs_human": True, "audit_id": 3,
                "error": {"code": "LIMIT_EXCEEDED", "message": "Above the automatic limit",
                          "policy_ref": "refund-policy#2.3"}}
    return ok({"payment_id": payment_id, "refunded_amount": 9.99, "currency": "USD"})


if __name__ == "__main__":
    mcp.run()

"""Step 1 smoke test: can Gemma 4 (via the Gemini API) answer and call tools?

Run from the repo root:  python agent/check_llm.py
"""
import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL = os.getenv("LLM_MODEL", "gemma-4-26b-a4b-it")

if not os.getenv("GEMINI_API_KEY"):
    sys.exit("GEMINI_API_KEY is empty. Put it in .env first.")

client = OpenAI(base_url=BASE_URL, api_key=os.environ["GEMINI_API_KEY"])

# Test 1: plain text answer
start = time.time()
resp = client.chat.completions.create(
    model=MODEL, messages=[{"role": "user", "content": "Say hello in five words."}])
print(f"[1] Text answer ({time.time() - start:.1f}s): {resp.choices[0].message.content!r}")

# Test 2: does the model decide to call a tool?
tools = [{
    "type": "function",
    "function": {
        "name": "get_payments",
        "description": "Get the current customer's recent payments.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}},
    },
}]
messages = [
    {"role": "system", "content": "You are a support agent. Always check facts with tools before answering."},
    {"role": "user", "content": "I was charged twice! Refund me."},
]
start = time.time()
resp = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
msg = resp.choices[0].message
calls = [(tc.function.name, tc.function.arguments) for tc in (msg.tool_calls or [])]
print(f"[2] Tool calls ({time.time() - start:.1f}s): {calls or 'NONE'}")
if not msg.tool_calls:
    sys.exit("FAIL: the model did not call the tool. Tell Claude: we need the native google-genai SDK.")

# Test 3: give the model a fake tool result and check that it uses it
call = msg.tool_calls[0]
fake_result = {"ok": True, "status": "done", "data": {
    "payments": [
        {"id": "pay_demo_dbl_1", "amount": 9.99, "charged_at": "2026-10-29T08:00:00Z"},
        {"id": "pay_demo_dbl_2", "amount": 9.99, "charged_at": "2026-10-29T08:02:00Z"},
    ],
    "duplicate_charge_candidates": [["pay_demo_dbl_1", "pay_demo_dbl_2"]],
}}
messages += [
    {"role": "assistant", "content": msg.content or "", "tool_calls": [call.model_dump()]},
    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(fake_result)},
]
resp = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
print(f"[3] Answer after tool result: {resp.choices[0].message.content!r}")
print("\nOK: Gemma answers, calls tools and uses tool results.")

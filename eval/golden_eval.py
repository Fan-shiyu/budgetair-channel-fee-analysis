"""Layer 3 — golden-question eval driven by Google Gemini through the MCP server.

Gemini is given the server's tools (function calling) and asked each of the 12 golden
questions. The harness runs the tool-use loop, captures every tool output, then checks
the final answer for (a) the required facts and (b) FABRICATION — any dollar/percent
figure in the answer that is not traceable (within rounding tolerance) to that
conversation's tool outputs or the question itself.

Pass bar: 0 fabrications AND >= 10 / 12 correct.

Prereqs:
    pip install -r requirements.txt
    export GEMINI_API_KEY=...            # or put it in a local .env (gitignored)
    python -m mcp_server.server --transport http --port 8000   # in another terminal
    python eval/golden_eval.py [--url http://127.0.0.1:8000/mcp] [--model gemini-2.5-flash]

Re-run it against the deployed URL after deployment (pass --url).
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

from fastmcp import Client
from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_questions import QUESTIONS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SYSTEM = (
    "You answer questions about BudgetAir's 2022 Aeroprice channel-fee change for a "
    "non-technical manager. ALWAYS call a tool; only state numbers that appear in a tool "
    "result; never estimate, forecast, or invent example calculations (do not make up numbers "
    "like 'a $200 ticket would pay $8' — call fee_for_ticket for a real example). If the tools "
    "cannot answer, say so plainly. Fee terms are known only for Aeroprice. When a tool's "
    "headline mentions a contrast (e.g. an after-change figure), include it. Keep answers short."
)


# --------------------------------------------------------------------------- #
# .env loader (no python-dotenv dependency)
# --------------------------------------------------------------------------- #
def load_env():
    if os.environ.get("GEMINI_API_KEY"):
        return
    envf = ROOT / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# --------------------------------------------------------------------------- #
# MCP tool schema -> Gemini function declaration
# --------------------------------------------------------------------------- #
def _clean_schema(schema):
    """Reduce a JSON Schema to the OpenAPI subset Gemini accepts."""
    if not isinstance(schema, dict):
        return {"type": "string"}
    # flatten anyOf/[type,null] (Optional[...]) to the first concrete type, nullable
    if "anyOf" in schema:
        concrete = [s for s in schema["anyOf"] if s.get("type") != "null"]
        base = _clean_schema(concrete[0]) if concrete else {"type": "string"}
        base["nullable"] = True
        if "description" in schema:
            base["description"] = schema["description"]
        return base
    out = {"type": schema.get("type", "string")}
    for k in ("description", "enum"):
        if k in schema:
            out[k] = schema[k]
    if out["type"] == "object":
        out["properties"] = {p: _clean_schema(v) for p, v in schema.get("properties", {}).items()}
        if schema.get("required"):
            out["required"] = schema["required"]
    if out["type"] == "array" and "items" in schema:
        out["items"] = _clean_schema(schema["items"])
    return out


def build_declarations(tools):
    decls = []
    for t in tools:
        params = _clean_schema(t.inputSchema or {"type": "object", "properties": {}})
        if params.get("type") != "object":
            params = {"type": "object", "properties": {}}
        params.setdefault("properties", {})
        decls.append(types.FunctionDeclaration(
            name=t.name, description=(t.description or "")[:1000], parameters=params))
    return [types.Tool(function_declarations=decls)]


def _tool_text(result):
    blocks = getattr(result, "content", None) or []
    texts = [b.text for b in blocks if getattr(b, "type", None) == "text" or type(b).__name__ == "TextContent"]
    return "\n".join(texts)


# --------------------------------------------------------------------------- #
# Fabrication guard
# --------------------------------------------------------------------------- #
_MONEY = re.compile(r"\$\s?-?[\d,]+(?:\.\d+)?\s?[kKmM]?")
_PCT = re.compile(r"-?\d+(?:\.\d+)?\s?(?:%|pp)")


def _to_number(token):
    t = token.replace("$", "").replace(",", "").replace(" ", "").lower()
    mult = 1.0
    if t.endswith("k"):
        mult, t = 1_000.0, t[:-1]
    elif t.endswith("m"):
        mult, t = 1_000_000.0, t[:-1]
    t = t.replace("%", "").replace("pp", "")
    try:
        return abs(float(t)) * mult
    except ValueError:
        return None


def extract_numbers(text):
    nums = []
    for m in _MONEY.findall(text) + _PCT.findall(text):
        v = _to_number(m)
        if v is not None:
            nums.append((m.strip(), v))
    return nums


def find_fabrications(answer, grounding):
    """Any $/% figure in the answer not within tolerance of a grounding figure."""
    ground_vals = [v for _, v in extract_numbers(grounding)]
    fabricated = []
    for tok, val in extract_numbers(answer):
        ok = any(abs(val - g) <= max(0.5, 0.02 * max(val, g)) for g in ground_vals)
        if not ok:
            fabricated.append(tok)
    return fabricated


# --------------------------------------------------------------------------- #
# Run one question through Gemini + the MCP tools
# --------------------------------------------------------------------------- #
async def ask(mcp, client, model, tools, question, max_steps=6):
    chat = client.chats.create(
        model=model,
        config=types.GenerateContentConfig(tools=tools, system_instruction=SYSTEM, temperature=0),
    )
    tool_outputs = []
    r = await asyncio.to_thread(chat.send_message, question)
    for _ in range(max_steps):
        fcs = r.function_calls or []
        if not fcs:
            break
        parts = []
        for fc in fcs:
            try:
                res = await mcp.call_tool(fc.name, dict(fc.args or {}))
                out = _tool_text(res)
            except Exception as e:  # noqa: BLE001
                out = f"(tool error: {e})"
            tool_outputs.append(out)
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": out}))
        r = await asyncio.to_thread(chat.send_message, parts)
    return (r.text or ""), "\n".join(tool_outputs)


def grade(qdef, answer, tool_text):
    a = answer.lower()
    grounding = tool_text + "\n" + qdef["q"]
    fabrications = find_fabrications(answer, grounding)
    if qdef.get("trap"):
        declined = any(m.lower() in a for m in qdef["decline"])
        correct = declined
        reason = "declined" if declined else "did NOT decline"
    else:
        missing = [grp for grp in qdef["needs"] if not any(alt.lower() in a for alt in grp)]
        correct = not missing
        reason = "ok" if correct else f"missing {missing}"
    return correct, fabrications, reason


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp"))
    ap.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    ap.add_argument("--out", default=str(ROOT / "eval" / "scorecard.md"))
    args = ap.parse_args()

    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: set GEMINI_API_KEY (env or .env).")
        sys.exit(2)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    rows, n_correct, n_fab = [], 0, 0
    # generous per-call timeout: a cold deployed instance renders chart PNGs in ~10s
    async with Client(args.url, timeout=150) as mcp:
        tools = await mcp.list_tools()
        decls = build_declarations(tools)
        print(f"Connected to {args.url} — {len(tools)} tools; model {args.model}\n")
        for q in QUESTIONS:
            answer, tool_text = await ask(mcp, client, args.model, decls, q["q"])
            correct, fabs, reason = grade(q, answer, tool_text)
            n_correct += int(correct)
            n_fab += len(fabs)
            status = ("PASS" if correct else "FAIL") + (" +FABRICATION" if fabs else "")
            rows.append((q["id"], q["q"], correct, fabs, reason, answer))
            print(f"Q{q['id']:>2} [{status}] {reason}")
            if fabs:
                print("     fabricated:", fabs)

    passed = (n_fab == 0) and (n_correct >= 10)
    _write_scorecard(args.out, args.model, args.url, rows, n_correct, n_fab, passed)
    print(f"\n==== {n_correct}/12 correct, {n_fab} fabrications -> "
          f"{'PASS' if passed else 'FAIL'} ====")
    sys.exit(0 if passed else 1)


def _write_scorecard(path, model, url, rows, n_correct, n_fab, passed):
    lines = [
        "# Golden-eval scorecard (Gemini)",
        "",
        f"- Model: `{model}`",
        f"- Server: `{url}`",
        f"- Result: **{n_correct}/12 correct, {n_fab} fabrications — "
        f"{'PASS' if passed else 'FAIL'}** (bar: 0 fabrications AND ≥10/12)",
        "",
        "| # | Question | Correct | Fabrications | Note |",
        "|---|---|---|---|---|",
    ]
    for qid, q, correct, fabs, reason, _ in rows:
        lines.append(f"| {qid} | {q} | {'✅' if correct else '❌'} | "
                     f"{', '.join(fabs) if fabs else '—'} | {reason} |")
    lines += ["", "## Answers", ""]
    for qid, q, _, _, _, ans in rows:
        lines.append(f"**Q{qid}. {q}**\n\n> {ans.strip().replace(chr(10), ' ')}\n")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())

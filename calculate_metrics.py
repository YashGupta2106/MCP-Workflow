"""
calculate_metrics.py - Person 5: After-Metrics Calculator
==========================================================
Reads workflows.yaml and calculates the "After" token counts for the
24 MCP tool descriptions (21 workflows + 3 meta-tools).

Compares against Person 1's baseline (specs/baseline_metrics.json) to
prove >=80% tool reduction and quantify the token savings.

Outputs:
  - specs/after_metrics.json  -- full comparison metrics
  - Prints a summary table to stdout

Usage:
    python calculate_metrics.py
"""

import json
import yaml
from pathlib import Path
from collections import Counter


# ---------------------------------------------------------------------------
# Token counting (same approach as Person 1's parse_spec.py)
# ---------------------------------------------------------------------------
def count_tokens(text: str) -> int:
    """Count tokens using tiktoken (cl100k_base). Falls back to char/4 if
    tiktoken is unavailable or cannot download its encoding file (offline)."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback: ~4 chars per token (GPT-4 average)
        return len(text) // 4


# ---------------------------------------------------------------------------
# Build the text that the AI model would see for all 24 MCP tools
# ---------------------------------------------------------------------------
def build_mcp_tool_text(workflows: list) -> str:
    """
    Reconstruct the tool descriptions exactly as they appear to the LLM.
    This mirrors the docstrings in mcp_server.py so the token count is
    as realistic as possible.
    """
    lines = []

    # 21 workflow tools
    for wf in workflows:
        name = wf["name"]
        desc = wf.get("description", "")
        params = wf.get("parameters", [])

        param_lines = []
        for p in params:
            req = "required" if p.get("required") else "optional"
            default = f" [default: {p['default']}]" if p.get("default") else ""
            param_lines.append(
                f"  - {p['name']} ({req}): {p.get('description', '')}{default}"
            )
        param_doc = "\n".join(param_lines) if param_lines else "  (no parameters)"

        tool_text = (
            f"Tool: {name}\n"
            f"{desc}\n\n"
            f"Parameters:\n{param_doc}\n\n"
            f"Args:\n"
            f"    params_json: JSON string of key/value pairs.\n\n"
            f"Returns:\n"
            f"    JSON object with: workflow_name, success, steps_executed, "
            f"variables, output, next_workflows, error, started_at, finished_at\n"
            f"{'─' * 60}\n"
        )
        lines.append(tool_text)

    # 3 meta-tools
    meta_tools = [
        (
            "list_workflows_meta",
            "Returns a catalogue of all available high-level workflow tools.\n"
            "Call this first to understand what workflows exist before deciding\n"
            "which one to invoke. Each entry includes name, description, category,\n"
            "parameters, step_count, and raw_endpoint_count.\n\n"
            "Returns:\n    JSON array of workflow summary objects.",
        ),
        (
            "list_raw_endpoints",
            "HIERARCHICAL EXPOSURE - Tier Toggle.\n"
            "When a high-level workflow tool cannot complete a task, call this tool\n"
            "to reveal the individual Redfish API endpoints that the workflow uses.\n\n"
            "Args:\n    workflow_name: Name of the workflow whose raw endpoints you want.\n\n"
            "Returns:\n    JSON object with workflow name, list of raw endpoint strings, and usage note.",
        ),
        (
            "run_raw_endpoint",
            "HIERARCHICAL EXPOSURE - Raw Endpoint Executor.\n"
            "Sends a single HTTP request directly to the Redfish server.\n"
            "Use ONLY after calling list_raw_endpoints to discover valid paths.\n\n"
            "Args:\n"
            "    method: HTTP method - GET, POST, PATCH, DELETE, PUT\n"
            "    path: Redfish path with variables resolved.\n"
            "    body_json: Optional JSON body string for POST/PATCH/PUT requests.\n\n"
            "Returns:\n    JSON object with: success (bool), status_code (int), body (object)",
        ),
    ]

    for name, doc in meta_tools:
        lines.append(f"Tool: {name}\n{doc}\n{'─' * 60}\n")

    return "\n".join(lines)


def build_raw_endpoint_text(all_endpoints_path: Path) -> str:
    """
    Build a realistic text representation of 133 raw endpoints as they
    would appear to an LLM without our MCP wrapper.
    """
    if not all_endpoints_path.exists():
        return ""

    with open(all_endpoints_path, "r", encoding="utf-8") as f:
        endpoints = json.load(f)

    lines = []
    for ep in endpoints:
        method = ep.get("method", "GET")
        path = ep.get("path", "")
        summary = ep.get("summary", "")
        params = ep.get("parameters", [])

        param_doc = (
            "\n".join(f"  - {p} (path, required): string" for p in params)
            if params
            else "  (no path parameters)"
        )

        lines.append(
            f"Tool: {method}_{path.replace('/', '_').strip('_')}\n"
            f"{summary}\n\n"
            f"Parameters:\n{param_doc}\n\n"
            f"Args:\n    method: {method}\n    path: {path}\n"
            f"    body: Optional JSON request body\n\n"
            f"Returns:\n    HTTP response body as JSON\n"
            f"{'─' * 60}\n"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    repo_root = Path(__file__).parent
    workflows_path = repo_root / "workflows.yaml"
    baseline_path  = repo_root / "specs" / "baseline_metrics.json"
    endpoints_path = repo_root / "specs" / "cleaned" / "all_endpoints.json"
    output_path    = repo_root / "specs" / "after_metrics.json"

    print("=" * 65)
    print("  PERSON 5 -- AFTER-METRICS CALCULATOR")
    print("=" * 65)
    print()

    # Load workflows
    print("[1/4] Loading workflows.yaml ...")
    with open(workflows_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    workflows = data.get("workflows", [])
    total_workflows = len(workflows)
    total_raw_in_yaml = data.get("meta", {}).get("total_raw_endpoints", 133)
    print(f"  Loaded {total_workflows} workflows covering {total_raw_in_yaml} raw endpoints")

    # Load baseline
    print("\n[2/4] Loading baseline metrics from Person 1 ...")
    if baseline_path.exists():
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)
        print(f"  Raw endpoints (before):    {baseline['raw_endpoints']}")
        print(f"  Full spec tokens (before): {baseline['full_spec_tokens']:,}")
    else:
        print("  WARNING: baseline_metrics.json not found -- using hardcoded values")
        baseline = {"raw_endpoints": 133, "full_spec_tokens": 410562, "cleaned_summary_tokens": 38445}

    # Count MCP tool tokens (After)
    print("\n[3/4] Counting MCP tool tokens (After) ...")
    mcp_tool_text   = build_mcp_tool_text(workflows)
    after_tokens    = count_tokens(mcp_tool_text)
    raw_tool_text   = build_raw_endpoint_text(endpoints_path)
    raw_tool_tokens = count_tokens(raw_tool_text) if raw_tool_text else baseline["full_spec_tokens"]

    # Compute metrics
    before_tools       = baseline["raw_endpoints"]
    after_tools        = total_workflows + 3   # 21 + 3 meta = 24
    tool_reduction_pct = round(100 - (after_tools / before_tools * 100), 1)
    token_vs_raw_pct   = round(100 - (after_tokens / max(raw_tool_tokens, 1) * 100), 1)
    token_vs_full_pct  = round(100 - (after_tokens / max(baseline["full_spec_tokens"], 1) * 100), 1)

    after_metrics = {
        "person5_calculated": True,
        "tool_counts": {
            "before_tools": before_tools,
            "after_tools": after_tools,
            "workflow_tools": total_workflows,
            "meta_tools": 3,
            "tool_reduction_count": before_tools - after_tools,
            "tool_reduction_pct": tool_reduction_pct,
            "meets_80pct_threshold": tool_reduction_pct >= 80,
        },
        "token_counts": {
            "full_spec_before_tokens": baseline["full_spec_tokens"],
            "mcp_tool_descriptions_tokens": after_tokens,
            "raw_as_tools_tokens": raw_tool_tokens,
            "vs_raw_as_tools_reduction_pct": token_vs_raw_pct,
            "vs_full_spec_reduction_pct": token_vs_full_pct,
        },
        "workflow_breakdown": [
            {
                "name": wf["name"],
                "category": wf.get("category", ""),
                "step_count": len(wf.get("steps", [])),
                "raw_endpoints_covered": len(wf.get("raw_endpoints", [])),
                "parameters": len(wf.get("parameters", [])),
            }
            for wf in workflows
        ],
        "categories": dict(Counter(wf.get("category", "unknown") for wf in workflows)),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(after_metrics, f, indent=2)

    print()
    print("=" * 65)
    print("  HACKATHON METRICS -- BEFORE vs AFTER")
    print("=" * 65)
    print(f"\n  TOOL COUNT REDUCTION")
    print(f"  {'Before (133 raw endpoints as tools):':<42} {before_tools}")
    print(f"  {'After  (24 MCP workflow tools):':<42} {after_tools}")
    print(f"  {'Reduction:':<42} {before_tools - after_tools} tools")
    print(f"  {'Reduction %:':<42} {tool_reduction_pct}%")
    print(f"  {'>=80% threshold:':<42} {'PASSES' if tool_reduction_pct >= 80 else 'FAILS'}")
    print(f"\n  TOKEN REDUCTION")
    print(f"  {'Full spec tokens (baseline):':<42} {baseline['full_spec_tokens']:,}")
    print(f"  {'MCP tool descriptions tokens:':<42} {after_tokens:,}")
    print(f"  {'Reduction vs full spec:':<42} {token_vs_full_pct}%")
    print(f"  {'Reduction vs raw-as-tools:':<42} {token_vs_raw_pct}%")
    print(f"\n  Output saved: {output_path}")
    print("=" * 65)

    return after_metrics


if __name__ == "__main__":
    main()

# 👤 Person 4 — The Connector: MCP Server Interface & Tiering Developer

> **Your job in one sentence:** Take the already-built workflow engine (`workflow_engine.py`) from Person 3 and wrap it inside a formal **Model Context Protocol (MCP) server** so that any AI assistant (Claude, Cursor, etc.) can discover and call the 19 workflows as first-class tools — and fall back to raw Redfish endpoints when needed.

---

## 📋 Table of Contents

1. [What You Own](#what-you-own)
2. [Prerequisites & Dependencies](#prerequisites--dependencies)
3. [Step 1 — Understand the Engine You Are Wrapping](#step-1--understand-the-engine-you-are-wrapping)
4. [Step 2 — Install the MCP Python SDK](#step-2--install-the-mcp-python-sdk)
5. [Step 3 — Create the MCP Server File](#step-3--create-the-mcp-server-file)
6. [Step 4 — Register the 19 Workflow Tools](#step-4--register-the-19-workflow-tools)
7. [Step 5 — Implement Hierarchical Exposure (the Tier Toggle)](#step-5--implement-hierarchical-exposure-the-tier-toggle)
8. [Step 6 — Wire Up the Server Entry-Point](#step-6--wire-up-the-server-entry-point)
9. [Step 7 — Test Locally](#step-7--test-locally)
10. [Step 8 — Hand Off to Person 5](#step-8--hand-off-to-person-5)
11. [File Checklist](#file-checklist)
12. [Quick Reference — Engine Public API](#quick-reference--engine-public-api)

---

## What You Own

| File | Status | Your responsibility |
|---|---|---|
| `workflow_engine.py` | ✅ Built by Person 3 | **Read-only** — do NOT modify |
| `workflows.yaml` | ✅ Built by Person 2 | **Read-only** — do NOT modify |
| `mcp_server.py` | 🆕 You create this | The entire MCP wrapper |
| `requirements.txt` | ✅ Exists | Add the MCP SDK line |

---

## Prerequisites & Dependencies

### What you need installed

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Runtime |
| pip | latest | Package manager |
| Node.js / npm | 18+ | Only if using the JS MCP SDK (optional) |

### Python packages to add

The existing `requirements.txt` already has:
```
pyyaml>=6.0
requests>=2.31.0
tiktoken>=0.5.0
```

**Add the MCP SDK:**
```
mcp>=1.0.0
```

Install everything:
```bash
pip install -r requirements.txt
pip install "mcp[cli]"
```

> **Why `mcp[cli]`?** The `[cli]` extra gives you the `mcp dev` inspector tool, which lets you test the server interactively without wiring it into Claude Desktop first.

---

## Step 1 — Understand the Engine You Are Wrapping

Open `workflow_engine.py` and read the **Public API for Person 4** block at the top (lines 22–27). You will call exactly three methods:

```python
from workflow_engine import WorkflowEngine

# 1. Create the engine (points at Person 2's YAML + Person 1's Prism server)
engine = WorkflowEngine(
    workflows_file="workflows.yaml",   # Person 2's output
    base_url="http://localhost:4000",  # Person 1's Prism mock server URL
)

# 2. List all available workflows (returns list of dicts)
workflows = engine.list_workflows()
# Each dict has: name, description, category, parameters, step_count, raw_endpoint_count

# 3. Get full detail on a single workflow
detail = engine.get_workflow_detail("server_health_check")
# Returns: name, description, category, parameters, steps, raw_endpoints, output_template, next_workflows

# 4. Execute a workflow with parameters
result = engine.run_workflow("server_health_check", {"SystemId": "Server1"})
# Returns: workflow_name, success, steps_executed, variables, output, next_workflows, error, started_at, finished_at
```

**You never touch HTTP calls or YAML parsing** — that is all handled inside `WorkflowEngine`. You are purely building the MCP door that lets an AI step into the engine.

---

## Step 2 — Install the MCP Python SDK

```bash
pip install "mcp[cli]"
```

Verify it works:
```bash
python -c "import mcp; print(mcp.__version__)"
```

You should see a version number (e.g., `1.9.2`). If you get an import error, try:
```bash
pip install --upgrade mcp
```

---

## Step 3 — Create the MCP Server File

Create a new file called **`mcp_server.py`** in the repo root (same folder as `workflow_engine.py`).

Start with this skeleton:

```python
"""
mcp_server.py — Person 4: The MCP Server Wrapper
=================================================
Wraps Person 3's WorkflowEngine as a formal MCP server.

Exposes:
  • 19 workflow tools  (one per workflow in workflows.yaml)
  • 1 meta-tool: list_raw_endpoints — the Tier Toggle for Hierarchical Exposure
  • 1 meta-tool: run_raw_endpoint   — escape hatch to call individual Redfish endpoints

Usage:
    python mcp_server.py                  # stdio transport (for Claude Desktop / Cursor)
    mcp dev mcp_server.py                 # interactive inspector (browser UI)
"""

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from workflow_engine import WorkflowEngine

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mcp_server")

# Create the MCP application
mcp = FastMCP("Redfish Workflow Proxy")

# Create the engine — adjust base_url if Person 1's Prism runs on a different port
engine = WorkflowEngine(
    workflows_file="workflows.yaml",
    base_url="http://localhost:4000",
)

logger.info("WorkflowEngine loaded — %d workflows available", len(engine.list_workflows()))
```

---

## Step 4 — Register the 19 Workflow Tools

Each workflow from `workflows.yaml` must become its own MCP tool. Use a **loop** to register them dynamically at startup — do NOT hardcode one function per workflow.

Add this block to `mcp_server.py` right after the engine creation:

```python
# ---------------------------------------------------------------------------
# Dynamically register one MCP tool per workflow
# ---------------------------------------------------------------------------

def _make_workflow_tool(workflow_name: str, description: str, parameters: list):
    """
    Factory that creates a closure for a specific workflow.
    This avoids the classic Python loop-closure bug (all lambdas capturing the
    same loop variable).
    """
    # Build a human-readable parameter hint for the docstring
    param_lines = []
    for p in parameters:
        req = "required" if p.get("required") else "optional"
        default = f" [default: {p['default']}]" if p.get("default") else ""
        param_lines.append(f"  - {p['name']} ({req}): {p.get('description', '')}{default}")
    param_doc = "\n".join(param_lines) if param_lines else "  (no parameters)"

    full_doc = f"{description}\n\nParameters:\n{param_doc}"

    # The actual tool function
    def tool_fn(params_json: str = "{}") -> str:
        """
        params_json: JSON string of key/value pairs for the workflow parameters.
        Example: '{"SystemId": "Server1", "ResetType": "GracefulRestart"}'
        """
        try:
            params = json.loads(params_json) if params_json.strip() else {}
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON params: {e}"})

        result = engine.run_workflow(workflow_name, params)
        return json.dumps(result, indent=2, default=str)

    # Rename the function so MCP sees the workflow name as the tool name
    tool_fn.__name__ = workflow_name
    tool_fn.__doc__ = full_doc
    return tool_fn


# Register each workflow as an MCP tool
for wf in engine.list_workflows():
    fn = _make_workflow_tool(wf["name"], wf["description"], wf["parameters"])
    mcp.tool()(fn)
    logger.info("Registered tool: %s", wf["name"])
```

> **What this achieves:** The AI sees exactly 19 tools — one per workflow. Instead of 133 raw Redfish API calls, it sees `server_health_check`, `firmware_update`, `storage_management`, etc.

---

## Step 5 — Implement Hierarchical Exposure (the Tier Toggle)

This is the **key innovation of Person 4's work**. When the AI hits a wall with the high-level workflow (e.g., a workflow step fails or the AI needs surgical control), it can call a toggle tool to get the raw sub-buttons for that specific workflow.

Add these two meta-tools to `mcp_server.py`:

```python
# ---------------------------------------------------------------------------
# Meta-Tool 1: list_raw_endpoints  — the Tier Toggle
# ---------------------------------------------------------------------------
@mcp.tool()
def list_raw_endpoints(workflow_name: str) -> str:
    """
    HIERARCHICAL EXPOSURE — Tier Toggle.

    When a high-level workflow tool cannot complete a task, call this tool
    to get the individual Redfish API endpoints that the workflow uses
    internally. This gives the AI fine-grained control to issue targeted
    sub-calls via run_raw_endpoint.

    Args:
        workflow_name: Name of the workflow whose raw endpoints you want.
                       Use list_workflows_meta to get valid names.

    Returns:
        JSON list of raw endpoint strings, e.g.:
        ["GET /redfish/v1/Systems/{SystemId}", "PATCH /redfish/v1/Systems/{SystemId}", ...]
    """
    detail = engine.get_workflow_detail(workflow_name)
    if detail is None:
        return json.dumps({
            "error": f"Workflow '{workflow_name}' not found.",
            "available": [wf["name"] for wf in engine.list_workflows()]
        })
    return json.dumps({
        "workflow": workflow_name,
        "raw_endpoints": detail["raw_endpoints"],
        "note": (
            "You can call any of these individually using the run_raw_endpoint tool. "
            "Supply the method, path, and optional JSON body."
        )
    }, indent=2)


# ---------------------------------------------------------------------------
# Meta-Tool 2: run_raw_endpoint  — the escape hatch
# ---------------------------------------------------------------------------
@mcp.tool()
def run_raw_endpoint(method: str, path: str, body_json: str = "{}") -> str:
    """
    HIERARCHICAL EXPOSURE — Raw Endpoint Executor.

    Sends a single HTTP request directly to the Redfish server (Person 1's
    Prism mock). Use this only AFTER calling list_raw_endpoints to discover
    valid paths. This is the escape hatch for surgical fixes when a
    high-level workflow cannot handle an edge case.

    Args:
        method:    HTTP method — GET, POST, PATCH, DELETE, PUT
        path:      Redfish path with variables resolved, e.g. /redfish/v1/Systems/Server1
        body_json: Optional JSON body string for POST/PATCH/PUT requests.

    Returns:
        JSON object with: status_code, body, success
    """
    try:
        body = json.loads(body_json) if body_json.strip() not in ("{}", "", "null") else None
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON body: {e}"})

    url = f"{engine.base_url}{path}"
    resp_data, status, headers = engine._http_request(method.upper(), url, body)

    return json.dumps({
        "success": 200 <= status < 400,
        "status_code": status,
        "body": resp_data,
    }, indent=2, default=str)


# ---------------------------------------------------------------------------
# Meta-Tool 3: list_workflows_meta  — discovery helper
# ---------------------------------------------------------------------------
@mcp.tool()
def list_workflows_meta() -> str:
    """
    Returns a catalogue of all available high-level workflow tools.
    Call this first to understand what workflows exist before deciding
    which one to invoke.

    Returns:
        JSON array of workflow summaries with name, description, category,
        parameter names, step count, and raw endpoint count.
    """
    return json.dumps(engine.list_workflows(), indent=2)
```

---

## Step 6 — Wire Up the Server Entry-Point

At the very bottom of `mcp_server.py`, add the entry point:

```python
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # stdio transport = how Claude Desktop and Cursor connect
    mcp.run(transport="stdio")
```

Your complete `mcp_server.py` should now contain, in order:
1. Imports & setup
2. `FastMCP` + `WorkflowEngine` instantiation
3. `_make_workflow_tool` factory function
4. The registration loop (19 tools)
5. `list_raw_endpoints` meta-tool
6. `run_raw_endpoint` meta-tool
7. `list_workflows_meta` meta-tool
8. `if __name__ == "__main__": mcp.run(transport="stdio")`

---

## Step 7 — Test Locally

### 7a. Quick smoke test (no Claude needed)

```bash
# Make sure Person 1's Prism mock is running at localhost:4000 first
# Then test the engine directly:
python workflow_engine.py list

# Should print all 19 workflows grouped by category
```

```bash
# Test a single workflow via CLI (engine only, no MCP layer yet)
python workflow_engine.py run discover_service_root
```

### 7b. Test the MCP server with the inspector

```bash
mcp dev mcp_server.py
```

This opens a browser-based inspector UI. You will see all your tools listed. Click any tool, fill in the parameters, and hit **Run** to execute it. Verify you see:
- ✅ All 19 workflow tools listed
- ✅ `list_raw_endpoints`, `run_raw_endpoint`, `list_workflows_meta` listed
- ✅ A workflow returns a JSON result with `success: true`
- ✅ `list_raw_endpoints("server_health_check")` returns the 7 raw Redfish endpoints for that workflow

### 7c. Test the Tier Toggle flow

In the MCP inspector:
1. Call `list_workflows_meta` → verify 19 entries appear
2. Call `server_health_check` with `params_json='{"SystemId":"Server1"}'`
3. Call `list_raw_endpoints` with `workflow_name="server_health_check"` → see 7 raw endpoints
4. Call `run_raw_endpoint` with `method="GET"`, `path="/redfish/v1/Systems/Server1"` → see raw JSON response

### 7d. Test via stdio (simulates Claude Desktop)

```bash
python mcp_server.py
```

The server will start and wait on stdin. You can type a JSON-RPC message to confirm it responds:
```json
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```
Press Enter. You should see a JSON response listing all 22 tools (19 workflows + 3 meta-tools).  
Press `Ctrl+C` to stop.

---

## Step 8 — Hand Off to Person 5

Once your server is working, give Person 5:

### ✅ The running server command
```bash
python mcp_server.py
```

### ✅ The Claude Desktop config snippet

Tell Person 5 to add this to their `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "redfish-workflow-proxy": {
      "command": "python",
      "args": ["C:\\path\\to\\MCP-Workflow\\mcp_server.py"],
      "env": {}
    }
  }
}
```

> Replace `C:\\path\\to\\MCP-Workflow` with the actual absolute path on Person 5's machine.

### ✅ The Cursor config snippet

In Cursor settings → MCP, add:
```json
{
  "name": "redfish-workflow-proxy",
  "command": "python mcp_server.py",
  "cwd": "C:\\path\\to\\MCP-Workflow"
}
```

### ✅ What Person 5 should test

Give them these example natural language prompts to verify everything works:
- *"Check the health of server Server1"* → should invoke `server_health_check`
- *"Show me a firmware inventory"* → should invoke `firmware_update`
- *"List all available workflows"* → should invoke `list_workflows_meta`
- *"The workflow failed — show me the raw endpoints for firmware_update"* → should invoke `list_raw_endpoints`

---

## File Checklist

By the time you are done, confirm the following:

```
MCP-Workflow/
├── workflow_engine.py      ✅ Untouched (Person 3's engine)
├── workflows.yaml          ✅ Untouched (Person 2's blueprint)
├── mcp_server.py           🆕 YOU CREATED THIS
│     ├── FastMCP app
│     ├── 19 dynamic workflow tools
│     ├── list_raw_endpoints tool (Tier Toggle)
│     ├── run_raw_endpoint tool  (escape hatch)
│     └── list_workflows_meta tool (discovery)
├── requirements.txt        ✅ You added: mcp>=1.0.0
└── README.md / PERSON4_README.md
```

---

## Quick Reference — Engine Public API

These are the **only three methods** you need from `workflow_engine.py`:

| Method | Returns | When to use |
|---|---|---|
| `engine.list_workflows()` | `List[Dict]` | Registering tools at startup; populating `list_workflows_meta` |
| `engine.get_workflow_detail(name)` | `Dict` or `None` | Populating `list_raw_endpoints` |
| `engine.run_workflow(name, params)` | `Dict` | Inside every workflow tool function |

Each `run_workflow` result dict has these keys:

```
workflow_name   str   — name of the workflow that ran
success         bool  — True if all critical steps passed
steps_executed  list  — per-step status, HTTP codes, extracted variables
variables       dict  — all variables extracted during execution
output          str   — filled-in output_template (markdown table)
next_workflows  list  — suggested follow-on workflows with reasons
error           str?  — error message if success=False, else None
started_at      str   — ISO-8601 timestamp
finished_at     str   — ISO-8601 timestamp
```

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: mcp` | MCP SDK not installed | `pip install "mcp[cli]"` |
| `FileNotFoundError: workflows.yaml` | Wrong working directory | Run `python mcp_server.py` from the repo root |
| `Connection refused: http://localhost:4000` | Person 1's Prism not running | Ask Person 1 to start Prism first |
| Tool names not showing in Claude | Server not saved to config | Double-check `claude_desktop_config.json` path and restart Claude |
| `KeyError: 'name'` on tool loop | `workflow_engine.py` version mismatch | Pull latest `workflow_engine.py` from Person 3 |

---

*This README covers Person 4's complete scope. Do not modify `workflow_engine.py` or `workflows.yaml` — those belong to Person 3 and Person 2 respectively.*

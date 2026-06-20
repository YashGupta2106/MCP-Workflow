"""
mcp_server.py — Person 4: The MCP Server Wrapper
=================================================
Wraps Person 3's WorkflowEngine as a formal MCP server.

Exposes:
  • 19 workflow tools  (one per workflow in workflows.yaml)
  • 1 meta-tool: list_raw_endpoints — the Tier Toggle for Hierarchical Exposure
  • 1 meta-tool: run_raw_endpoint   — escape hatch to call individual Redfish endpoints
  • 1 meta-tool: list_workflows_meta — discovery catalogue

Usage:
    python mcp_server.py                  # stdio transport (for Claude Desktop / Cursor)
    mcp dev mcp_server.py                 # interactive inspector (browser UI)
"""

import json
import logging

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
    base_url="http://localhost:4010",   # Prism default port is 4010
)

logger.info("WorkflowEngine loaded — %d workflows available", len(engine.list_workflows()))


# ---------------------------------------------------------------------------
# Dynamically register one MCP tool per workflow (Step 4)
# ---------------------------------------------------------------------------

def _make_workflow_tool(workflow_name: str, description: str, parameters: list):
    """
    Factory that creates a closure for a specific workflow.
    Using a factory avoids the classic Python loop-closure bug where all
    lambdas capture the same loop variable reference.
    """
    # Build a human-readable parameter hint for the docstring
    param_lines = []
    for p in parameters:
        req = "required" if p.get("required") else "optional"
        default = f" [default: {p['default']}]" if p.get("default") else ""
        param_lines.append(f"  - {p['name']} ({req}): {p.get('description', '')}{default}")
    param_doc = "\n".join(param_lines) if param_lines else "  (no parameters)"

    full_doc = (
        f"{description}\n\n"
        f"Parameters:\n{param_doc}\n\n"
        f"Args:\n"
        f"    params_json: JSON string of key/value pairs, e.g. "
        f'\'{{\"SystemId\": \"Server1\"}}\'. '
        f"Pass '{{}}' if the workflow has no required parameters.\n\n"
        f"Returns:\n"
        f"    JSON object with: workflow_name, success, steps_executed, "
        f"variables, output, next_workflows, error, started_at, finished_at"
    )

    def tool_fn(params_json: str = "{}") -> str:
        try:
            params = json.loads(params_json) if params_json.strip() else {}
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON params: {e}"})

        result = engine.run_workflow(workflow_name, params)
        return json.dumps(result, indent=2, default=str)

    # Rename so MCP registers the tool under the workflow name
    tool_fn.__name__ = workflow_name
    tool_fn.__doc__ = full_doc
    return tool_fn


# Register each workflow as an MCP tool
for _wf in engine.list_workflows():
    _fn = _make_workflow_tool(_wf["name"], _wf["description"], _wf["parameters"])
    mcp.tool()(_fn)
    logger.info("Registered tool: %s", _wf["name"])


# ---------------------------------------------------------------------------
# Meta-Tool 1: list_workflows_meta — discovery catalogue (Step 5)
# ---------------------------------------------------------------------------
@mcp.tool()
def list_workflows_meta() -> str:
    """
    Returns a catalogue of all available high-level workflow tools.

    Call this first to understand what workflows exist before deciding
    which one to invoke. Each entry includes name, description, category,
    parameters, step_count, and raw_endpoint_count.

    Returns:
        JSON array of workflow summary objects.
    """
    return json.dumps(engine.list_workflows(), indent=2)


# ---------------------------------------------------------------------------
# Meta-Tool 2: list_raw_endpoints — the Tier Toggle (Step 5)
# ---------------------------------------------------------------------------
@mcp.tool()
def list_raw_endpoints(workflow_name: str) -> str:
    """
    HIERARCHICAL EXPOSURE — Tier Toggle.

    When a high-level workflow tool cannot complete a task (e.g., a step
    fails, or the AI needs surgical control), call this tool to reveal the
    individual Redfish API endpoints that the workflow uses internally.
    The AI can then issue targeted calls via run_raw_endpoint.

    Args:
        workflow_name: Name of the workflow whose raw endpoints you want.
                       Call list_workflows_meta first to get valid names.

    Returns:
        JSON object with the workflow name, list of raw endpoint strings
        (e.g. "GET /redfish/v1/Systems/{SystemId}"), and a usage note.
    """
    detail = engine.get_workflow_detail(workflow_name)
    if detail is None:
        return json.dumps({
            "error": f"Workflow '{workflow_name}' not found.",
            "available": [wf["name"] for wf in engine.list_workflows()],
        })
    return json.dumps({
        "workflow": workflow_name,
        "raw_endpoints": detail["raw_endpoints"],
        "note": (
            "Call any of these individually using the run_raw_endpoint tool. "
            "Resolve path variables like {SystemId} before calling."
        ),
    }, indent=2)


# ---------------------------------------------------------------------------
# Meta-Tool 3: run_raw_endpoint — the escape hatch (Step 5)
# ---------------------------------------------------------------------------
@mcp.tool()
def run_raw_endpoint(method: str, path: str, body_json: str = "{}") -> str:
    """
    HIERARCHICAL EXPOSURE — Raw Endpoint Executor.

    Sends a single HTTP request directly to the Redfish server (Person 1's
    Prism mock). Use this ONLY after calling list_raw_endpoints to discover
    valid paths. This is the escape hatch for surgical fixes when a
    high-level workflow cannot handle an edge case.

    Args:
        method:    HTTP method — GET, POST, PATCH, DELETE, PUT
        path:      Redfish path with variables already resolved,
                   e.g. /redfish/v1/Systems/Server1
        body_json: Optional JSON body string for POST/PATCH/PUT requests.
                   Pass '{}' or omit for GET/DELETE.

    Returns:
        JSON object with: success (bool), status_code (int), body (object)
    """
    try:
        body = (
            json.loads(body_json)
            if body_json.strip() not in ("{}", "", "null")
            else None
        )
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON body: {e}"})

    url = f"{engine.base_url}{path}"
    resp_data, status, _headers = engine._http_request(method.upper(), url, body)

    return json.dumps({
        "success": 200 <= status < 400,
        "status_code": status,
        "body": resp_data,
    }, indent=2, default=str)


# ---------------------------------------------------------------------------
# Entry point (Step 6)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # stdio transport = how Claude Desktop and Cursor connect
    mcp.run(transport="stdio")

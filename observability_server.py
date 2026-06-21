"""
observability_server.py — Observability Dashboard Backend
==========================================================
FastAPI server that powers the Observability Dashboard for the
MCP Workflow Proxy hackathon project.

Provides REST API endpoints for:
- Workflow catalog and mapping visualization
- Workflow execution with detailed tracing
- Trace history and detail retrieval
- System metrics (tool count, token savings)
- Server-Sent Events for live execution streaming

Usage:
    python observability_server.py
    # Dashboard opens at http://localhost:8080
"""

import os
import sys
import json
import asyncio
import logging
import webbrowser
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

import uvicorn

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from observability_engine import ObservabilityEngine
import nl_workflow_generator
# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("observability_server")

REPO_ROOT = Path(__file__).parent

app = FastAPI(
    title="MCP Workflow Proxy — Observability Dashboard",
    description="Visualize workflow-to-API mappings and execution traces",
    version="1.0.0",
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the instrumented engine
engine = ObservabilityEngine(
    workflows_file=str(REPO_ROOT / "workflows.yaml"),
    base_url="http://localhost:4010",
)

logger.info("ObservabilityEngine loaded — %d workflows available", len(engine.list_workflows()))

# SSE event queues for live streaming
sse_queues: list = []


def broadcast_sse(event: str, data: dict):
    """Broadcast an SSE event to all connected clients."""
    for q in sse_queues:
        try:
            q.put_nowait({"event": event, "data": json.dumps(data, default=str)})
        except Exception:
            pass


engine.register_sse_callback(broadcast_sse)


# ===========================================================================
#  API Endpoints
# ===========================================================================


# ---------------------------------------------------------------------------
#  Workflows Catalog
# ---------------------------------------------------------------------------

@app.get("/api/workflows")
async def list_workflows():
    """List all workflows with their step counts, endpoint mappings, and categories."""
    workflows = engine.list_workflows()

    # Enrich with raw endpoint data from workflow details
    enriched = []
    for wf in workflows:
        detail = engine.get_workflow_detail(wf["name"])
        enriched.append({
            **wf,
            "raw_endpoints": detail.get("raw_endpoints", []) if detail else [],
            "steps": detail.get("steps", []) if detail else [],
            "output_template": detail.get("output_template", "") if detail else "",
            "next_workflows": detail.get("next_workflows", []) if detail else [],
        })

    return JSONResponse(content=enriched)


@app.get("/api/workflows/{name}")
async def get_workflow(name: str):
    """Get full detail for a single workflow."""
    detail = engine.get_workflow_detail(name)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    return JSONResponse(content=detail)


# ---------------------------------------------------------------------------
#  Natural Language Workflow Generator
# ---------------------------------------------------------------------------

@app.post("/api/generate_workflow")
async def generate_workflow_api(request: Request):
    """Generate a workflow from natural language and hot-reload."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    prompt = body.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
        
    logger.info("Generating workflow for prompt: %s", prompt)
    
    # Call the generator
    yaml_content = nl_workflow_generator.generate_workflow_yaml(prompt)
    if not yaml_content:
        raise HTTPException(status_code=500, detail="Failed to generate workflow YAML")
        
    # Append to workflows.yaml
    success = nl_workflow_generator.append_workflow(yaml_content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to append workflow to YAML file")
        
    # Hot-reload the engine
    engine._raw = engine._load_workflows(engine.workflows_file)
    engine._workflow_map = {
        wf["name"]: wf for wf in engine._raw.get("workflows", [])
    }
    logger.info("WorkflowEngine hot-reloaded successfully. Now has %d workflows.", len(engine._workflow_map))
    
    return JSONResponse(content={
        "success": True,
        "yaml": yaml_content,
        "message": "Workflow generated and loaded successfully"
    })


# ---------------------------------------------------------------------------
#  Metrics
# ---------------------------------------------------------------------------

@app.get("/api/metrics")
async def get_metrics():
    """Return system metrics including tool/token reduction stats."""
    metrics_path = REPO_ROOT / "specs" / "after_metrics.json"

    metrics = {}
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

    # Add live stats
    traces = engine.get_traces()
    total_executions = len(traces)
    successful = sum(1 for t in traces if t.get("success"))
    failed = total_executions - successful
    total_http = sum(t.get("total_http_calls", 0) for t in traces)
    avg_duration = (
        sum(t.get("duration_ms", 0) for t in traces) / total_executions
        if total_executions > 0
        else 0
    )

    metrics["live_stats"] = {
        "total_executions": total_executions,
        "successful_executions": successful,
        "failed_executions": failed,
        "total_http_calls": total_http,
        "avg_duration_ms": round(avg_duration, 2),
    }

    return JSONResponse(content=metrics)


# ---------------------------------------------------------------------------
#  Execution
# ---------------------------------------------------------------------------

@app.post("/api/execute/{name}")
async def execute_workflow(name: str, request: Request):
    """Execute a workflow and return the full trace."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    params = body.get("params", body) if body else {}

    logger.info("Executing workflow: %s with params: %s", name, params)

    try:
        result, trace = engine.run_workflow_traced(name, params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse(content={
        "result": result,
        "trace": trace,
    })


# ---------------------------------------------------------------------------
#  Traces
# ---------------------------------------------------------------------------

@app.get("/api/traces")
async def list_traces():
    """List all stored execution traces (summary view)."""
    return JSONResponse(content=engine.get_traces())


@app.get("/api/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get full detail for a single trace."""
    trace = engine.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return JSONResponse(content=trace)


# ---------------------------------------------------------------------------
#  Server-Sent Events
# ---------------------------------------------------------------------------

@app.get("/events")
async def sse_endpoint(request: Request):
    """SSE stream for live execution updates."""
    queue = asyncio.Queue()
    sse_queues.append(queue)

    async def event_generator():
        try:
            # Send initial heartbeat
            yield {"event": "connected", "data": json.dumps({"status": "connected"})}

            while True:
                if await request.is_disconnected():
                    break

                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield msg
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield {"event": "heartbeat", "data": json.dumps({"ts": datetime.now(timezone.utc).isoformat()})}
        finally:
            if queue in sse_queues:
                sse_queues.remove(queue)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
#  Workflow-to-API Mapping Data (for DAG visualization)
# ---------------------------------------------------------------------------

@app.get("/api/mapping")
async def get_workflow_mapping():
    """
    Return structured data for the workflow-to-API mapping visualization.
    Returns workflows as nodes and their raw_endpoints as connected nodes.
    """
    workflows = engine.list_workflows()
    nodes = []
    edges = []
    endpoint_set = set()

    for wf in workflows:
        detail = engine.get_workflow_detail(wf["name"])
        if not detail:
            continue

        # Workflow node
        nodes.append({
            "id": wf["name"],
            "type": "workflow",
            "label": wf["name"].replace("_", " ").title(),
            "category": wf["category"],
            "step_count": wf["step_count"],
            "endpoint_count": wf["raw_endpoint_count"],
        })

        # Endpoint nodes and edges
        for ep in detail.get("raw_endpoints", []):
            ep_id = ep.replace(" ", "_").replace("/", "_")
            if ep_id not in endpoint_set:
                parts = ep.split(" ", 1)
                method = parts[0] if len(parts) > 1 else "GET"
                path = parts[1] if len(parts) > 1 else ep
                nodes.append({
                    "id": ep_id,
                    "type": "endpoint",
                    "label": ep,
                    "method": method,
                    "path": path,
                })
                endpoint_set.add(ep_id)

            edges.append({
                "source": wf["name"],
                "target": ep_id,
            })

    return JSONResponse(content={
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_workflows": len(workflows),
            "total_unique_endpoints": len(endpoint_set),
            "total_edges": len(edges),
        },
    })


# ---------------------------------------------------------------------------
#  Static files + Dashboard
# ---------------------------------------------------------------------------

dashboard_dir = REPO_ROOT / "dashboard"
if dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard HTML."""
    index_path = dashboard_dir / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Dashboard not found. Please build the dashboard first.</h1>")
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
#  Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    PORT = 8765

    print()
    print("=" * 65)
    print("  MCP Workflow Proxy — Observability Dashboard")
    print("=" * 65)
    print()
    print(f"  Dashboard:  http://localhost:{PORT}")
    print(f"  API docs:   http://localhost:{PORT}/docs")
    print(f"  SSE stream: http://localhost:{PORT}/events")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 65)
    print()

    # Auto-open browser
    webbrowser.open(f"http://localhost:{PORT}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )


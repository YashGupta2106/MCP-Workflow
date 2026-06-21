"""
observability_engine.py — Instrumented WorkflowEngine for Observability Dashboard
==================================================================================
A subclass of WorkflowEngine that wraps execution to collect detailed trace data:

- Per-step timing (started_at, finished_at, duration_ms)
- HTTP detail capture (method, URL, status code, response size)
- Variable snapshots after each step
- Condition/loop metadata (which branches taken, iteration counts)
- Trace storage (in-memory deque, max 100 traces)
- Unique trace IDs (UUID per execution)

This is completely non-invasive: it imports the original WorkflowEngine
and wraps its methods without modifying any existing code.

Usage:
    engine = ObservabilityEngine('workflows.yaml', 'http://localhost:4010')
    result, trace = engine.run_workflow_traced('server_health_check', {'SystemId': 'Server1'})
"""

import uuid
import time
import json
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from workflow_engine import WorkflowEngine

logger = logging.getLogger("observability_engine")


class StepTrace:
    """Detailed trace of a single workflow step execution."""

    def __init__(self, step_id: str, step_index: int, description: str = ""):
        self.trace_id = str(uuid.uuid4())[:8]
        self.step_id = step_id
        self.step_index = step_index
        self.description = description
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None
        self.duration_ms: float = 0

        # HTTP details
        self.http_method: Optional[str] = None
        self.http_endpoint: Optional[str] = None
        self.http_resolved_url: Optional[str] = None
        self.http_status_code: Optional[int] = None
        self.http_response_size: int = 0

        # Execution details
        self.status: str = "pending"  # pending, running, success, skipped, error
        self.action: str = "continue"
        self.error: Optional[str] = None

        # Condition evaluation
        self.condition_expr: Optional[str] = None
        self.condition_result: Optional[str] = None

        # Loop details
        self.is_loop: bool = False
        self.loop_source: Optional[str] = None
        self.loop_variable: Optional[str] = None
        self.loop_iterations_total: int = 0
        self.loop_iterations_completed: int = 0
        self.loop_iterations: List[dict] = []

        # Variables extracted
        self.extracted_variables: Dict[str, Any] = {}
        self.context_snapshot: Dict[str, Any] = {}

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "step_id": self.step_id,
            "step_index": self.step_index,
            "description": self.description,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2),
            "http": {
                "method": self.http_method,
                "endpoint": self.http_endpoint,
                "resolved_url": self.http_resolved_url,
                "status_code": self.http_status_code,
                "response_size": self.http_response_size,
            } if self.http_method else None,
            "status": self.status,
            "action": self.action,
            "error": self.error,
            "condition": {
                "expression": self.condition_expr,
                "result": self.condition_result,
            } if self.condition_expr else None,
            "loop": {
                "source": self.loop_source,
                "variable": self.loop_variable,
                "iterations_total": self.loop_iterations_total,
                "iterations_completed": self.loop_iterations_completed,
                "iterations": self.loop_iterations,
            } if self.is_loop else None,
            "extracted_variables": self.extracted_variables,
        }


class WorkflowTrace:
    """Complete trace of a workflow execution."""

    def __init__(self, workflow_name: str, params: dict):
        self.id = str(uuid.uuid4())
        self.workflow_name = workflow_name
        self.params = params
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: Optional[str] = None
        self.duration_ms: float = 0
        self.success: bool = False
        self.error: Optional[str] = None
        self.steps: List[StepTrace] = []
        self.total_http_calls: int = 0
        self.total_steps: int = 0
        self.variables: Dict[str, Any] = {}
        self.output: str = ""
        self.next_workflows: list = []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_name": self.workflow_name,
            "params": self.params,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
            "total_steps": self.total_steps,
            "total_http_calls": self.total_http_calls,
            "steps": [s.to_dict() for s in self.steps],
            "variables": self.variables,
            "output": self.output,
            "next_workflows": self.next_workflows,
        }

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "workflow_name": self.workflow_name,
            "started_at": self.started_at,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "total_steps": self.total_steps,
            "total_http_calls": self.total_http_calls,
            "steps_succeeded": sum(1 for s in self.steps if s.status == "success"),
            "steps_skipped": sum(1 for s in self.steps if s.status == "skipped"),
            "steps_errored": sum(1 for s in self.steps if s.status == "error"),
        }


class ObservabilityEngine(WorkflowEngine):
    """
    Instrumented WorkflowEngine that collects detailed execution traces.

    Uses the same API as WorkflowEngine but adds a `run_workflow_traced()`
    method that returns both the normal result and a detailed trace object.
    """

    def __init__(
        self,
        workflows_file: str = "workflows.yaml",
        base_url: str = "http://localhost:4010",
        timeout: int = 30,
        max_traces: int = 100,
    ):
        super().__init__(workflows_file, base_url, timeout)
        self._traces: deque = deque(maxlen=max_traces)
        self._current_trace: Optional[WorkflowTrace] = None
        self._sse_callbacks: List = []
        logger.info("ObservabilityEngine initialized with max %d traces", max_traces)

    # ------------------------------------------------------------------
    #  Trace storage
    # ------------------------------------------------------------------

    def get_traces(self) -> List[dict]:
        """Return summary of all stored traces."""
        return [t.to_summary() for t in reversed(self._traces)]

    def get_trace(self, trace_id: str) -> Optional[dict]:
        """Return full detail for a single trace."""
        for t in self._traces:
            if t.id == trace_id:
                return t.to_dict()
        return None

    def register_sse_callback(self, callback):
        """Register a callback for live SSE updates."""
        self._sse_callbacks.append(callback)

    def unregister_sse_callback(self, callback):
        """Remove an SSE callback."""
        if callback in self._sse_callbacks:
            self._sse_callbacks.remove(callback)

    def _emit_sse(self, event: str, data: dict):
        """Emit an SSE event to all registered callbacks."""
        for cb in self._sse_callbacks:
            try:
                cb(event, data)
            except Exception:
                pass

    # ------------------------------------------------------------------
    #  Traced execution
    # ------------------------------------------------------------------

    def run_workflow_traced(
        self, name: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[dict, dict]:
        """
        Execute a workflow and return (result, trace).

        The result is the same dict as WorkflowEngine.run_workflow().
        The trace is a detailed dict with per-step timing and metadata.
        """
        params = params or {}
        trace = WorkflowTrace(name, params)
        self._current_trace = trace
        start_time = time.perf_counter()

        self._emit_sse("workflow_start", {
            "id": trace.id,
            "workflow_name": name,
            "params": params,
            "started_at": trace.started_at,
        })

        wf = self._workflow_map.get(name)
        if wf is None:
            trace.success = False
            trace.error = f"Workflow '{name}' not found"
            trace.finished_at = datetime.now(timezone.utc).isoformat()
            trace.duration_ms = (time.perf_counter() - start_time) * 1000
            self._traces.append(trace)
            self._current_trace = None
            result = self._error_result(name, trace.error, trace.started_at)
            self._emit_sse("workflow_end", trace.to_summary())
            return result, trace.to_dict()

        # Build initial context
        context: Dict[str, Any] = {}
        for p in wf.get("parameters", []):
            if p.get("default") is not None:
                context[p["name"]] = p["default"]
        if params:
            context.update(params)

        steps = wf.get("steps", [])
        step_index_map = {s["step_id"]: idx for idx, s in enumerate(steps)}
        trace.total_steps = len(steps)
        step_results: List[dict] = []
        current_idx = 0
        success = True
        error_msg: Optional[str] = None

        # Step execution loop with tracing
        while current_idx < len(steps):
            step = steps[current_idx]
            step_id = step["step_id"]

            step_trace = StepTrace(
                step_id=step_id,
                step_index=current_idx,
                description=step.get("description", ""),
            )
            step_trace.started_at = datetime.now(timezone.utc).isoformat()
            step_trace.status = "running"
            step_trace.http_method = step.get("action", "GET").upper()
            step_trace.http_endpoint = step.get("endpoint", "")

            # Resolve the endpoint URL for display
            if step_trace.http_endpoint:
                step_trace.http_resolved_url = self._resolve_template(
                    step_trace.http_endpoint, context
                )

            # Check for condition
            if "condition" in step:
                cond = step["condition"]
                step_trace.condition_expr = cond.get("if", "")

            # Check for loop
            if "loop_over" in step:
                step_trace.is_loop = True
                step_trace.loop_source = step["loop_over"]
                step_trace.loop_variable = step["loop_variable"]
                items = context.get(step["loop_over"], [])
                if not isinstance(items, list):
                    items = [items] if items else []
                step_trace.loop_iterations_total = len(items)

            self._emit_sse("step_start", {
                "trace_id": trace.id,
                "step": step_trace.to_dict(),
            })

            step_start = time.perf_counter()

            try:
                result = self._execute_step(
                    step, context, step_index_map, current_idx + 1, len(steps)
                )
                step_results.append(result)

                step_trace.status = result.get("status", "success")
                step_trace.action = result.get("action", "continue")
                step_trace.http_status_code = result.get("status_code")

                if result.get("extracted"):
                    step_trace.extracted_variables = result["extracted"]

                if "iterations_completed" in result:
                    step_trace.loop_iterations_completed = result["iterations_completed"]

                # Condition result
                if step_trace.condition_expr:
                    if step_trace.status == "skipped":
                        step_trace.condition_result = result.get("action", "skip")
                    else:
                        step_trace.condition_result = "continue"

                # Handle goto
                if result.get("action") == "goto":
                    target = result.get("goto_target", "")
                    step_trace.action = f"goto:{target}"
                    if target in step_index_map:
                        step_trace.finished_at = datetime.now(timezone.utc).isoformat()
                        step_trace.duration_ms = (time.perf_counter() - step_start) * 1000
                        step_trace.context_snapshot = self._safe_snapshot(context)
                        trace.steps.append(step_trace)
                        trace.total_http_calls += 1 if step_trace.http_status_code else 0
                        self._emit_sse("step_end", {
                            "trace_id": trace.id,
                            "step": step_trace.to_dict(),
                        })
                        current_idx = step_index_map[target]
                        continue

                # Handle stop
                if result.get("action") == "stop":
                    success = False
                    error_msg = f"Step '{step_id}' triggered stop: {result.get('error', '')}"

            except Exception as exc:
                step_trace.status = "error"
                step_trace.error = str(exc)
                step_results.append(
                    {"step_id": step_id, "status": "error", "error": str(exc)}
                )
                on_err = step.get("on_error", "continue")
                if on_err == "stop":
                    success = False
                    error_msg = f"Step '{step_id}' failed: {exc}"
                elif on_err.startswith("goto:"):
                    target = on_err[5:]
                    if target in step_index_map:
                        step_trace.finished_at = datetime.now(timezone.utc).isoformat()
                        step_trace.duration_ms = (time.perf_counter() - step_start) * 1000
                        trace.steps.append(step_trace)
                        self._emit_sse("step_end", {
                            "trace_id": trace.id,
                            "step": step_trace.to_dict(),
                        })
                        current_idx = step_index_map[target]
                        continue

            step_trace.finished_at = datetime.now(timezone.utc).isoformat()
            step_trace.duration_ms = (time.perf_counter() - step_start) * 1000
            step_trace.context_snapshot = self._safe_snapshot(context)
            if step_trace.http_status_code:
                trace.total_http_calls += 1
            if step_trace.is_loop and step_trace.loop_iterations_completed > 0:
                trace.total_http_calls += step_trace.loop_iterations_completed

            trace.steps.append(step_trace)

            self._emit_sse("step_end", {
                "trace_id": trace.id,
                "step": step_trace.to_dict(),
            })

            if not success:
                break

            current_idx += 1

        # Finalize trace
        output = self._render_output(wf.get("output_template", ""), context)
        suggested = self._evaluate_next_workflows(
            wf.get("next_workflows", []), context
        )

        trace.success = success
        trace.error = error_msg
        trace.finished_at = datetime.now(timezone.utc).isoformat()
        trace.duration_ms = (time.perf_counter() - start_time) * 1000
        trace.variables = self._sanitize_variables(context)
        trace.output = output
        trace.next_workflows = suggested

        self._traces.append(trace)
        self._current_trace = None

        self._emit_sse("workflow_end", trace.to_summary())

        engine_result = {
            "workflow_name": name,
            "success": success,
            "steps_executed": step_results,
            "variables": self._sanitize_variables(context),
            "output": output,
            "next_workflows": suggested,
            "error": error_msg,
            "started_at": trace.started_at,
            "finished_at": trace.finished_at,
        }

        return engine_result, trace.to_dict()

    @staticmethod
    def _safe_snapshot(ctx: dict, max_items: int = 20) -> dict:
        """Take a JSON-safe snapshot of context for trace storage."""
        snapshot = {}
        count = 0
        for k, v in ctx.items():
            if count >= max_items:
                break
            try:
                s = str(v)
                if len(s) > 200:
                    s = s[:200] + "..."
                snapshot[k] = s
                count += 1
            except Exception:
                snapshot[k] = "<non-serializable>"
                count += 1
        return snapshot

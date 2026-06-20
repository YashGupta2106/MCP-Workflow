# 👤 Person 5 — The Closer: Integration Guide & Pitch Master

> **Your job in one sentence:** Wire Person 4's MCP server into Claude Desktop, test it end-to-end with natural language, calculate the final token metrics, and present the pitch dashboard.

---

## 📋 Table of Contents

1. [What You Own](#what-you-own)
2. [Final Metrics (Proof of Value)](#final-metrics)
3. [Step 1 — Install Dependencies](#step-1--install-dependencies)
4. [Step 2 — Run the Metrics Calculator](#step-2--run-the-metrics-calculator)
5. [Step 3 — Connect Claude Desktop](#step-3--connect-claude-desktop)
6. [Step 4 — Test with Natural Language](#step-4--test-with-natural-language)
7. [Step 5 — Open the Pitch Dashboard](#step-5--open-the-pitch-dashboard)
8. [Troubleshooting](#troubleshooting)

---

## What You Own

| File | Status | Your responsibility |
|---|---|---|
| `workflow_engine.py` | ✅ Person 3 | Read-only |
| `workflows.yaml` | ✅ Person 2 | Read-only |
| `mcp_server.py` | ✅ Person 4 | Read-only |
| `calculate_metrics.py` | 🆕 You created | Runs the after-metrics calculation |
| `specs/after_metrics.json` | 🆕 You generated | The "After" proof numbers |
| `pitch_dashboard/index.html` | 🆕 You created | The hackathon presentation |
| `claude_desktop_config.json` | 🆕 You created | Drop-in Claude Desktop config |
| `PERSON5_README.md` | 🆕 You created | This file |

---

## Final Metrics

These are the numbers you will present to the hackathon judges:

| Metric | Before | After | Reduction |
|---|---|---|---|
| **Tool count** | 133 raw endpoints | 22 MCP tools | **83.5% ✅** |
| **Token count** | 410,562 tokens | 3,374 tokens | **99.2%** |
| **LLM calls needed** | 1 per API call | 0 at runtime | Design-time only |

> The ≥80% tool reduction threshold is **met and exceeded** at **83.5%**.

---

## Step 1 — Install Dependencies

```bash
pip install -r requirements.txt
pip install "mcp[cli]"
```

Verify MCP is installed:
```bash
python -c "import mcp; print(mcp.__version__)"
```

---

## Step 2 — Run the Metrics Calculator

```bash
python calculate_metrics.py
```

Expected output:
```
=================================================================
  PERSON 5 -- AFTER-METRICS CALCULATOR
=================================================================
...
  TOOL COUNT REDUCTION
  Before (133 raw endpoints as tools):     133
  After  (22 MCP workflow tools):          22
  Reduction:                               111 tools
  Reduction %:                             83.5%
  >=80% threshold:                         PASSES

  TOKEN REDUCTION
  Full spec tokens (baseline):             410,562
  MCP tool descriptions tokens:            3,374
  Reduction vs full spec:                  99.2%
```

This generates `specs/after_metrics.json` with the full breakdown.

---

## Step 3 — Connect Claude Desktop

### 3a. Find your Claude Desktop config file

| OS | Path |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

### 3b. Add the MCP server config

Copy the contents of `claude_desktop_config.json` (already pre-filled with your path):

```json
{
  "mcpServers": {
    "redfish-workflow-proxy": {
      "command": "python",
      "args": ["C:\\Users\\romir\\Desktop\\Projects\\MCP-Workflow\\mcp_server.py"],
      "env": {}
    }
  }
}
```

If Claude Desktop already has other MCP servers configured, merge the `"redfish-workflow-proxy"` entry into the existing `"mcpServers"` object.

### 3c. Restart Claude Desktop

Fully quit and reopen Claude Desktop. After restart, you should see **22 tools** listed when Claude is asked about available tools.

### 3d. Start Prism (optional — for live execution)

Without Prism, tools appear in Claude but workflow execution returns HTTP 503. For a full demo:

```bash
npx @stoplight/prism-cli mock specs/merged/full_spec.yaml --port 4010
```

---

## Step 4 — Test with Natural Language

Type these prompts into Claude Desktop and verify the correct tool is invoked:

| Prompt | Expected Tool | What Happens |
|---|---|---|
| *"Check the health of server Server1"* | `server_health_check` | Runs 8-step health workflow |
| *"Show me all available workflows"* | `list_workflows_meta` | Returns catalogue of 19 tools |
| *"Update firmware on my rack"* | `firmware_update` | Checks inventory, triggers update |
| *"Is my chassis overheating?"* | `thermal_and_power_monitoring` | Reads temps, fans, PSUs |
| *"Enable Secure Boot on S1"* | `secure_boot_management` | Reads and patches SecureBoot |
| *"The workflow failed — show me the raw endpoints for firmware_update"* | `list_raw_endpoints` | Reveals 8 underlying endpoints |
| *"Call GET /redfish/v1/Systems/Server1 directly"* | `run_raw_endpoint` | Fires raw HTTP request |

### Verifying the tier-toggle (hierarchical exposure)

1. Ask: *"List the raw Redfish endpoints for server_health_check"*
2. Claude should call `list_raw_endpoints("server_health_check")`
3. Response shows 7 raw endpoints
4. Ask Claude to call one directly via `run_raw_endpoint`

---

## Step 5 — Open the Pitch Dashboard

No server needed — just open the HTML file in any browser:

```bash
start pitch_dashboard\index.html
```

Or on macOS:
```bash
open pitch_dashboard/index.html
```

The dashboard includes:
- ✅ Animated hero counters (83.5%, 99.2%, etc.)
- ✅ Before/After tool count comparison
- ✅ Four Chart.js charts (tools, tokens, categories, coverage)
- ✅ Full 5-person pipeline diagram
- ✅ All 19 workflow cards with metadata
- ✅ 6 demo prompt examples
- ✅ Claude Desktop config snippet with copy button

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Claude shows 0 tools | Config path wrong | Check path in `claude_desktop_config.json`, restart Claude |
| `ModuleNotFoundError: mcp` | MCP not installed | `pip install "mcp[cli]"` |
| All workflows return HTTP 503 | Prism not running | Start Prism on port 4010 (or demo without live calls) |
| `FileNotFoundError: workflows.yaml` | Wrong working dir | Run `python mcp_server.py` from the repo root |
| `calculate_metrics.py` fails | Missing baseline | Run `python parse_spec.py` first (Person 1's script) |
| Charts not loading in dashboard | No internet | Chart.js loads from CDN; use local fallback if offline |

---

## Architecture Summary

```
User prompt (Claude Desktop)
        ↓
  MCP Server (mcp_server.py)  ← Person 4
        ↓
  WorkflowEngine (workflow_engine.py)  ← Person 3
        ↓
  workflows.yaml  ← Person 2
        ↓
  Prism Mock Server :4010  ← Person 1
```

**133 raw HTTP calls → 22 semantic tool invocations → 83.5% reduction ✅**

---

*Person 5 scope complete. The pitch dashboard, metrics, and integration config are all in this branch.*

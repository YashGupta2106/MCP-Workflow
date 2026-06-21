# 🚀 MCP Workflow Proxy — Redfish Edition

> **82.0% Tool Reduction • 74.7% Token Savings • 133 Endpoints → 24 High-Value MCP Tools**
>
> A Model Context Protocol (MCP) server that simplifies a raw 133-endpoint DMTF Redfish spec into **21 semantic workflow tools** + **3 advanced meta-tools**. This gives LLM agents (like Claude or Cursor) the power to manage entire server infrastructures with plain English, eliminating context window bloat and tool selection confusion.

---

## ⚡ Key Highlights
* **82.0% Tool Count Reduction:** Collapses 133 raw, confusing API endpoints into 24 intelligent, semantic MCP tools.
* **74.7% Token Footprint Savings:** Reduces tool definition size from **12,060+** tokens down to **3,058** tokens (and **99.3% savings** compared to raw OpenAPI spec ingestion).
* **Zero Runtime LLM Cost:** Workflow execution runs locally in a pure Python engine. No LLM calls are made at runtime, ensuring sub-second execution times and deterministic behavior.
* **Hierarchical Exposure ("Tier Toggle"):** Provides high-level abstractions but exposes an escape hatch toolset if the LLM needs to call raw endpoints.
* **Stateful Cache Integration:** Implements an in-memory TTL cache for GET calls that automatically invalidates on state-changing requests (POST/PATCH/PUT/DELETE) within a workflow execution.
* **Dynamic Natural Language Builder:** Generate new workflow YAML templates on-the-fly using plain English prompts, which hot-reload directly into the active MCP server tools without server downtime.
* **Rich Observability Dashboard:** FastAPI-powered dashboard with real-time SSE execution tracing, mapping visualizations, metrics charts, and a manual execution portal.

---

## 📐 High-Level Architecture

The MCP Workflow Proxy operates in a hybrid **two-phase workflow**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          1. DESIGN TIME (Offline)                           │
│                                                                             │
│  Raw OpenAPI Spec ──► parse_spec.py ──► summaries ──► LLM Clustering ──────┐│
│   (133 Endpoints)       (Person 1)     (Token-Clean)  (Design-Time Prompt)  ││
│                                                                            ││
│                                           workflows.yaml ◄─────────────────┘│
│                                     (21 Workflow Blueprints)                │
└─────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             │ (Loads YAML & registers tools)
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          2. RUNTIME (Local Engine)                          │
│                                                                             │
│  AI Agent  ──► MCP Client  ──► mcp_server.py ──► workflow_engine.py         │
│  (Claude,       (FastMCP)       (stdio/SSE)       (Chaining & Conditions)   │
│   Cursor)                                               │                   │
│                                                         ▼                   │
│                                              Local Caching (GETs)           │
│                                                         │                   │
│                                                         ▼                   │
│                                                Prism Mock / Real BMC        │
│                                                  (localhost:4010)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Structure

```
MCP-Workflow/
├── download_spec.py             # Downloads DMTF Redfish schema files (Person 1)
├── parse_spec.py                # Merges and cleans schemas into summary format (Person 1)
├── fix_spec_for_prism.py        # Patches merged OpenAPI spec for compatibility with Prism (Person 1)
├── workflows.yaml               # Declarative workflow blueprints (21 YAML profiles) (Person 2)
├── workflow_engine.py           # Core runtime engine with variable chaining, loops, and conditions (Person 3)
├── mcp_server.py                # Wraps the engine as a FastMCP stdio/SSE server (Person 4)
├── calculate_metrics.py         # Computes before/after tool/token metrics (Person 5)
├── claude_desktop_config.json    # Drop-in configuration for Claude Desktop Integration (Person 5)
├── nl_workflow_generator.py     # Custom dynamic workflow synthesizer (Gemini Pro / Local Offline)
├── observability_engine.py      # Instrumented executor with timing and HTTP request tracing
├── observability_server.py      # FastAPI server serving live SSE stream and HTML dashboard
├── requirements.txt             # Python project dependencies (includes FastMCP, cachetools, FastAPI)
├── specs/
│   ├── raw/                     # Original OpenAPI schema components (85 files)
│   ├── merged/
│   │   ├── full_spec.yaml       # Merged Redfish spec (OpenAPI 3.0 format)
│   │   └── full_spec_local.yaml # Merged spec patched with local mock server details
│   ├── cleaned/
│   │   ├── all_endpoints.json   # Processed endpoint lists
│   │   └── endpoints_summary.yaml # Token-efficient summary for LLM design-time input
│   ├── baseline_metrics.json    # Original metrics (133 tools, 410,562 full spec tokens)
│   └── after_metrics.json       # Live metrics verification output
├── dashboard/                   # Main Observability Dashboard UI (HTML, CSS, JS)
├── pitch_dashboard/             # Standalone presentation deck highlighting key hackathon deliverables
└── prompts/
    └── workflow_generation_prompt.md # The exact Claude prompt used to group endpoints
```

---

## 🛠️ Quick Start

Follow these simple steps to set up a mock Redfish hardware environment, start the MCP server, and launch the observability dashboard.

### Prerequisites

* **Python 3.10+** (runtime)
* **Node.js 18+** (for running the Prism mock server)

### 1. Install Dependencies

Install the Python libraries and the MCP CLI tool:

```powershell
pip install -r requirements.txt
pip install "mcp[cli]"
```

### 2. Start the Mock Server

Use Prism to spin up a mock server that simulates real server hardware using the local OpenAPI spec:

```powershell
npx @stoplight/prism-cli mock specs/merged/full_spec_local.yaml --port 4010
```

### 3. Run the MCP Server

Start the stdio-based MCP server:

```powershell
python mcp_server.py
```
*The server will start listening on standard input/output (`stdio`) and will register **24 tools** with any client.*

### 4. Launch the Observability Dashboard & NL Builder

In a separate terminal, launch the FastAPI observability server:

```powershell
python observability_server.py
```
*This will automatically launch your default browser to `http://localhost:8765`. If it doesn't open, navigate there manually.*

---

## 📊 Live Metrics & Verification

To verify that the implementation satisfies the hackathon thresholds (tool reduction ≥80%, token reduction ≥70%), run the verification tool:

```powershell
python calculate_metrics.py
```

### Measured Project Metrics:
| Metric Component | Before | After (MCP Proxy) | Reduction % | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Exposed MCP Tools** | 133 endpoints | **24 tools** (21 workflows + 3 meta) | **82.0%** | **PASS (≥80%)** |
| **Tool Definition Tokens** | 12,060+ (est.) | **3,058** | **74.7%** | **PASS (≥70%)** |
| **Full Spec Raw Ingestion** | 410,562 | **3,058** | **99.3%** | Info |

---

## 🔌 Integrating with Claude Desktop

To let Claude Desktop control your mock server using these high-level workflow tools, follow these instructions:

1. Locate your Claude Desktop configuration file:
   * **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   * **macOS/Linux:** `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Add the `redfish-workflow-proxy` config (make sure to replace `C:\path\to\MCP-Workflow` with your actual repository path):

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

3. Save the file and **restart Claude Desktop**.
4. Ask Claude to discover the tools:
   * *"What tools are available?"*
   * *"Perform a health check on server S1."*

---

## 💡 How to Use the MCP Tools

### 1. High-Level Workflows (21 Tools)
These tools perform multi-step, conditional operations over the Redfish API.
* **`server_health_check`**: Runs an 8-step diagnostics pipeline across systems, processors, memory, chassis, and thermal logs. Features conditional logic: if status is healthy, it returns immediately; if degraded, it dives into sub-resource checks.
* **`firmware_update`**: Inspects existing inventory versions, compares against targeted image URIs, triggers a simple update task, and polls the progress state.
* **`hardware_inventory_report`**: Gathers comprehensive inventory data including network cards, PCI devices, and storage arrays in a single execution.

*Example prompts for Claude:*
* *"Run a complete health status report on system Server1."*
* *"Update the server firmware using the image http://firmware.local/v2.bin"*
* *"Get the thermal levels and power stats for the chassis."*

### 2. Tier Toggle & Escape Hatch (3 Meta-Tools)
If a high-level workflow fails or the agent encounters an edge case that requires direct API access, it uses the Tier Toggle:
1. **`list_workflows_meta`**: Ingests all workflows to let the LLM search available catalog definitions.
2. **`list_raw_endpoints`**: Takes a workflow name and returns its constituent API endpoints (e.g. `GET /redfish/v1/Systems/{SystemId}`).
3. **`run_raw_endpoint`**: The ultimate escape hatch. Executes a direct, raw HTTP call with a JSON payload to the mock server, bypassing the high-level workflow abstraction.

*Example prompt sequence for Claude:*
> **User:** *"Configure a custom bios setting that isn't in the bios workflow."*
> **Claude:** *"I will search the bios workflows first. Let me see its raw endpoints."* (calls `list_raw_endpoints("bios_configuration")`)
> **Claude:** *"I see the bios endpoints. I will now perform a surgical raw endpoint write."* (calls `run_raw_endpoint(method="PATCH", path="/redfish/v1/Systems/Server1/Bios/Settings", body_json="{\"Attributes\": {\"BootMode\": \"Uefi\"}}")`)

---

## 🔍 Features in Detail

### 1. In-Memory Request Caching
Within a single workflow execution, `GET` responses are stored in a local cache using `cachetools.TTLCache`.
* **Deduplication:** Repeated reads to `/redfish/v1/Systems/Server1` within the same flow hit the cache, saving network latency.
* **Auto-Invalidation:** Any state-changing method (`POST`, `PATCH`, `PUT`, `DELETE`) immediately purges cached entries for that URL to prevent stale read hazards.

### 2. Real-Time Observability Dashboard
Run `python observability_server.py` to open the web console.
* **Overview Tab:** Live statistics displaying tool and token metrics, execution history counts, and success rates.
* **Workflow Map:** Visualizes the dynamic relationships and mappings showing how workflow nodes hook into raw endpoints.
* **Execution Traces:** A live tracing timeline driven by Server-Sent Events (SSE). Click **Execute**, pass parameters, and watch step-by-step timings, response sizes, status codes, and context variables update as the engine executes.
* **Workflow Catalog:** A searchable library of all 21 blueprints.

### 3. Natural Language Workflow Builder
Located in the **NL Builder** tab of the dashboard, or triggered via the API:
* Write a requirement in plain English (e.g. *"Create a workflow that checks system memory, then checks storage, and restarts the chassis if degraded"*).
* The backend sends the prompt to Gemini Pro (or a local heuristics engine if no key is provided).
* The builder compiles a clean YAML workflow blueprint matching the execution engine's syntax.
* The file is automatically appended to `workflows.yaml` and the server **hot-reloads** the configuration on the fly. The newly generated workflow immediately becomes an active MCP tool!

---

## ⚡ Extension Guide: Onboarding a New Spec in 5 Minutes

To adapt this MCP Workflow Proxy to a completely different API (e.g., Kubernetes, GitHub, or AWS):

1. **Place the Spec:** Drop your raw OpenAPI schema YAML/JSON files into `specs/raw/`.
2. **Consolidate & Clean:** Run `python parse_spec.py` to merge them and generate `specs/cleaned/endpoints_summary.yaml` (a token-efficient path list).
3. **Cluster with AI:** Run the design-time LLM prompt in `prompts/workflow_generation_prompt.md`, feeding it the cleaned summary.
4. **Deploy workflows.yaml:** Save the LLM's output array as `workflows.yaml` in the root.
5. **Start Servers:** Run `python mcp_server.py` and `python observability_server.py`. The new workflows will auto-register as MCP tools!

---

## 👥 Hackathon Team Credits

Built as a modular development pipeline:

| Team Member | Role | Key Contributions |
| :--- | :--- | :--- |
| **Person 1** | Data & Mock Engineer | Spec downloading, OpenAPI parsing, Prism mock patching |
| **Person 2** | AI Clustering Architect | LLM clustering prompts, `workflows.yaml` blueprint structure |
| **Person 3** | Runtime Engine Builder | `workflow_engine.py` logic, loop/branch executor, JSONPath extraction |
| **Person 4** | MCP Server Developer | FastMCP wrapper, Dynamic tool generation, Tier Toggle implementation |
| **Person 5** | Integrator & Pitch Master | Token metrics script, Observability Dashboard, Pitch deck dashboard |

---
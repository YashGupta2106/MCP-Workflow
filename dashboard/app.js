/**
 * MCP Workflow Proxy — Observability Dashboard (app.js)
 * =====================================================
 * All interactive logic for the Observability Dashboard:
 * - View switching (sidebar navigation)
 * - Fetch and display system metrics + charts
 * - Workflow catalog with detail drill-down
 * - Workflow → API mapping visualization
 * - Workflow execution with real-time trace timeline
 * - SSE connection for live execution streaming
 * - Trace history
 */

// =====================================================================
//  Constants & State
// =====================================================================

const API_BASE = '';  // Same origin
let workflowsData = [];
let metricsData = {};
let chartsInitialized = false;
let sseConnection = null;

// Chart instances (for update/destroy)
let chartTools = null;
let chartTokens = null;
let chartCategories = null;
let chartCoverage = null;

// Chart.js global defaults
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.padding = 16;

// =====================================================================
//  View Switching
// =====================================================================

function switchView(viewName) {
  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  // Deactivate all nav items
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Show target view
  const target = document.getElementById(`view-${viewName}`);
  if (target) target.classList.add('active');

  // Activate nav item
  const navItem = document.querySelector(`.nav-item[data-view="${viewName}"]`);
  if (navItem) navItem.classList.add('active');
}

// =====================================================================
//  Data Loading
// =====================================================================

async function loadWorkflows() {
  try {
    const res = await fetch(`${API_BASE}/api/workflows`);
    workflowsData = await res.json();
    renderCatalog();
    renderMappingSidebar();
    populateExecDropdown();
  } catch (err) {
    console.error('Failed to load workflows:', err);
  }
}

async function loadMetrics() {
  try {
    const res = await fetch(`${API_BASE}/api/metrics`);
    metricsData = await res.json();
    renderMetrics();
    renderCharts();
  } catch (err) {
    console.error('Failed to load metrics:', err);
  }
}

async function loadTraces() {
  try {
    const res = await fetch(`${API_BASE}/api/traces`);
    const traces = await res.json();
    renderTraceHistory(traces);
  } catch (err) {
    console.error('Failed to load traces:', err);
  }
}

// =====================================================================
//  Overview: Metrics Rendering
// =====================================================================

function renderMetrics() {
  const tc = metricsData.tool_counts || {};
  const tk = metricsData.token_counts || {};
  const live = metricsData.live_stats || {};

  animateCounter('statToolReduction', tc.tool_reduction_pct || 83.5, '%');
  animateCounter('statTokenSavings', tk.vs_full_spec_reduction_pct || 99.2, '%');
  animateCounter('statWorkflows', tc.workflow_tools || 19, '');
  animateCounter('statEndpoints', tc.before_tools || 133, '');
  animateCounter('statExecutions', live.total_executions || 0, '');

  const successRate = live.total_executions > 0
    ? Math.round((live.successful_executions / live.total_executions) * 100)
    : 100;
  animateCounter('statSuccessRate', successRate, '%');
}

function animateCounter(id, target, suffix) {
  const el = document.getElementById(id);
  if (!el) return;

  const isFloat = target % 1 !== 0;
  const duration = 1200;
  const start = performance.now();
  const startVal = 0;

  function tick(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    const current = startVal + (target - startVal) * eased;

    el.textContent = (isFloat ? current.toFixed(1) : Math.round(current)) + suffix;

    if (progress < 1) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

// =====================================================================
//  Overview: Charts
// =====================================================================

function renderCharts() {
  if (chartsInitialized) return;
  chartsInitialized = true;

  const tc = metricsData.tool_counts || {};
  const tk = metricsData.token_counts || {};
  const cats = metricsData.categories || {};
  const breakdown = metricsData.workflow_breakdown || [];

  // -- Tool Count Bar Chart --
  const ctxTools = document.getElementById('chartTools');
  if (ctxTools) {
    chartTools = new Chart(ctxTools, {
      type: 'bar',
      data: {
        labels: ['Before (Raw)', 'After (MCP)'],
        datasets: [{
          label: 'Tool Count',
          data: [tc.before_tools || 133, tc.after_tools || 22],
          backgroundColor: [
            'rgba(248,113,113,0.7)',
            'rgba(52,211,153,0.7)',
          ],
          borderColor: [
            'rgba(248,113,113,1)',
            'rgba(52,211,153,1)',
          ],
          borderWidth: 2,
          borderRadius: 8,
          barThickness: 60,
        }],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#111827',
            borderColor: 'rgba(99,102,241,0.3)',
            borderWidth: 1,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(255,255,255,0.04)' },
          },
          x: {
            grid: { display: false },
          },
        },
      },
    });
  }

  // -- Token Comparison Doughnut --
  const ctxTokens = document.getElementById('chartTokens');
  if (ctxTokens) {
    chartTokens = new Chart(ctxTokens, {
      type: 'doughnut',
      data: {
        labels: ['MCP Tool Descriptions', 'Tokens Saved'],
        datasets: [{
          data: [
            tk.mcp_tool_descriptions_tokens || 3374,
            (tk.full_spec_before_tokens || 410562) - (tk.mcp_tool_descriptions_tokens || 3374),
          ],
          backgroundColor: [
            'rgba(99,102,241,0.8)',
            'rgba(52,211,153,0.3)',
          ],
          borderColor: ['rgba(99,102,241,1)', 'rgba(52,211,153,0.5)'],
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        cutout: '65%',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            backgroundColor: '#111827',
            borderColor: 'rgba(99,102,241,0.3)',
            borderWidth: 1,
            callbacks: {
              label: ctx => `${ctx.label}: ${ctx.raw.toLocaleString()} tokens`,
            },
          },
        },
      },
    });
  }

  // -- Category Doughnut --
  const categoryColors = {
    monitoring: '#22d3ee',
    configuration: '#818cf8',
    lifecycle: '#fbbf24',
    security: '#f87171',
    maintenance: '#a78bfa',
    diagnostics: '#34d399',
  };

  const ctxCats = document.getElementById('chartCategories');
  if (ctxCats) {
    const labels = Object.keys(cats);
    const data = Object.values(cats);
    const colors = labels.map(l => categoryColors[l] || '#64748b');

    chartCategories = new Chart(ctxCats, {
      type: 'doughnut',
      data: {
        labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
        datasets: [{
          data: data,
          backgroundColor: colors.map(c => c + 'cc'),
          borderColor: colors,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        cutout: '60%',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            backgroundColor: '#111827',
            borderColor: 'rgba(99,102,241,0.3)',
            borderWidth: 1,
          },
        },
      },
    });
  }

  // -- Coverage Horizontal Bar --
  const ctxCoverage = document.getElementById('chartCoverage');
  if (ctxCoverage) {
    const sorted = [...breakdown].sort((a, b) => b.raw_endpoints_covered - a.raw_endpoints_covered);
    const labels = sorted.map(w => w.name.replace(/_/g, ' '));
    const data = sorted.map(w => w.raw_endpoints_covered);
    const colors = sorted.map(w => categoryColors[w.category] || '#64748b');

    chartCoverage = new Chart(ctxCoverage, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Endpoints Covered',
          data: data,
          backgroundColor: colors.map(c => c + '99'),
          borderColor: colors,
          borderWidth: 1,
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#111827',
            borderColor: 'rgba(99,102,241,0.3)',
            borderWidth: 1,
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: 'rgba(255,255,255,0.04)' },
          },
          y: {
            grid: { display: false },
            ticks: { font: { family: "'JetBrains Mono', monospace", size: 10 } },
          },
        },
      },
    });
  }
}

// =====================================================================
//  Catalog: Workflow Cards
// =====================================================================

function renderCatalog() {
  const grid = document.getElementById('catalogGrid');
  if (!grid) return;

  grid.innerHTML = workflowsData.map(wf => {
    const desc = wf.description || '';
    const truncDesc = desc.length > 120 ? desc.slice(0, 120) + '...' : desc;
    return `
      <div class="wf-card ${wf.category}" onclick="showCatalogDetail('${wf.name}')">
        <div class="wf-card-header">
          <span class="wf-card-name">${wf.name}</span>
          <span class="category-badge cat-${wf.category}">${wf.category}</span>
        </div>
        <div class="wf-card-desc">${truncDesc}</div>
        <div class="wf-card-meta">
          <span>⚙️ ${wf.step_count} steps</span>
          <span>🔗 ${wf.raw_endpoint_count} endpoints</span>
          <span>📝 ${(wf.parameters || []).length} params</span>
        </div>
      </div>
    `;
  }).join('');
}

function showCatalogDetail(name) {
  const wf = workflowsData.find(w => w.name === name);
  if (!wf) return;

  const detail = document.getElementById('catalogDetail');
  const steps = wf.steps || [];
  const rawEps = wf.raw_endpoints || [];
  const params = wf.parameters || [];

  detail.innerHTML = `
    <div class="detail-panel">
      <div class="detail-header">
        <h3>${wf.name}</h3>
        <div style="display:flex; gap:8px; align-items:center;">
          <span class="category-badge cat-${wf.category}">${wf.category}</span>
          <button class="close-btn" onclick="document.getElementById('catalogDetail').innerHTML=''">✕ Close</button>
        </div>
      </div>

      <p style="font-size:0.85rem; color:var(--muted); margin-bottom:20px;">${wf.description || ''}</p>

      ${params.length > 0 ? `
        <h4 style="font-size:0.8rem; font-weight:700; margin-bottom:10px; color:var(--accent);">Parameters</h4>
        <div style="margin-bottom:20px;">
          ${params.map(p => `
            <div style="display:flex; gap:12px; padding:6px 0; font-size:0.78rem; border-bottom:1px solid var(--border2);">
              <span style="font-family:var(--mono); color:var(--primary-l); font-weight:600; min-width:120px;">${p.name}</span>
              <span style="color:${p.required ? 'var(--red)' : 'var(--dim)'}; font-size:0.7rem; min-width:60px;">${p.required ? 'required' : 'optional'}</span>
              <span style="color:var(--muted); flex:1;">${p.description || ''}</span>
              ${p.default ? `<span style="font-family:var(--mono); font-size:0.7rem; color:var(--dim);">[${p.default}]</span>` : ''}
            </div>
          `).join('')}
        </div>
      ` : ''}

      <h4 style="font-size:0.8rem; font-weight:700; margin-bottom:10px; color:var(--accent);">Execution Steps (${steps.length})</h4>
      <div class="steps-timeline">
        ${steps.map((s, i) => {
          const method = (s.action || 'GET').toUpperCase();
          const flags = [];
          if (s.condition) flags.push('cond');
          if (s.loop_over) flags.push(`loop:${s.loop_over}`);
          if (s.break_if) flags.push('break');
          if (s.on_error && s.on_error !== 'continue') flags.push(`err:${s.on_error}`);

          const cls = s.condition ? 'condition' : (s.loop_over ? 'loop' : 'success');

          return `
            <div class="step-item ${cls}">
              <div class="step-header">
                <span class="step-id">${s.step_id}</span>
                <span class="method-badge method-${method}">${method}</span>
                ${flags.map(f => {
                  const fCls = f.startsWith('loop') ? 'flag-loop' :
                              f === 'cond' ? 'flag-cond' :
                              f === 'break' ? 'flag-break' : 'flag-err';
                  return `<span class="flow-flag ${fCls}">${f}</span>`;
                }).join('')}
              </div>
              <div class="step-endpoint">${s.endpoint || ''}</div>
              <div class="step-desc">${s.description || ''}</div>
              ${s.extract ? `
                <div class="step-vars">
                  ${Object.entries(s.extract).map(([k,v]) => `
                    <span class="var-name">${k}</span>: <span class="var-value">${v}</span><br/>
                  `).join('')}
                </div>
              ` : ''}
            </div>
          `;
        }).join('')}
      </div>

      ${rawEps.length > 0 ? `
        <h4 style="font-size:0.8rem; font-weight:700; margin:20px 0 10px; color:var(--accent);">Raw Endpoints Covered (${rawEps.length})</h4>
        <div class="endpoint-list">
          ${rawEps.map((ep, i) => {
            const parts = ep.split(' ');
            const method = parts[0];
            const path = parts.slice(1).join(' ');
            return `
              <div class="endpoint-item" style="animation-delay:${i * 30}ms">
                <span class="method-badge method-${method}">${method}</span>
                <span class="ep-path">${path}</span>
              </div>
            `;
          }).join('')}
        </div>
      ` : ''}

      ${wf.output_template ? `
        <h4 style="font-size:0.8rem; font-weight:700; margin:20px 0 10px; color:var(--accent);">Output Template</h4>
        <div style="background:rgba(0,0,0,0.3); border-radius:var(--radius-xs); padding:12px 16px; font-family:var(--mono); font-size:0.72rem; color:var(--muted); white-space:pre-wrap;">${escapeHtml(wf.output_template)}</div>
      ` : ''}
    </div>
  `;

  detail.scrollIntoView({ behavior: 'smooth' });
}

// =====================================================================
//  Mapping: Workflow → API Visualization
// =====================================================================

function renderMappingSidebar() {
  const list = document.getElementById('mappingWorkflowList');
  if (!list) return;

  list.innerHTML = workflowsData.map(wf => `
    <div class="mapping-wf-item" data-wf="${wf.name}" onclick="showMapping('${wf.name}')">
      <div class="name">${wf.name}</div>
      <div class="meta">
        <span class="category-badge cat-${wf.category}" style="font-size:0.55rem; padding:1px 5px;">${wf.category}</span>
        &nbsp;${wf.step_count} steps · ${wf.raw_endpoint_count} endpoints
      </div>
    </div>
  `).join('');
}

function showMapping(name) {
  const wf = workflowsData.find(w => w.name === name);
  if (!wf) return;

  // Highlight active item
  document.querySelectorAll('.mapping-wf-item').forEach(el => el.classList.remove('active'));
  const activeEl = document.querySelector(`.mapping-wf-item[data-wf="${name}"]`);
  if (activeEl) activeEl.classList.add('active');

  const canvas = document.getElementById('mappingCanvas');
  const steps = wf.steps || [];
  const rawEps = wf.raw_endpoints || [];

  canvas.innerHTML = `
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:24px;">
      <h3 style="margin:0;">${wf.name}</h3>
      <span class="category-badge cat-${wf.category}">${wf.category}</span>
      <span style="font-size:0.75rem; color:var(--muted);">${wf.description ? wf.description.slice(0, 80) + '...' : ''}</span>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
      <!-- Step Flow -->
      <div>
        <h4 style="font-size:0.78rem; font-weight:700; color:var(--accent); margin-bottom:12px;">
          ⚙️ Execution Flow (${steps.length} steps)
        </h4>
        <div class="flow-diagram">
          ${steps.map((s, i) => {
            const method = (s.action || 'GET').toUpperCase();
            const methodCls = method.toLowerCase();
            const flags = [];
            if (s.condition) flags.push({ text: 'cond', cls: 'flag-cond' });
            if (s.loop_over) flags.push({ text: `loop`, cls: 'flag-loop' });
            if (s.break_if) flags.push({ text: 'break', cls: 'flag-break' });

            return `
              <div class="flow-node" style="animation-delay:${i * 50}ms">
                <div class="flow-node-icon ${methodCls}">${method.slice(0, 3)}</div>
                <div class="flow-node-content">
                  <div class="flow-step-id">${s.step_id}</div>
                  <div class="flow-step-desc">${s.endpoint || ''}</div>
                </div>
                <div class="flow-flags">
                  ${flags.map(f => `<span class="flow-flag ${f.cls}">${f.text}</span>`).join('')}
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>

      <!-- Raw Endpoints -->
      <div>
        <h4 style="font-size:0.78rem; font-weight:700; color:var(--green); margin-bottom:12px;">
          🔗 Raw API Endpoints (${rawEps.length})
        </h4>
        <div class="endpoint-list">
          ${rawEps.map((ep, i) => {
            const parts = ep.split(' ');
            const method = parts[0];
            const path = parts.slice(1).join(' ');

            // Find which step uses this endpoint
            const matchStep = steps.find(s =>
              ep.toLowerCase().includes((s.action || 'GET').toLowerCase()) &&
              ep.includes(s.endpoint || '___none___')
            );

            return `
              <div class="endpoint-item" style="animation-delay:${i * 40}ms">
                <span class="method-badge method-${method}">${method}</span>
                <span class="ep-path">${path}</span>
                ${matchStep ? `<span class="ep-step">→ ${matchStep.step_id}</span>` : ''}
              </div>
            `;
          }).join('')}
        </div>
      </div>
    </div>
  `;
}

// =====================================================================
//  Execution: Run Workflows
// =====================================================================

function populateExecDropdown() {
  const select = document.getElementById('execWorkflow');
  if (!select) return;

  select.innerHTML = workflowsData.map(wf =>
    `<option value="${wf.name}">${wf.name} (${wf.category})</option>`
  ).join('');

  // Update default params when selection changes
  select.addEventListener('change', () => {
    const wf = workflowsData.find(w => w.name === select.value);
    if (wf && wf.parameters && wf.parameters.length > 0) {
      const defaultParams = {};
      wf.parameters.forEach(p => {
        if (p.required) {
          defaultParams[p.name] = p.type === 'string' ? 'Server1' : '';
        }
      });
      document.getElementById('execParams').value = JSON.stringify(defaultParams, null, 2);
    } else {
      document.getElementById('execParams').value = '{}';
    }
  });

  // Trigger initial change
  select.dispatchEvent(new Event('change'));
}

async function executeWorkflow() {
  const name = document.getElementById('execWorkflow').value;
  const paramsRaw = document.getElementById('execParams').value;
  const btn = document.getElementById('execBtn');

  let params;
  try {
    params = JSON.parse(paramsRaw || '{}');
  } catch (e) {
    alert('Invalid JSON parameters: ' + e.message);
    return;
  }

  // Loading state
  btn.classList.add('loading');
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/execute/${name}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ params }),
    });

    const data = await res.json();
    renderTraceResult(data.trace);

    // Refresh trace history and metrics
    loadTraces();
    loadMetrics();
  } catch (err) {
    console.error('Execution failed:', err);
    document.getElementById('traceResult').innerHTML = `
      <div class="exec-panel" style="border-color: rgba(248,113,113,0.3);">
        <h3 style="color:var(--red);">❌ Execution Failed</h3>
        <p style="color:var(--muted); font-size:0.85rem;">${err.message}</p>
      </div>
    `;
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

function renderTraceResult(trace) {
  if (!trace) return;

  const container = document.getElementById('traceResult');
  const steps = trace.steps || [];
  const totalDuration = trace.duration_ms || 0;

  container.innerHTML = `
    <div class="trace-result">
      <div class="trace-header">
        <h4>${trace.success ? '✅' : '❌'} ${trace.workflow_name}</h4>
        <div class="trace-summary">
          <span style="color:${trace.success ? 'var(--green)' : 'var(--red)'};">
            ${trace.success ? 'SUCCESS' : 'FAILED'}
          </span>
          <span style="color:var(--accent);">${totalDuration.toFixed(0)}ms</span>
          <span>${trace.total_steps} steps</span>
          <span>${trace.total_http_calls} HTTP calls</span>
        </div>
      </div>

      ${trace.error ? `<div style="background:var(--red-bg); border:1px solid rgba(248,113,113,0.3); border-radius:var(--radius-xs); padding:10px 14px; margin-bottom:16px; font-size:0.82rem; color:var(--red);">Error: ${escapeHtml(trace.error)}</div>` : ''}

      <div class="steps-timeline">
        ${steps.map((s, i) => {
          const http = s.http || {};
          const method = http.method || 'GET';
          const statusCode = http.status_code;
          const duration = s.duration_ms || 0;
          const condition = s.condition;
          const loop = s.loop;
          const vars = s.extracted_variables || {};

          const stepClass = s.status === 'success' ? 'success' :
                           s.status === 'skipped' ? 'skipped' :
                           s.status === 'error' ? 'error' : '';

          // Calculate width for duration bar (relative to total)
          const durationPct = totalDuration > 0 ? Math.max((duration / totalDuration) * 100, 2) : 0;

          return `
            <div class="step-item ${stepClass}${loop ? ' loop' : ''}${condition ? ' condition' : ''}">
              <div class="step-header">
                <span class="step-id">${s.step_id}</span>
                ${http.method ? `<span class="method-badge method-${method}">${method}</span>` : ''}
                <span class="status-badge status-${s.status}">${s.status}</span>
                ${s.action && s.action !== 'continue' && s.action !== 'skip' ? `<span style="font-size:0.65rem; color:var(--accent2);">→ ${s.action}</span>` : ''}
              </div>

              ${http.endpoint ? `<div class="step-endpoint">${http.resolved_url || http.endpoint}</div>` : ''}
              <div class="step-desc">${s.description || ''}</div>

              <div class="step-meta">
                <span class="duration">⏱ ${duration.toFixed(1)}ms</span>
                ${statusCode ? `<span class="http-code">${statusCode}</span>` : ''}
                ${loop ? `<span class="loop-info">⟳ ${loop.iterations_completed}/${loop.iterations_total} iterations</span>` : ''}
                ${condition ? `<span class="condition-info">◇ ${condition.expression} → ${condition.result}</span>` : ''}
              </div>

              <!-- Duration bar -->
              <div style="margin-top:6px; height:3px; background:rgba(255,255,255,0.04); border-radius:2px; overflow:hidden;">
                <div style="height:100%; width:${durationPct}%; background:linear-gradient(90deg, var(--primary), var(--accent)); border-radius:2px; transition:width 0.5s ease;"></div>
              </div>

              ${Object.keys(vars).length > 0 ? `
                <div class="step-vars">
                  ${Object.entries(vars).map(([k, v]) => `
                    <span class="var-name">${k}</span> = <span class="var-value">${escapeHtml(String(v).slice(0, 100))}</span><br/>
                  `).join('')}
                </div>
              ` : ''}
            </div>
          `;
        }).join('')}
      </div>

      ${trace.output ? `
        <div style="margin-top:20px; background:rgba(0,0,0,0.2); border-radius:var(--radius-xs); padding:14px 18px;">
          <h4 style="font-size:0.78rem; font-weight:700; color:var(--green); margin-bottom:8px;">📄 Output</h4>
          <pre style="font-size:0.75rem; color:var(--muted); white-space:pre-wrap; padding:0; background:none;">${escapeHtml(trace.output)}</pre>
        </div>
      ` : ''}

      ${(trace.next_workflows || []).length > 0 ? `
        <div style="margin-top:16px;">
          <h4 style="font-size:0.78rem; font-weight:700; color:var(--accent2); margin-bottom:8px;">🔗 Suggested Next Workflows</h4>
          ${trace.next_workflows.map(nw => `
            <div style="padding:6px 12px; margin-bottom:4px; background:rgba(167,139,250,0.08); border-radius:var(--radius-xs); font-size:0.78rem;">
              <span style="font-family:var(--mono); color:var(--primary-l); font-weight:600;">${nw.workflow}</span>
              <span style="color:var(--dim); margin-left:8px;">${nw.reason || ''}</span>
            </div>
          `).join('')}
        </div>
      ` : ''}
    </div>
  `;

  container.scrollIntoView({ behavior: 'smooth' });
}

// =====================================================================
//  Trace History
// =====================================================================

function renderTraceHistory(traces) {
  const container = document.getElementById('traceHistory');
  if (!container) return;

  if (!traces || traces.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="icon">📜</div>
        <h3>No Traces Yet</h3>
        <p>Execute a workflow above to see traces appear here</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <table class="trace-table">
      <thead>
        <tr>
          <th>Status</th>
          <th>Workflow</th>
          <th>Duration</th>
          <th>Steps</th>
          <th>HTTP Calls</th>
          <th>Time</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        ${traces.map(t => `
          <tr onclick="viewTraceDetail('${t.id}')">
            <td>${t.success ? '<span class="status-badge status-success">✓</span>' : '<span class="status-badge status-error">✗</span>'}</td>
            <td class="wf-name">${t.workflow_name}</td>
            <td class="duration">${(t.duration_ms || 0).toFixed(0)}ms</td>
            <td>${t.steps_succeeded || 0}/${t.total_steps || 0}</td>
            <td>${t.total_http_calls || 0}</td>
            <td class="time">${formatTime(t.started_at)}</td>
            <td><button class="close-btn" onclick="event.stopPropagation(); viewTraceDetail('${t.id}')">View</button></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function viewTraceDetail(traceId) {
  try {
    const res = await fetch(`${API_BASE}/api/traces/${traceId}`);
    const trace = await res.json();
    renderTraceResult(trace);
  } catch (err) {
    console.error('Failed to load trace detail:', err);
  }
}

// =====================================================================
//  SSE: Live Connection
// =====================================================================

function connectSSE() {
  const dot = document.getElementById('liveDot');
  const status = document.getElementById('liveStatus');

  try {
    sseConnection = new EventSource(`${API_BASE}/events`);

    sseConnection.addEventListener('connected', () => {
      dot.classList.remove('disconnected');
      status.textContent = 'Connected';
    });

    sseConnection.addEventListener('workflow_start', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Workflow started:', data.workflow_name);
      status.textContent = `Running: ${data.workflow_name}`;
    });

    sseConnection.addEventListener('workflow_end', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Workflow ended:', data.workflow_name, data.success);
      status.textContent = 'Connected';
      // Refresh traces and metrics
      loadTraces();
      loadMetrics();
    });

    sseConnection.addEventListener('step_end', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Step:', data.step?.step_id, data.step?.status);
    });

    sseConnection.addEventListener('heartbeat', () => {
      // Keep alive
    });

    sseConnection.onerror = () => {
      dot.classList.add('disconnected');
      status.textContent = 'Disconnected';
      // Reconnect after 5s
      setTimeout(connectSSE, 5000);
    };
  } catch (err) {
    console.warn('SSE not available:', err);
    dot.classList.add('disconnected');
    status.textContent = 'SSE unavailable';
  }
}

// =====================================================================
//  Utilities
// =====================================================================

function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function formatTime(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoString;
  }
}

// =====================================================================
//  Initialization
// =====================================================================

document.addEventListener('DOMContentLoaded', () => {
  // Load all data
  loadWorkflows();
  loadMetrics();
  loadTraces();

  // Connect SSE
  connectSSE();

  // Auto-refresh metrics every 30 seconds
  setInterval(() => {
    loadMetrics();
    loadTraces();
  }, 30000);
});

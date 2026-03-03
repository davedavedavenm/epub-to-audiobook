# Plan: GPU Status UI in Ops Tab

## Design Direction

**Aesthetic**: Industrial/utilitarian — matches the "Ops" tab's operational character. Think control room panel with live telemetry. Not decorative; functional with personality.

**Approach**: A dedicated **GPU Compute** card in the Ops tab (between Queue Operations and Diagnostics), using the existing card/status-tag/job-btn patterns but with a distinctive GPU flavor: a pulsing status indicator, real-time cost ticker, and manual override controls.

**Typography/Color**: Stays within the existing CSS variable system (works across all 4 themes). GPU-specific accent: warm amber/orange for GPU active state (distinct from the blue accent used elsewhere), keeping existing green/red for healthy/error.

## What Gets Built

### 1. GPU Compute Card (Ops Tab)

A new card in `tab-ops` with three sections:

**A. Status Header Row**
- Left: GPU state indicator — a small pulsing dot (idle=grey, provisioning=amber pulse, active=green pulse, error=red) + state label text
- Right: Compute mode badge showing "CPU" or "GPU" with the current TTS endpoint

**B. Telemetry Strip** (only visible when GPU is active or provisioning)
- Three telemetry cells in a horizontal strip:
  - **Session Time**: elapsed minutes since GPU came up
  - **Session Cost**: running dollar total (e.g., "$0.12")
  - **Cost Cap**: configured cap with a mini progress bar showing spend vs cap
- Styled as a monospace telemetry readout (dark bg even in light theme, like a real instrument panel)

**C. Controls Row**
- **Force GPU** button: calls POST `/api/gpu/scale-up` (disabled when already active/provisioning)
- **Force CPU** button: calls POST `/api/gpu/scale-down` (disabled when already idle)
- **Auto-scale** toggle indicator: shows "Auto: ON (≥3 books)" or "Auto: OFF" — read-only display, not a toggle (config change requires .env edit + restart)
- Buttons use existing `.job-btn` class for consistency

### 2. Header Status Pip

A small status pip in the app header (next to the logo) that shows GPU state at a glance without needing to visit the Ops tab:
- Tiny dot + "CPU" or "GPU" text, ~12px font
- Only visible when GPU is active (hidden when idle to keep header clean)
- Clicking it navigates to the Ops tab

### 3. JavaScript Integration

- New `loadGpuStatus()` function that fetches `/api/gpu/status`
- Called inside the existing `loadOps()` function (piggybacks on the ops refresh cycle)
- Also called on a 10s interval when GPU state is not idle (for live cost updates)
- Updates all GPU UI elements
- Scale-up/down buttons call the API and trigger a refresh

## Files Modified

- **`webapp/templates/index.html`** — All changes in this single file:
  - ~40 lines of CSS (GPU card styles, telemetry strip, status pip, pulse animation)
  - ~20 lines of HTML (GPU card in ops tab, header pip)
  - ~50 lines of JS (loadGpuStatus, button handlers, conditional polling)

## Implementation Steps

1. Add CSS for GPU card: `.gpu-telemetry`, `.gpu-status-dot`, `.gpu-pip`, pulse keyframe animation
2. Add HTML: GPU Compute card between "Queue Operations" and "Conversion Timeline" in ops tab
3. Add HTML: header pip element (hidden by default)
4. Add JS: `loadGpuStatus()` function
5. Wire JS: call from `loadOps()`, button click handlers, conditional fast-poll
6. Test across all 4 themes (light, dark, midnight, forest) and 4 design modes (studio, editorial, technical, minimal)

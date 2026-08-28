# VS Code Remote Debugging Setup for NetBox Plugin

## Overview

This guide explains how to debug the NetBox AAS Integration plugin running in a Docker container from VS Code on your local machine using `debugpy` remote debugging.

The development environment is already configured for debugging:

- **Debug port 5678** is exposed for debugpy
- **NetBox runs with debugpy** enabled automatically
- **VS Code launch configuration** is ready in `.vscode/launch.json`

## Quick Start

### Step 1: Start the Development Environment

```bash
cd dev-environment
docker-compose up -d
```

Wait for NetBox to be healthy:

```bash
docker-compose ps netbox
# Should show: Up ... (healthy)
```

### Step 2: Open VS Code

```bash
# From the project root
cd ..
code .
```

### Step 3: Set a Breakpoint

An easy option to set quick breakpoint to check the debugger is to break at the test connection function:

1. Open `aas_integration/views.py`
2. Go to `test_connection` function
3. Set a breakpoint on:

   ```python
   connection = get_object_or_404(AASConnection, pk=pk)
   ```

**To trigger:**

- First create an AAS Connection in NetBox
- Navigate to the connection detail page
- Click "Test Connection" button

### Step 4: Attach the Debugger

1. In VS Code, press **F5**
2. If prompted, select **"Python: Remote Attach (NetBox)"**
3. Look for these success indicators:
   - Debug toolbar appears at the top
   - Status bar turns **orange/red**
   - **Debug Console** shows "Debugger attached"

### Step 5: Trigger Your Breakpoint

Open your browser and navigate to the URL that triggers your breakpoint (e.g., the connections list page).

When the breakpoint is hit:

- **Execution pauses** with yellow highlight on current line
- **Variables panel** (left) shows all local variables
- **Call Stack** shows how you got here
- **Debug Console** (bottom) lets you evaluate Python expressions

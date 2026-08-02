---
name: unity-mcp-core
description: Use when starting any Unity Editor automation task through MCP for Unity, before calling manage_gameobject, create_script, manage_scene, or any other MCP for Unity tool — establishes editor-state checks, compilation waits, batch_execute usage, and console/screenshot verification that every Unity-MCP tool call depends on.
---

# Unity-MCP Core

Baseline discipline for every MCP for Unity task. Read this once per task, then jump to the domain skill for the actual work (unity-mcp-scene-objects, unity-mcp-scripting, unity-mcp-ui, unity-mcp-assets-materials, unity-mcp-camera-graphics, unity-mcp-testing-editor, unity-mcp-packages-docs).

## Template Notice

Examples across all unity-mcp-* skills are reusable templates, not guarantees. They may be inaccurate across Unity versions, package setups (UGUI/TMP/Input System), and project-specific conventions. Validate targets/components via resources and `find_gameobjects` before applying a template; treat names, enum values, and property payloads as placeholders to adapt. Check console, compilation errors, or a screenshot after implementation.

## Resource-First Workflow

Always read relevant resources before using tools — this prevents errors and gives necessary context.

```
1. Check editor state     → mcpforunity://editor/state
2. Understand the scene   → mcpforunity://scene/gameobject-api
3. Find what you need     → find_gameobjects or resources
4. Take action            → domain-specific tools
5. Verify results          → read_console, manage_camera(action="screenshot"), resources
```

Read `mcpforunity://project/info` before making UI/input/rendering assumptions — it returns `unityVersion`, `renderPipeline`, `activeInputHandler`, and installed packages (`ugui`, `textmeshpro`, `inputsystem`, `uiToolkit`, `screenCapture`).

## Critical Best Practices

### 1. Wait for compilation, then check console — don't call refresh_unity redundantly

`create_script` and `script_apply_edits` already trigger `AssetDatabase.ImportAsset` + `RequestScriptCompilation` automatically. Calling `refresh_unity` afterward is redundant.

```python
# 1. Poll editor state until compilation completes
# Read mcpforunity://editor/state → wait until is_compiling == false

# 2. Check for compilation errors
read_console(types=["error"], count=10, include_stacktrace=True)
```

### 2. Use `batch_execute` for multiple operations (10-100x faster)

```python
batch_execute(
    commands=[                    # list[dict], required, max 25 default (configurable to 100)
        {"tool": "tool_name", "params": {...}},
        ...
    ],
    parallel=False,              # bool, advisory only — Unity may still run sequentially
    fail_fast=False,             # bool, stop on first failure
    max_parallelism=None         # int, max parallel workers
)
```

Not transactional — earlier commands are not rolled back if a later one fails. Also use it for discovery: batch multiple `find_gameobjects` calls instead of calling them one at a time.

### 3. Use screenshots to verify visual results

```python
manage_camera(action="screenshot")                                    # file only, saves to Assets/
manage_camera(action="screenshot", include_image=True)                # inline base64 PNG
manage_camera(action="screenshot", camera="MainCamera", include_image=True, max_resolution=512)
manage_camera(action="screenshot", batch="surround", max_resolution=256)          # 6-angle contact sheet
manage_camera(action="screenshot", batch="surround", view_target="Player", max_resolution=256)
manage_camera(action="screenshot", view_target="Player", view_position=[0, 10, -10], max_resolution=512)
manage_camera(action="screenshot", capture_source="scene_view", include_image=True)  # editor viewport (gizmos, wireframes, grid)
```

Keep `max_resolution` at 256–512 to balance quality vs. token cost. Use `capture_source="scene_view"` to see what the editor viewport shows (not what a game camera sees).

### 4. Check console after major changes

```python
read_console(types=["error", "warning"], count=10, format="detailed")
```

### 5. Always check `editor_state` before complex operations

```python
# Read mcpforunity://editor/state to check:
# - is_compiling: Wait if true
# - is_domain_reload_pending: Wait if true
# - ready_for_tools: Only proceed if true
# - blocking_reasons: Why tools might fail
```

## Parameter Type Conventions

Common patterns, not strict guarantees — `manage_components.set_property` payload shapes can vary by component/property; if a template fails, inspect the component resource payload and adjust.

| Type | Forms accepted |
|------|-----------------|
| Vectors | `[1.0, 2.0, 3.0]` (list) or `"[1.0, 2.0, 3.0]"` (JSON string) |
| Booleans | `True` or `"true"` |
| Colors | `[255, 0, 0, 255]` (0-255) or `[1.0, 0.0, 0.0, 1.0]` (0.0-1.0, auto-converted) |
| Paths | `"Assets/Scripts/MyScript.cs"` (Assets-relative, default), `"mcpforunity://path/Assets/..."`, or `"file:///full/path/..."` |

## Pagination Pattern

Large queries return paginated results — always follow `next_cursor`:

```python
cursor = 0
all_items = []
while True:
    result = manage_scene(action="get_hierarchy", page_size=50, cursor=cursor)
    all_items.extend(result["data"]["items"])
    if not result["data"].get("next_cursor"):
        break
    cursor = result["data"]["next_cursor"]
```

## Multi-Instance Workflow

```python
# 1. List instances via resource: mcpforunity://instances
# 2. Set active instance
set_active_instance(instance="MyProject@abc123")
# 3. All subsequent calls route to that instance
```

## Custom Tools

Discover project-specific custom tools via the `mcpforunity://custom-tools` resource, then invoke with `execute_custom_tool(tool_name="my_custom_tool", parameters={...})`.

## Batch Discovery and Mass Operations

```python
# Batch multiple searches instead of sequential find_gameobjects calls
batch_execute(commands=[
    {"tool": "find_gameobjects", "params": {"search_term": "Camera", "search_method": "by_component"}},
    {"tool": "find_gameobjects", "params": {"search_term": "Player", "search_method": "by_tag"}},
])

# Mass update: find, build command list, execute in chunks of 25
enemies = find_gameobjects(search_term="Enemy", search_method="by_tag")
commands = [{"tool": "manage_components", "params": {
    "action": "set_property", "target": eid, "component_type": "EnemyHealth",
    "property": "maxHealth", "value": 100
}} for eid in enemies["ids"]]
for i in range(0, len(commands), 25):
    batch_execute(commands=commands[i:i+25], parallel=True)
```

## Error Recovery

| Symptom | Cause | Solution |
|---------|-------|----------|
| Tools return "busy" | Compilation in progress | Wait, check `editor_state` |
| "stale_file" error | File changed since SHA | Re-fetch SHA with `get_sha`, retry |
| Connection lost | Domain reload | Wait ~5s (exponential backoff), reconnect |
| Commands fail silently | Wrong instance | Check `set_active_instance` |
| Compilation blocked | Script errors | Check `read_console`, fix, `refresh_unity(mode="force", scope="scripts", compile="request", wait_for_ready=True)`, re-check console |

## Companion skills

Domain work happens in the sibling skills: **unity-mcp-scene-objects**, **unity-mcp-scripting**, **unity-mcp-ui**, **unity-mcp-assets-materials**, **unity-mcp-camera-graphics**, **unity-mcp-testing-editor**, **unity-mcp-packages-docs**. This skill has no reference/ subfolder — everything here is meant to be read in full, every time.

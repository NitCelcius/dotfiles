---
name: unity-mcp-testing-editor
description: Use when running Unity tests, controlling editor state (play mode, menu items, tags/layers), or diagnosing compile errors and console output through MCP for Unity — covers run_tests, get_test_job, manage_editor, execute_menu_item, and read_console.
---

# Unity-MCP Testing & Editor Control Tools

**REQUIRED BACKGROUND:** unity-mcp-core (compilation-wait discipline, editor_state checks).

## manage_editor

```python
manage_editor(action="play")               # Enter play mode
manage_editor(action="pause")
manage_editor(action="stop")
manage_editor(action="set_active_tool", tool_name="Move")  # Move/Rotate/Scale/etc.
manage_editor(action="add_tag", tag_name="Enemy")
manage_editor(action="remove_tag", tag_name="OldTag")
manage_editor(action="add_layer", layer_name="Projectiles")
manage_editor(action="remove_layer", layer_name="OldLayer")
manage_editor(action="open_prefab_stage", prefab_path="Assets/Prefabs/Enemy.prefab")
manage_editor(action="save_prefab_stage")
manage_editor(action="close_prefab_stage")

# Package deployment (no confirmation dialog — for LLM-driven iteration)
manage_editor(action="deploy_package")     # copy configured MCPForUnity source into installed package
manage_editor(action="restore_package")    # revert to pre-deployment backup
```

**Deploy workflow:** set the source path in MCP for Unity Advanced Settings first. `deploy_package` copies source into the project's package location, creates a backup, triggers `AssetDatabase.Refresh`. Follow with `refresh_unity(wait_for_ready=True)` to wait for recompilation. See unity-mcp-packages-docs for the full edit→deploy→test loop.

## execute_menu_item

```python
execute_menu_item(menu_path="File/Save Project")
execute_menu_item(menu_path="GameObject/3D Object/Cube")
execute_menu_item(menu_path="Window/General/Console")
```

## read_console

```python
read_console(action="get", types=["error", "warning", "log"], count=10, filter_text="NullReference",
    page_size=50, cursor=0, format="detailed", include_stacktrace=True)  # format: "plain"|"detailed"|"json"
read_console(action="clear")
```

## run_tests / get_test_job

```python
result = run_tests(mode="EditMode", test_names=["MyTests.TestA", "MyTests.TestB"],
    group_names=["Integration*"], category_names=["Unit"], assembly_names=["Tests"],
    include_failed_tests=True, include_details=False)
# Returns: {"job_id": "abc123", ...}

result = get_test_job(job_id="abc123", wait_timeout=60, include_failed_tests=True, include_details=False)
# Returns: {"status": "complete"|"running"|"failed", "results": {...}}
```

### Run specific tests and check results

```python
# Read mcpforunity://tests/EditMode for the available test list first
result = run_tests(mode="EditMode", test_names=["MyTests.TestPlayerMovement", "MyTests.TestEnemySpawn"],
    include_failed_tests=True)
final = get_test_job(job_id=result["job_id"], wait_timeout=60, include_failed_tests=True)
if final["status"] == "complete":
    for test in final.get("failed_tests", []):
        print(f"FAILED: {test['name']}: {test['message']}")
```

### Run by category, poll to completion

```python
result = run_tests(mode="EditMode", category_names=["Unit"], include_failed_tests=True)
while True:
    status = get_test_job(job_id=result["job_id"], wait_timeout=30)
    if status["status"] in ["complete", "failed"]:
        break
```

### Test-driven pattern

```python
create_script(path="Assets/Tests/Editor/PlayerTests.cs", contents='''using NUnit.Framework;
using UnityEngine;

public class PlayerTests
{
    [Test]
    public void TestPlayerStartsAtOrigin()
    {
        var player = new GameObject("TestPlayer");
        Assert.AreEqual(Vector3.zero, player.transform.position);
        Object.DestroyImmediate(player);
    }
}''')
# create_script auto-triggers import + compile — wait for is_compiling == false, then:
result = run_tests(mode="EditMode", test_names=["PlayerTests.TestPlayerStartsAtOrigin"])
get_test_job(job_id=result["job_id"], wait_timeout=30)
```

## Debugging workflows

### Diagnose compilation errors

```python
errors = read_console(types=["error"], count=20, include_stacktrace=True, format="detailed")
# Parse each error's file:line, use find_in_file (unity-mcp-scripting) to locate the code
# After fixing:
refresh_unity(mode="force", scope="scripts", compile="request", wait_for_ready=True)
read_console(types=["error"], count=10)
```

### Investigate missing references

```python
result = find_gameobjects(search_term="Player", search_method="by_name")
# Read mcpforunity://scene/gameobject/{id}/components — check for null serialized fields
target_result = find_gameobjects(search_term="Target", search_method="by_name")
manage_components(action="set_property", target="Player", component_type="PlayerController",
    property="target", value={"instanceID": target_result["ids"][0]})
```

### Check scene state (e.g. objects that fell through the floor)

```python
hierarchy = manage_scene(action="get_hierarchy", page_size=100, include_transform=True)
for item in hierarchy["data"]["items"]:
    if item.get("transform", {}).get("position", [0,0,0])[1] < -100:
        print(f"Object {item['name']} fell through floor!")
manage_camera(action="screenshot")  # visual confirmation
```

### Domain reload recovery

```python
# Connection may drop after a domain reload — retry with backoff
import time
for attempt in range(5):
    try:
        editor_state = read_resource("mcpforunity://editor/state")
        if editor_state["ready_for_tools"]:
            break
    except:
        time.sleep(2 ** attempt)
```

## Companion skills

**unity-mcp-core** for the baseline workflow (this skill assumes you already know the compile-wait pattern). **unity-mcp-scripting** for the create/edit tools whose output you're testing. **unity-mcp-packages-docs** for the deploy_package iteration loop in depth.

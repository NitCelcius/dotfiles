---
name: unity-mcp-scripting
description: Use when creating or editing C# scripts through MCP for Unity — covers create_script, script_apply_edits, apply_text_edits, validate_script, get_sha, delete_script, find_in_file, and the compile-wait-then-verify cycle after any script change.
---

# Unity-MCP Script Tools

**REQUIRED BACKGROUND:** unity-mcp-core (compilation-wait discipline, console checks).

## create_script

```python
create_script(
    path="Assets/Scripts/MyScript.cs",
    contents='''using UnityEngine;

public class MyScript : MonoBehaviour
{
    void Start() { }
    void Update() { }
}''',
    script_type="MonoBehaviour",  # optional hint
    namespace="MyGame"            # optional
)
```

## script_apply_edits

Structured edits — safer than raw text edits.

```python
script_apply_edits(
    name="MyScript",             # script name, no .cs
    path="Assets/Scripts",       # folder path
    edits=[
        {"op": "replace_method", "methodName": "Update",
         "replacement": "void Update() { transform.Rotate(Vector3.up); }"},
        {"op": "insert_method", "afterMethod": "Start",
         "code": 'void OnEnable() { Debug.Log("Enabled"); }'},
        {"op": "delete_method", "methodName": "OldMethod"},
        {"op": "anchor_insert", "anchor": "void Start()", "position": "before",  # "before"|"after"
         "text": "// Called before Start\n"},
        {"op": "regex_replace", "pattern": "Debug\\.Log\\(", "text": "Debug.LogWarning("},
        {"op": "prepend", "text": "// File header\n"},
        {"op": "append", "text": "\n// File footer"}
    ]
)
```

## apply_text_edits

Precise character-position edits (1-indexed lines/columns) — use when you need surgical control `script_apply_edits` ops don't cover.

```python
apply_text_edits(
    uri="mcpforunity://path/Assets/Scripts/MyScript.cs",
    edits=[{"startLine": 10, "startCol": 5, "endLine": 10, "endCol": 20, "newText": "replacement text"}],
    precondition_sha256="abc123...",  # optional — prevents stale edits, see Error Recovery below
    strict=True
)
```

## validate_script / get_sha / delete_script

```python
validate_script(uri="mcpforunity://path/Assets/Scripts/MyScript.cs", level="standard", include_diagnostics=True)  # level: "basic"|"standard"

get_sha(uri="mcpforunity://path/Assets/Scripts/MyScript.cs")
# Returns: {"sha256": "...", "lengthBytes": 1234, "lastModifiedUtc": "..."}

delete_script(uri="mcpforunity://path/Assets/Scripts/OldScript.cs")
```

## find_in_file

Regex search within a single file's contents (for locating a method/anchor before editing).

```python
find_in_file(uri="mcpforunity://path/Assets/Scripts/MyScript.cs", pattern="public void \\w+", max_results=200, ignore_case=True)
# Returns: line numbers, content excerpts, match positions
```

## The compile-then-verify cycle

**`create_script` and `script_apply_edits` already trigger import + compilation automatically — never call `refresh_unity` afterward, it's redundant.**

```python
# 1. Create/edit
create_script(path="Assets/Scripts/EnemyAI.cs", contents="...")

# 2. Wait for compilation
# Read mcpforunity://editor/state → wait until is_compiling == false

# 3. Check for errors before touching the result
console = read_console(types=["error"], count=10)
if console["messages"]:
    # handle compilation errors — do not proceed to attach/configure
    pass
else:
    manage_gameobject(action="modify", target="Enemy", components_to_add=["EnemyAI"])
    manage_components(action="set_property", target="Enemy", component_type="EnemyAI", properties={"speed": 10.0})
```

## Edit an existing script safely

```python
# 1. Get current SHA (precondition for stale-edit protection)
sha_info = get_sha(uri="mcpforunity://path/Assets/Scripts/PlayerController.cs")

# 2. Locate the target method
matches = find_in_file(uri="mcpforunity://path/Assets/Scripts/PlayerController.cs", pattern="void Update\\(\\)")

# 3. Apply structured edit
script_apply_edits(name="PlayerController", path="Assets/Scripts", edits=[{
    "op": "replace_method", "methodName": "Update",
    "replacement": '''void Update()
    {
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");
        transform.Translate(new Vector3(h, 0, v) * speed * Time.deltaTime);
    }'''
}])

# 4. Validate, then wait for compilation (auto-triggered) and check console
validate_script(uri="mcpforunity://path/Assets/Scripts/PlayerController.cs", level="standard")
read_console(types=["error"], count=10)
```

## Add a method + a using directive together

```python
script_apply_edits(name="GameManager", path="Assets/Scripts", edits=[
    {"op": "insert_method", "afterMethod": "Start",
     "code": '''
    public void ResetGame()
    {
        SceneManager.LoadScene(SceneManager.GetActiveScene().name);
    }'''},
    {"op": "anchor_insert", "anchor": "using UnityEngine;", "position": "after",
     "text": "\nusing UnityEngine.SceneManagement;"}
])
```

## Stale file recovery

```python
try:
    apply_text_edits(uri=script_uri, edits=[...], precondition_sha256=old_sha)
except Exception as e:
    if "stale_file" in str(e):
        new_sha = get_sha(uri=script_uri)
        apply_text_edits(uri=script_uri, edits=[...], precondition_sha256=new_sha["sha256"])
```

## Companion skills

**unity-mcp-core** for the baseline workflow. **unity-mcp-scene-objects** for attaching the finished script to a GameObject and wiring its serialized fields. **unity-mcp-testing-editor** for running EditMode/PlayMode tests against the script and diagnosing compile errors in depth.

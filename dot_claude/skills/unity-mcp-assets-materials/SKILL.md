---
name: unity-mcp-assets-materials
description: Use when managing Unity asset files, prefabs, materials, or textures through MCP for Unity — covers manage_asset (search/create/move/delete), manage_prefabs (headless prefab editing), manage_material (create/color/shader properties), and manage_texture (procedural textures/patterns).
---

# Unity-MCP Asset, Prefab & Material Tools

**REQUIRED BACKGROUND:** unity-mcp-core (batch_execute, console checks).

## manage_asset

```python
manage_asset(action="search", path="Assets", search_pattern="*.prefab", filter_type="Prefab",
    page_size=25, page_number=1, generate_preview=False)  # keep page_size small, avoid base64 bloat
manage_asset(action="get_info", path="Assets/Prefabs/Player.prefab")
manage_asset(action="create", path="Assets/Materials/NewMaterial.mat", asset_type="Material",
    properties={"color": [1, 0, 0, 1]})
manage_asset(action="duplicate", path="Assets/A.prefab", destination="Assets/B.prefab")
manage_asset(action="move", path="Assets/A.prefab", destination="Assets/Prefabs/A.prefab")
manage_asset(action="rename", path="Assets/A.prefab", destination="Assets/B.prefab")
manage_asset(action="create_folder", path="Assets/NewFolder")
manage_asset(action="delete", path="Assets/OldAsset.asset")
```

## manage_prefabs

Headless prefab editing. **To instantiate a prefab into the scene, use `manage_gameobject(action="create", prefab_path="...")` instead** (see unity-mcp-scene-objects) — `manage_prefabs` is for inspecting/editing prefab contents without a scene instance.

```python
manage_prefabs(action="get_info", prefab_path="Assets/Prefabs/Player.prefab")
manage_prefabs(action="get_hierarchy", prefab_path="Assets/Prefabs/Player.prefab")

manage_prefabs(action="create_from_gameobject", target="Player",
    prefab_path="Assets/Prefabs/Player.prefab", allow_overwrite=False)

manage_prefabs(action="modify_contents", prefab_path="Assets/Prefabs/Player.prefab",
    target="ChildObject", position=[0, 1, 0], components_to_add=["AudioSource"])
manage_prefabs(action="modify_contents", prefab_path="Assets/Prefabs/Player.prefab",
    delete_child=["OldChild", "Turret/Barrel"])  # single string or list
manage_prefabs(action="modify_contents", prefab_path="Assets/Prefabs/Player.prefab",
    create_child={"name": "SpawnPoint", "primitive_type": "Sphere", "position": [0, 2, 0]})
manage_prefabs(action="modify_contents", prefab_path="Assets/Prefabs/Player.prefab",
    target="ChildObject", component_properties={"Rigidbody": {"mass": 5.0}, "MyScript": {"health": 100}})
```

## manage_material

```python
manage_material(action="create", material_path="Assets/Materials/Red.mat", shader="Standard",
    properties={"_Color": [1, 0, 0, 1]})
manage_material(action="get_material_info", material_path="Assets/Materials/Red.mat")
manage_material(action="set_material_shader_property", material_path="Assets/Materials/Red.mat",
    property="_Metallic", value=0.8)
manage_material(action="set_material_color", material_path="Assets/Materials/Red.mat",
    property="_BaseColor", color=[0, 1, 0, 1])
manage_material(action="assign_material_to_renderer", target="MyCube",
    material_path="Assets/Materials/Red.mat", slot=0)

# Set renderer color directly — pick the mode deliberately, it changes persistence semantics
manage_material(action="set_renderer_color", target="MyCube", color=[1, 0, 0, 1],
    mode="create_unique")
    # "create_unique": creates a unique .mat asset per object (persistent) — usually what you want
    # "property_block" (default): not persistent
    # "shared": mutates the shared material — avoid on primitives, affects every user of that material
    # "instance": runtime only, not persistent
```

## manage_texture

```python
manage_texture(action="create", path="Assets/Textures/Checker.png", width=64, height=64,
    fill_color=[255, 255, 255, 255])
manage_texture(action="apply_pattern", path="Assets/Textures/Checker.png",
    pattern="checkerboard", palette=[[0,0,0,255], [255,255,255,255]], pattern_size=8)
    # pattern: "checkerboard"|"stripes"|"dots"|"grid"|"brick"
manage_texture(action="apply_gradient", path="Assets/Textures/Gradient.png",
    gradient_type="linear", gradient_angle=45, palette=[[255,0,0,255], [0,0,255,255]])
```

## Workflows

### Create and apply a material

```python
manage_material(action="create", material_path="Assets/Materials/PlayerMaterial.mat", shader="Standard",
    properties={"_Color": [0.2, 0.5, 1.0, 1.0], "_Metallic": 0.5, "_Glossiness": 0.8})
manage_material(action="assign_material_to_renderer", target="Player",
    material_path="Assets/Materials/PlayerMaterial.mat", slot=0)
manage_camera(action="screenshot")  # verify visually
```

### Organize assets into folders

```python
batch_execute(commands=[
    {"tool": "manage_asset", "params": {"action": "create_folder", "path": "Assets/Prefabs"}},
    {"tool": "manage_asset", "params": {"action": "create_folder", "path": "Assets/Materials"}},
    {"tool": "manage_asset", "params": {"action": "create_folder", "path": "Assets/Textures"}},
])
manage_asset(action="move", path="Assets/MyMaterial.mat", destination="Assets/Materials/MyMaterial.mat")
```

### Search and process assets

```python
result = manage_asset(action="search", path="Assets", search_pattern="*.prefab", page_size=50, generate_preview=False)
for asset in result["assets"]:
    info = manage_prefabs(action="get_info", prefab_path=asset["path"])
    print(f"Prefab: {asset['path']}, Children: {info['childCount']}")
```

### Batch-spawn prefab instances

```python
batch_execute(commands=[
    {"tool": "manage_gameobject", "params": {"action": "create", "name": f"Enemy_{i}",
        "prefab_path": "Enemy", "position": [i * 3, 0, 0], "parent": "Enemies"}}
    for i in range(5)
])
```

## Companion skills

**unity-mcp-core** for the baseline workflow. **unity-mcp-scene-objects** for `manage_gameobject(action="create", prefab_path=...)` — actually placing a prefab instance in the scene. **unity-mcp-camera-graphics** for shaders tied to render pipeline effects (post-processing materials, renderer features).

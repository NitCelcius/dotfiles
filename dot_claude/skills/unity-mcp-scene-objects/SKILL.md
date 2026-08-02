---
name: unity-mcp-scene-objects
description: Use when creating, finding, modifying, or wiring GameObjects, Components, or Scenes through MCP for Unity — covers manage_scene, manage_gameobject, manage_components, find_gameobjects, scene hierarchy/screenshot actions, prefab instantiation into a scene, and cross-component reference wiring.
---

# Unity-MCP Scene & GameObject Tools

**REQUIRED BACKGROUND:** unity-mcp-core (editor-state checks, batch_execute, console verification).

## manage_scene

Scene CRUD, hierarchy queries, screenshots, scene view control.

```python
manage_scene(action="get_hierarchy", page_size=50, cursor=0, parent=None, include_transform=False)
manage_scene(action="get_active")
manage_scene(action="get_build_settings")
manage_scene(action="create", name="NewScene", path="Assets/Scenes/")
manage_scene(action="load", path="Assets/Scenes/Main.unity")
manage_scene(action="save")

# Screenshot with inline image
manage_scene(action="screenshot", camera="MainCamera", include_image=True, max_resolution=512)
# Batch surround (6-angle contact sheet) or orbit (configurable grid)
manage_scene(action="screenshot", batch="surround", view_target="Player", max_resolution=256)
manage_scene(action="screenshot", batch="orbit", view_target="Player", orbit_angles=8, orbit_elevations=[0, 30], max_resolution=256)
# Positioned screenshot (temp camera, no file saved)
manage_scene(action="screenshot", view_target="Enemy", view_position=[0, 10, -10], view_rotation=[45, 0, 0], max_resolution=512)
# Frame scene view on a target
manage_scene(action="scene_view_frame", scene_view_target="Player")
```

## find_gameobjects

Returns instance IDs only (paginated).

```python
find_gameobjects(
    search_term="Player", search_method="by_name",  # by_name|by_tag|by_layer|by_component|by_path|by_id
    include_inactive=False, page_size=50, cursor=0
)
# Returns: {"ids": [12345, 67890], "next_cursor": 50, ...}
```

## manage_gameobject

Create, modify, delete, duplicate GameObjects.

```python
# Create primitive
manage_gameobject(action="create", name="MyCube", primitive_type="Cube",
    position=[0, 1, 0], rotation=[0, 45, 0], scale=[1, 1, 1],
    components_to_add=["Rigidbody", "BoxCollider"])

# Instantiate a prefab into the scene (NOT manage_prefabs — see unity-mcp-assets-materials)
manage_gameobject(action="create", name="Enemy_1", prefab_path="Assets/Prefabs/Enemy.prefab",
    position=[5, 0, 3], parent="Enemies")
manage_gameobject(action="create", name="Enemy_2", prefab_path="Enemy", position=[10, 0, 3])  # smart lookup by name

# Modify
manage_gameobject(action="modify", target="Player", search_method="by_name",
    position=[10, 0, 0], rotation=[0, 90, 0], scale=[2, 2, 2], set_active=True, layer="Player",
    components_to_add=["AudioSource"], components_to_remove=["OldComponent"],
    component_properties={"Rigidbody": {"mass": 10.0, "useGravity": True}})

manage_gameobject(action="delete", target="OldObject")
manage_gameobject(action="duplicate", target="Player", new_name="Player2", offset=[5, 0, 0])
manage_gameobject(action="move_relative", target="Player", reference_object="Enemy",
    direction="left", distance=5.0, world_space=True)  # left|right|up|down|forward|back
manage_gameobject(action="look_at", target="MainCamera", look_at_target="Player", look_at_up=[0, 1, 0])
```

## manage_components

```python
manage_components(action="add", target=12345, component_type="Rigidbody", search_method="by_id")
manage_components(action="remove", target="Player", component_type="OldScript")
manage_components(action="set_property", target=12345, component_type="Rigidbody", property="mass", value=5.0)
manage_components(action="set_property", target=12345, component_type="Transform",
    properties={"position": [1, 2, 3], "localScale": [2, 2, 2]})

# Object reference property — reference another GameObject by name
manage_components(action="set_property", target="GameManager", component_type="GameManagerScript",
    property="targetObjects", value=[{"name": "Flower_1"}, {"name": "Flower_2"}, {"name": "Bee_1"}])
```

Object reference formats supported: `{"name": "ObjectName"}` (scene lookup), `{"instanceID": 12345}`, `{"guid": "abc123..."}`, `{"path": "Assets/..."}`, bare string as asset path or scene name shorthand, bare int as instanceID shorthand.

## Workflows

### Fresh scene before a generated build

**Always start a generated scene build with `manage_scene(action="create")`** for a clean empty scene — avoids "already exists" conflicts with default objects (Camera, Light) when your execution plan creates its own.

```python
manage_scene(action="create", name="MyGeneratedScene", path="Assets/Scenes/")
# Then proceed phased: Environment → Objects → Materials → ...
```

### Wiring object references between components

Use `{"name": "ObjectName"}` to wire cross-references after creating scripts/components:

```python
manage_components(action="set_property", target="BeeManager", component_type="BeeManagerScript",
    property="targetObjects", value=[{"name": "Flower_1"}, {"name": "Flower_2"}, {"name": "Flower_3"}])
```

### Trigger colliders need a Rigidbody

`OnTriggerEnter`/`OnTriggerStay`/`OnTriggerExit` fire only if **at least one** of the two colliding objects has a `Rigidbody`. Moving objects (bees, players) commonly need a kinematic one purely to satisfy this:

```python
batch_execute(commands=[
    {"tool": "manage_components", "params": {"action": "add", "target": "Bee_1", "component_type": "Rigidbody"}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "Bee_1",
        "component_type": "Rigidbody", "properties": {"useGravity": False, "isKinematic": True}}}
])
```

### Create a complete scene from scratch

```python
manage_scene(action="create", name="GameLevel", path="Assets/Scenes/")

batch_execute(commands=[
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "Ground", "primitive_type": "Plane",
        "position": [0, 0, 0], "scale": [10, 1, 10]}},
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "Light", "primitive_type": "Cube"}},
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "Player", "primitive_type": "Capsule",
        "position": [0, 1, 0]}}
])

# Convert the "Light" cube into an actual directional light
manage_components(action="remove", target="Light", component_type="MeshRenderer")
manage_components(action="remove", target="Light", component_type="MeshFilter")
manage_components(action="remove", target="Light", component_type="BoxCollider")
manage_components(action="add", target="Light", component_type="Light")
manage_components(action="set_property", target="Light", component_type="Light", property="type", value="Directional")

manage_gameobject(action="modify", target="Main Camera", position=[0, 5, -10], rotation=[30, 0, 0])
manage_camera(action="screenshot")
manage_scene(action="save")
```

### Populate a grid or clone a template

```python
# Grid of objects via batch (chunks of 25)
commands = [{"tool": "manage_gameobject", "params": {"action": "create", "name": f"Cube_{x}_{z}",
    "primitive_type": "Cube", "position": [x * 2, 0, z * 2]}} for x in range(5) for z in range(5)]
batch_execute(commands=commands[:25], parallel=True)

# Clone a template in a line
template_id = find_gameobjects(search_term="Template", search_method="by_name")["ids"][0]
for i in range(10):
    manage_gameobject(action="duplicate", target=template_id, new_name=f"Instance_{i}", offset=[i * 2, 0, 0])
```

## Companion skills

**unity-mcp-core** for the baseline workflow. **unity-mcp-scripting** for attaching/wiring a script you're creating alongside these GameObjects. **unity-mcp-assets-materials** for `manage_prefabs` (headless prefab editing, as opposed to instantiating one here). **unity-mcp-packages-docs** for `manage_physics` (rigidbody/joint/raycast details beyond basic trigger setup).

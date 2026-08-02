---
name: unity-mcp-packages-docs
description: Use when installing/managing Unity packages, configuring physics (settings, collision matrix, materials, joints, raycasts, rigidbodies), or verifying Unity C# APIs / fetching documentation through MCP for Unity — covers manage_packages, manage_physics, unity_reflect, and unity_docs.
---

# Unity-MCP Package, Physics & Docs Tools

**REQUIRED BACKGROUND:** unity-mcp-core (batch_execute, console checks).

## manage_packages

Install triggers domain reload. Query actions return immediately or async (`job_id`); mutating actions are async.

**Query:** `list_packages`, `search_packages` (`query`), `get_package_info` (`package`), `list_registries`, `ping`, `status` (`job_id` — omit to poll the latest add/remove/embed job).
**Mutating:** `add_package` (`package`: name, name@version, git URL, or file: path), `remove_package` (`package`, `force`), `embed_package`, `resolve_packages`, `add_registry` (`name`,`url`,`scopes`), `remove_registry`.

Invalid names (uppercase, missing dots) are rejected outright. Git URLs and `file:` paths are allowed but return a trust warning.

```python
manage_packages(action="list_packages")
manage_packages(action="status", job_id="<job_id>")

manage_packages(action="add_package", package="com.unity.inputsystem")
manage_packages(action="status", job_id="<job_id>")

# Blocked removal shows dependents; force overrides
manage_packages(action="remove_package", package="com.unity.modules.ui")
manage_packages(action="remove_package", package="com.unity.modules.ui", force=True)

manage_packages(action="add_registry", name="OpenUPM", url="https://package.openupm.com",
    scopes=["com.cysharp", "com.neuecc"])
```

### Add scoped registry then install from it

```python
manage_packages(action="add_registry", name="OpenUPM", url="https://package.openupm.com", scopes=["com.cysharp"])
manage_packages(action="resolve_packages")  # force resolution to pick up new registry
manage_packages(action="add_package", package="com.cysharp.unitask")
manage_packages(action="status", job_id="<job_id>")
```

### Package deployment loop (edit → deploy → test)

`deploy_package` (in `manage_editor`, unity-mcp-testing-editor) copies local MCPForUnity source into the installed package location, bypassing the UI dialog, and auto-triggers recompilation.

```python
# 1. Make code changes (script_apply_edits / create_script)
# 2. Deploy
manage_editor(action="deploy_package")
# 3. Wait for recompilation
refresh_unity(mode="force", compile="request", wait_for_ready=True)
# 4. Check errors, then test
read_console(types=["error"], count=10, include_stacktrace=True)
run_tests(mode="EditMode")

# Rollback after a failed deploy
manage_editor(action="restore_package")
refresh_unity(mode="force", compile="request", wait_for_ready=True)
```

## manage_physics

3D and 2D physics: settings, collision matrix, materials, joints, queries, rigidbody config, validation, edit-mode simulation. Most actions take `dimension="3d"` (default) or `dimension="2d"`.

**Action groups:** Settings (`ping`, `get_settings`, `set_settings`) · Collision Matrix (`get_collision_matrix`, `set_collision_matrix`) · Materials (`create_physics_material`, `configure_physics_material`, `assign_physics_material`) · Joints (`add_joint`, `configure_joint`, `remove_joint`) · Queries (`raycast`, `raycast_all`, `linecast`, `shapecast`, `overlap`) · Forces (`apply_force`) · Rigidbody (`get_rigidbody`, `configure_rigidbody`) · Validation (`validate`) · Simulation (`simulate_step`).

```python
manage_physics(action="ping")
manage_physics(action="set_settings", dimension="3d", settings={"gravity": [0, -20, 0]})
manage_physics(action="set_collision_matrix", layer_a="Player", layer_b="Enemy", collide=False)

manage_physics(action="create_physics_material", name="Bouncy", bounciness=0.9, dynamic_friction=0.2)
manage_physics(action="assign_physics_material", target="Ball",
    material_path="Assets/Physics Materials/Bouncy.physicMaterial")

manage_physics(action="add_joint", target="Door", joint_type="hinge", connected_body="DoorFrame")
manage_physics(action="configure_joint", target="Door", joint_type="hinge",
    motor={"targetVelocity": 90, "force": 100}, limits={"min": -90, "max": 0, "bounciness": 0})

manage_physics(action="raycast", origin=[0, 10, 0], direction=[0, -1, 0], max_distance=50)
manage_physics(action="raycast_all", origin=[0, 10, 0], direction=[0, -1, 0])  # all hits, sorted by distance
manage_physics(action="linecast", start=[0, 0, 0], end=[10, 0, 0])
manage_physics(action="shapecast", shape="sphere", origin=[0, 5, 0], direction=[0, -1, 0], size=0.5)
manage_physics(action="overlap", shape="sphere", position=[0, 0, 0], size=5.0)

manage_physics(action="apply_force", target="Ball", force=[0, 500, 0], force_mode="Impulse")
manage_physics(action="apply_force", target="Crate", force_type="explosion",
    explosion_force=1000, explosion_position=[0, 0, 0], explosion_radius=10)

manage_physics(action="configure_rigidbody", target="Player",
    properties={"mass": 80, "drag": 0.5, "useGravity": True, "collisionDetectionMode": "Continuous"})

manage_physics(action="validate")                    # whole scene
manage_physics(action="validate", target="Player")   # single object
manage_physics(action="simulate_step", steps=10, step_size=0.02)  # edit-mode preview
```

`joint_type` values — 3D: `fixed`, `hinge`, `spring`, `character`, `configurable`. 2D: `distance`, `fixed`, `friction`, `hinge`, `relative`, `slider`, `spring`, `target`, `wheel`. `force_mode` — 3D: `Force`/`Impulse`/`Acceleration`/`VelocityChange`; 2D: `Force`/`Impulse`. `friction_combine`/`bounce_combine`: `Average`/`Minimum`/`Multiply`/`Maximum`.

## unity_reflect

Inspect Unity's live C# API via reflection. **Always use before writing C# code that references Unity APIs** — LLM training data frequently contains incorrect, outdated, or hallucinated APIs. Requires Unity connection.

```python
unity_reflect(action="search", query="NavMesh", scope="all")           # scope: unity|packages|project|all
unity_reflect(action="get_type", class_name="UnityEngine.AI.NavMeshAgent")
unity_reflect(action="get_member", class_name="Physics", member_name="Raycast")
```

## unity_docs

Fetch official docs.unity3d.com content. No Unity connection needed except `lookup` with asset-related queries (searches project assets too). Use after `unity_reflect` confirms a type exists. **Trust hierarchy: reflection (live runtime) > project assets > official docs.**

```python
unity_docs(action="get_doc", class_name="Physics", member_name="Raycast")
unity_docs(action="get_manual", slug="execution-order")
unity_docs(action="get_package_doc", package="com.unity.render-pipelines.universal", page="2d-index", pkg_version="17.0")
unity_docs(action="lookup", query="Physics.Raycast")                     # parallel search across all sources
unity_docs(action="lookup", queries="Physics.Raycast,NavMeshAgent,Light2D")  # batch
```

### Full API verification before writing code

```python
unity_reflect(action="search", query="NavMesh")
unity_reflect(action="get_type", class_name="UnityEngine.AI.NavMeshAgent")
unity_reflect(action="get_member", class_name="NavMeshAgent", member_name="SetDestination")
unity_docs(action="get_doc", class_name="NavMeshAgent", member_name="SetDestination")
```

## Companion skills

**unity-mcp-core** for the baseline workflow. **unity-mcp-testing-editor** for `manage_editor(action="deploy_package"/"restore_package")` itself. **unity-mcp-scene-objects** for the rigidbody/trigger setup that `manage_physics` configures further.

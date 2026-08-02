---
name: unity-mcp-camera-graphics
description: Use when configuring Unity cameras, Cinemachine, rendering/post-processing, ProBuilder mesh geometry, or the Profiler through MCP for Unity — covers manage_camera, manage_graphics (volumes, light baking, pipeline, URP renderer features), manage_probuilder (mesh editing), and manage_profiler.
---

# Unity-MCP Camera, Graphics, ProBuilder & Profiler Tools

**REQUIRED BACKGROUND:** unity-mcp-core (batch_execute, console checks, screenshot verification).

## manage_camera

Unified Camera + Cinemachine management. Works with plain Unity Camera; unlocks presets/pipelines/blending when `com.unity.cinemachine` is installed. `ping` checks availability.

**Tier system:** Tier 1 (`ping`, `create_camera`, `set_target`, `set_lens`, `set_priority`, `list_cameras`, `screenshot`, `screenshot_multiview`) works without Cinemachine. Tier 2 (`ensure_brain`, `get_brain_status`, `set_body`, `set_aim`, `set_noise`, `add/remove_extension`, `set_blend`, `force_camera`, `release_override`) requires Cinemachine and errors with a fallback suggestion otherwise.

```python
manage_camera(action="ping")
manage_camera(action="create_camera", properties={"name": "FollowCam", "preset": "third_person",
    "follow": "Player", "lookAt": "Player", "priority": 20})
    # presets: follow, third_person, freelook, dolly, static, top_down, side_scroller
manage_camera(action="ensure_brain")  # ensure CinemachineBrain exists on main camera
manage_camera(action="set_body", target="FollowCam", properties={"bodyType": "CinemachineThirdPersonFollow",
    "cameraDistance": 5.0, "shoulderOffset": [0.5, 0.5, 0]})
manage_camera(action="set_aim", target="FollowCam", properties={"aimType": "CinemachineRotationComposer"})
manage_camera(action="set_noise", target="FollowCam", properties={"amplitudeGain": 0.5, "frequencyGain": 1.0})
manage_camera(action="set_priority", target="FollowCam", properties={"priority": 50})
manage_camera(action="force_camera", target="CinematicCam")   # override Brain selection
manage_camera(action="release_override")                       # return to priority-based selection
manage_camera(action="set_blend", properties={"style": "EaseInOut", "duration": 2.0})
manage_camera(action="add_extension", target="FollowCam", properties={"extensionType": "CinemachineDeoccluder"})
manage_camera(action="list_cameras")
```

Screenshots: `screenshot` (supports `capture_source="game_view"`|`"scene_view"`, `view_target`, `view_position`/`view_rotation`, `batch="surround"`|`"orbit"`, `include_image`, `max_resolution`) and `screenshot_multiview` (shorthand for surround + inline image). scene_view does not support batch/view_position/view_rotation/camera selection — use game_view for those.

**Resource:** `mcpforunity://scene/cameras` for current camera state before modifying.

### Third-person camera setup

```python
manage_camera(action="ping")
manage_camera(action="ensure_brain")
manage_camera(action="create_camera", properties={"name": "FollowCam", "preset": "third_person",
    "follow": "Player", "lookAt": "Player", "priority": 20})
manage_camera(action="set_body", target="FollowCam", properties={"cameraDistance": 5.0, "shoulderOffset": [0.5, 0.5, 0]})
manage_camera(action="set_noise", target="FollowCam", properties={"amplitudeGain": 0.3, "frequencyGain": 0.8})
manage_camera(action="screenshot", camera="FollowCam", include_image=True, max_resolution=512)  # verify
```

## manage_graphics

Rendering/post-processing: volumes, light baking, rendering stats, pipeline config, URP renderer features. Requires URP/HDRP for volume/feature actions. `ping` checks pipeline status.

**Volume** (URP/HDRP): `volume_create`, `volume_add_effect`, `volume_set_effect`, `volume_remove_effect`, `volume_get_info`, `volume_set_properties`, `volume_list_effects`, `volume_create_profile`.
**Bake** (Edit mode only — fails in Play mode): `bake_start`/`bake_cancel`/`bake_status`/`bake_clear`, `bake_reflection_probe`, `bake_get_settings`/`bake_set_settings`, `bake_create_light_probe_group`, `bake_create_reflection_probe`, `bake_set_probe_positions`.
**Stats:** `stats_get`, `stats_list_counters`, `stats_set_scene_debug`, `stats_get_memory`.
**Pipeline:** `pipeline_get_info`, `pipeline_set_quality`, `pipeline_get_settings`/`pipeline_set_settings`.
**Features** (URP only — errors on HDRP/Built-in): `feature_list`, `feature_add`, `feature_remove`, `feature_configure`, `feature_toggle`, `feature_reorder`.

```python
manage_graphics(action="ping")
manage_graphics(action="volume_create", name="PostProcessing", is_global=True, effects=[
    {"type": "Bloom", "parameters": {"intensity": 1.5, "threshold": 0.9}},
    {"type": "Vignette", "parameters": {"intensity": 0.4}},
])
manage_graphics(action="volume_list_effects")  # discover available effect types for active pipeline
manage_graphics(action="bake_create_light_probe_group", name="ProbeGrid", position=[0, 1, 0], grid_size=[3, 2, 3], spacing=2.0)
manage_graphics(action="bake_start", async_bake=True)
manage_graphics(action="bake_status")  # poll until complete
manage_graphics(action="stats_get")
manage_graphics(action="pipeline_set_quality", level="High")
manage_graphics(action="feature_add", feature_type="FullScreenPassRendererFeature", name="NightVision",
    material="Assets/Materials/NightVision.mat")
```

**Resources:** `mcpforunity://scene/volumes`, `mcpforunity://rendering/stats`, `mcpforunity://pipeline/renderer-features`.

### Post-processing + light baking workflow

```python
manage_graphics(action="ping")
manage_graphics(action="volume_create", name="GlobalPostProcess", is_global=True, effects=[
    {"type": "Bloom", "parameters": {"intensity": 1.0, "threshold": 0.9, "scatter": 0.7}},
    {"type": "Vignette", "parameters": {"intensity": 0.35}},
])
manage_camera(action="screenshot", include_image=True, max_resolution=512)  # verify visually

# Baking: mark lights Mixed/Baked, mark static geo, configure, place probes, bake, poll
manage_components(action="set_property", target="Directional Light", component_type="Light",
    properties={"lightmapBakeType": 1})  # 1 = Mixed
manage_graphics(action="bake_set_settings", settings={"lightmapper": 1, "directSamples": 32,
    "indirectSamples": 128, "maxBounces": 4, "lightmapResolution": 40})
manage_graphics(action="bake_create_reflection_probe", name="RoomReflection", position=[0, 2, 0],
    size=[8, 4, 8], resolution=256, hdr=True, box_projection=True)
manage_graphics(action="bake_start", async_bake=True)
manage_graphics(action="bake_status")  # repeat until complete
```

## manage_probuilder

Requires `com.unity.probuilder`. **When installed, prefer ProBuilder over primitive GameObjects** for editable geometry, multi-material faces, or complex shapes.

**Shape creation:** `create_shape` (12 types: Cube, Cylinder, Sphere, Plane, Cone, Torus, Pipe, Arch, Stair, CurvedStair, Door, Prism), `create_poly_shape` (from 2D footprint).
**Mesh editing:** `extrude_faces`/`extrude_edges`, `bevel_edges`, `subdivide`, `delete_faces`, `bridge_edges`, `connect_elements`, `detach_faces`, `flip_normals`, `merge_faces`, `combine_meshes`/`merge_objects`, `duplicate_and_flip`, `create_polygon`.
**Vertex ops:** `merge_vertices`, `weld_vertices`, `split_vertices`, `move_vertices`, `insert_vertex`, `append_vertices_to_edge`.
**Selection/UV/Materials:** `select_faces`, `set_face_material`, `set_face_color`, `set_face_uvs`.
**Query:** `get_mesh_info` (include: `"summary"`|`"faces"`|`"edges"`|`"all"`), `ping`.
**Smoothing:** `set_smoothing`, `auto_smooth`.
**Utilities:** `center_pivot`, `freeze_transform`, `validate_mesh`, `repair_mesh`.
**Known broken:** `set_pivot` (vertex positions don't persist through rebuild — use `center_pivot` instead), `convert_to_probuilder` (MeshImporter throws — create shapes natively instead).

```python
manage_probuilder(action="ping")
manage_probuilder(action="create_shape", properties={"shape_type": "Cube", "name": "MyCube"})
info = manage_probuilder(action="get_mesh_info", target="MyCube", properties={"include": "faces"})
manage_probuilder(action="extrude_faces", target="MyCube", properties={"faceIndices": [2], "distance": 1.5})
manage_probuilder(action="select_faces", target="MyCube", properties={"direction": "up", "tolerance": 0.7})
manage_probuilder(action="set_face_material", target="Floor", properties={"faceIndices": [0], "materialPath": "Assets/Materials/Stone.mat"})
manage_probuilder(action="auto_smooth", target="MyCube", properties={"angleThreshold": 30})
manage_probuilder(action="center_pivot", target="MyCube")
manage_probuilder(action="validate_mesh", target="MyCube")
```

**Edit-verify loop — face/edge/vertex indices shift after every edit. Never reuse indices across edits without re-querying:**

```python
# WRONG
manage_probuilder(action="subdivide", target="Obj", properties={"faceIndices": [2]})
manage_probuilder(action="delete_faces", target="Obj", properties={"faceIndices": [5]})  # index may now be wrong

# RIGHT — re-query after each structural edit
manage_probuilder(action="subdivide", target="Obj", properties={"faceIndices": [2]})
info = manage_probuilder(action="get_mesh_info", target="Obj", properties={"include": "faces"})
# find the correct face by direction/center, then act on it
manage_probuilder(action="delete_faces", target="Obj", properties={"faceIndices": [correct_index]})
```

## manage_profiler

Profiler session control, counters, memory snapshots, Frame Debugger. Group: `profiling` (opt-in via `manage_tools`).

**Session:** `profiler_start`/`profiler_stop`/`profiler_status`, `profiler_set_areas`.
**Counters:** `get_frame_timing`, `get_counters` (category: `Render`/`Scripts`/`Memory`/`Physics`), `get_object_memory`.
**Memory Snapshot** (requires `com.unity.memoryprofiler`): `memory_take_snapshot`, `memory_list_snapshots`, `memory_compare_snapshots`.
**Frame Debugger:** `frame_debugger_enable`/`frame_debugger_disable`, `frame_debugger_get_events`.

```python
manage_profiler(action="ping")
manage_profiler(action="profiler_start")
manage_profiler(action="profiler_set_areas", areas={"CPU": True, "GPU": True, "Rendering": True, "Memory": False})
manage_profiler(action="get_counters", category="Memory", counters=["Total Used Memory", "GC Used Memory"])
manage_profiler(action="memory_take_snapshot", snapshot_path="Assets/Snapshots/baseline.snap")
manage_profiler(action="memory_compare_snapshots", snapshot_a="Assets/Snapshots/before.snap", snapshot_b="Assets/Snapshots/after.snap")
```

## Companion skills

**unity-mcp-core** for the baseline workflow. **unity-mcp-assets-materials** for creating the materials referenced by renderer features/ProBuilder faces. **unity-mcp-scene-objects** for GameObject-level camera/light targets these tools act on.

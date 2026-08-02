---
name: unity-mcp-ui
description: Use when building or editing Unity UI through MCP for Unity — either UI Toolkit (UXML/USS via manage_ui) or uGUI/Canvas-based UI (Canvas, Button, Text, Slider, Toggle, Input Field, EventSystem, RectTransform via manage_gameobject/manage_components). Also covers choosing between the old and new Input System for EventSystem wiring.
---

# Unity-MCP UI Tools

**REQUIRED BACKGROUND:** unity-mcp-core (batch_execute, console checks).

Unity has two UI systems: **UI Toolkit** (modern, preferred for new UI — `manage_ui`) and **uGUI** (Canvas-based, legacy but still common in existing projects — `batch_execute` with `manage_gameobject`/`manage_components`).

## Step 0: detect project UI capabilities — always do this first

```python
# Read mcpforunity://project/info
```

| field | value | use |
|---|---|---|
| `packages.uiToolkit` | `true` (always, Unity 2021.3+) | **Preferred:** `manage_ui` for UXML/USS |
| `packages.ugui` | `true` | Canvas-based UI via `batch_execute` |
| `packages.textmeshpro` | `true` | `TextMeshProUGUI` for text (uGUI) |
| `packages.textmeshpro` | `false` | `UnityEngine.UI.Text` (legacy, lower quality) |
| `activeInputHandler` | `"Old"` | `StandaloneInputModule` for EventSystem |
| `activeInputHandler` | `"New"` | `InputSystemUIInputModule` for EventSystem |
| `activeInputHandler` | `"Both"` | Either works; prefer `InputSystemUIInputModule` |

## UI Toolkit (manage_ui)

Web-like model: UXML (structure, like HTML) + USS (styling, like CSS).

**Always use `<ui:Style>` with the `ui:` namespace prefix, never bare `<Style>`** — UI Builder fails to open files with the unprefixed form.

```python
manage_ui(action="create", path="Assets/UI/MainMenu.uxml", contents='''<ui:UXML xmlns:ui="UnityEngine.UIElements">
    <ui:Style src="Assets/UI/MainMenu.uss" />
    <ui:VisualElement name="root" class="root-container">
        <ui:Label text="My Game" class="title" />
        <ui:Button text="Play" name="play-btn" class="menu-button" />
    </ui:VisualElement>
</ui:UXML>''')

manage_ui(action="create", path="Assets/UI/MainMenu.uss", contents='''.root-container {
    flex-grow: 1; justify-content: center; align-items: center; background-color: rgba(0, 0, 0, 0.8);
}
.title { font-size: 48px; color: white; -unity-font-style: bold; margin-bottom: 40px; }
.menu-button { width: 300px; height: 60px; font-size: 24px; margin: 8px;
    background-color: rgb(50, 120, 200); color: white; border-radius: 8px; }
.menu-button:hover { background-color: rgb(70, 140, 220); }''')

manage_gameobject(action="create", name="UIRoot")
manage_ui(action="attach_ui_document", target="UIRoot", source_asset="Assets/UI/MainMenu.uxml")
    # panel_settings auto-created if omitted; pass panel_settings="Assets/UI/Panel.asset" for a specific one

manage_ui(action="get_visual_tree", target="UIRoot", max_depth=5)  # verify the result

# Update existing file
manage_ui(action="update", path="Assets/UI/MainMenu.uss", contents=".title { font-size: 64px; color: yellow; }")

# Custom PanelSettings (e.g. for ScaleWithScreenSize)
manage_ui(action="create_panel_settings", path="Assets/UI/GamePanelSettings.asset",
    scale_mode="ScaleWithScreenSize", reference_resolution={"width": 1920, "height": 1080})
```

`manage_ui(action="read", path=...)` returns `{"success": true, "data": {"contents": "...", "path": "..."}}`.

## uGUI (Canvas-based)

### RectTransform sizing — critical for every UI child

Every GameObject under a Canvas gets a `RectTransform` instead of `Transform`. **Without setting anchor/size, elements default to zero size and won't be visible.**

```python
# Stretch to fill parent
{"anchorMin": [0, 0], "anchorMax": [1, 1], "sizeDelta": [0, 0], "anchoredPosition": [0, 0]}
# Fixed-size centered element (e.g. 300x50 button)
{"anchorMin": [0.5, 0.5], "anchorMax": [0.5, 0.5], "sizeDelta": [300, 50], "anchoredPosition": [0, 0]}
# Top-anchored bar, full width, 60px tall
{"anchorMin": [0, 1], "anchorMax": [1, 1], "sizeDelta": [0, 60], "anchoredPosition": [0, -30]}
```
Set via `manage_components(action="set_property", target=..., component_type="RectTransform", properties={...})`. Vector2 properties accept both `[x, y]` array and `{"x": ..., "y": ...}` object form.

### Complete worked example: Main Menu Screen

Canvas + EventSystem + Panel + Title + 3 Buttons, in two `batch_execute` calls (default limit 25 commands/batch, configurable up to 100). Assumes `project_info` has been read and `activeInputHandler` is known (this example uses `"Old"` — swap `StandaloneInputModule` for `InputSystemUIInputModule` if `"New"`/`"Both"`).

```python
batch_execute(fail_fast=True, commands=[
    # Canvas (Canvas + CanvasScaler + GraphicRaycaster is the required trio)
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "MenuCanvas"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "MenuCanvas", "component_type": "Canvas"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "MenuCanvas", "component_type": "CanvasScaler"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "MenuCanvas", "component_type": "GraphicRaycaster"}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "MenuCanvas", "component_type": "Canvas", "property": "renderMode", "value": 0}},  # 0=ScreenSpaceOverlay
    {"tool": "manage_components", "params": {"action": "set_property", "target": "MenuCanvas", "component_type": "CanvasScaler", "properties": {"uiScaleMode": 1, "referenceResolution": [1920, 1080]}}},  # 1=ScaleWithScreenSize
    # EventSystem — one per scene, required for any interaction
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "EventSystem"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "EventSystem", "component_type": "UnityEngine.EventSystems.EventSystem"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "EventSystem", "component_type": "UnityEngine.EventSystems.StandaloneInputModule"}},
    # Panel (centered, 60% width) with VerticalLayoutGroup so children below need no manual RectTransform
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "MenuPanel", "parent": "MenuCanvas"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "MenuPanel", "component_type": "Image"}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "MenuPanel", "component_type": "Image", "property": "color", "value": [0.1, 0.1, 0.15, 0.9]}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "MenuPanel", "component_type": "RectTransform", "properties": {"anchorMin": [0.2, 0.15], "anchorMax": [0.8, 0.85], "sizeDelta": [0, 0]}}},
    {"tool": "manage_components", "params": {"action": "add", "target": "MenuPanel", "component_type": "VerticalLayoutGroup"}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "MenuPanel", "component_type": "VerticalLayoutGroup", "properties": {"spacing": 20, "childAlignment": 4, "childForceExpandWidth": True, "childForceExpandHeight": False}}},  # 4=MiddleCenter
    # Title
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "Title", "parent": "MenuPanel"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "Title", "component_type": "TextMeshProUGUI"}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "Title", "component_type": "TextMeshProUGUI", "properties": {"text": "My Game", "fontSize": 64, "alignment": 514, "color": [1, 1, 1, 1]}}},  # 514=MiddleCenter
])

batch_execute(fail_fast=True, commands=[
    # Button = Image (visual) + Button (click handler) on parent, + child with TextMeshProUGUI label
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "PlayButton", "parent": "MenuPanel"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "PlayButton", "component_type": "Image"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "PlayButton", "component_type": "Button"}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "PlayButton", "component_type": "Image", "property": "color", "value": [0.2, 0.6, 1.0, 1.0]}},
    {"tool": "manage_gameobject", "params": {"action": "create", "name": "PlayLabel", "parent": "PlayButton"}},
    {"tool": "manage_components", "params": {"action": "add", "target": "PlayLabel", "component_type": "TextMeshProUGUI"}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "PlayLabel", "component_type": "TextMeshProUGUI", "properties": {"text": "Play", "fontSize": 32, "alignment": 514}}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "PlayLabel", "component_type": "RectTransform", "properties": {"anchorMin": [0, 0], "anchorMax": [1, 1], "sizeDelta": [0, 0]}}},
    # (repeat the same PlayButton pattern for Settings/Quit — same 8-command shape, different name/color/text)
])
```

TextMeshPro `alignment` values: 257=TopLeft, 258=TopCenter, 260=TopRight, 513=MiddleLeft, 514=MiddleCenter, 516=MiddleRight, 1025=BottomLeft, 1026=BottomCenter, 1028=BottomRight. `childAlignment`: 0=UpperLeft..4=MiddleCenter..8=LowerRight (row-major). `ContentSizeFitter` fit modes: 0=Unconstrained, 1=MinSize, 2=PreferredSize.

### uGUI component quick reference

Every element below follows the same pattern as the worked example: create GameObject(s) → add components → set RectTransform → **wire any reference marked critical**, since unwired components silently fail to function (no error, just dead interaction).

| Element | Required components | Wiring |
|---|---|---|
| **Canvas** | Canvas + CanvasScaler + GraphicRaycaster | — (root for all UI, one per screen) |
| **EventSystem** | EventSystem + input module | — (one per scene, see Input System below) |
| **Panel** | Image + RectTransform | — |
| **Text** | TextMeshProUGUI (or Text if no TMP) + RectTransform | — |
| **Button** | Image + Button + child(TextMeshProUGUI) | — |
| **Slider** | Slider + Image + Background/FillArea/Fill/HandleArea/Handle child hierarchy | **CRITICAL:** wire `Slider.fillRect` → Fill image, `Slider.handleRect` → Handle image |
| **Toggle** | Toggle + Background/Checkmark/Label children | **CRITICAL:** wire `Toggle.graphic` → Checkmark image |
| **Input Field** | Image + TMP_InputField + TextArea/Placeholder/Text children | **CRITICAL:** wire `textViewport`, `textComponent`, `placeholder` |
| **Layout Group** | VerticalLayoutGroup / HorizontalLayoutGroup / GridLayoutGroup | Auto-arranges children — skip manual RectTransform on children |

Wiring example (Slider — same `set_property` pattern applies to Toggle/Input Field):
```python
batch_execute(fail_fast=True, commands=[
    {"tool": "manage_components", "params": {"action": "set_property", "target": "HealthSlider",
        "component_type": "Slider", "property": "fillRect", "value": {"name": "SliderFill"}}},
    {"tool": "manage_components", "params": {"action": "set_property", "target": "HealthSlider",
        "component_type": "Slider", "property": "handleRect", "value": {"name": "SliderHandle"}}},
])
```

## Input System: old vs new

**Always check `project_info.activeInputHandler` before creating an EventSystem or writing input code** — adding `StandaloneInputModule` when `activeInputHandler` is `"New"` causes a runtime error.

```python
# "Old": StandaloneInputModule, reads Input.GetAxis()/GetButton()/GetKeyDown()
{"tool": "manage_components", "params": {"action": "add", "target": "EventSystem",
    "component_type": "UnityEngine.EventSystems.StandaloneInputModule"}}

# "New" or "Both": InputSystemUIInputModule (com.unity.inputsystem package)
{"tool": "manage_components", "params": {"action": "add", "target": "EventSystem",
    "component_type": "UnityEngine.InputSystem.UI.InputSystemUIInputModule"}}
```

Script-side, old style reads `Input.GetAxis("Horizontal")` / `Input.GetKeyDown(KeyCode.Space)` directly in `Update()`. New style implements `OnMove(InputValue value)` / `OnJump(InputValue value)` callbacks invoked by a `PlayerInput` component, reading `value.Get<Vector2>()` / `value.isPressed`. When `activeInputHandler` is `"Both"`, both work simultaneously for gameplay scripts, but UI should still prefer `InputSystemUIInputModule`.

## Companion skills

**unity-mcp-core** for the baseline workflow. **unity-mcp-scripting** for the script backing a button's `onClick` handler or a custom input callback. **unity-mcp-scene-objects** for `manage_components` details beyond UI-specific wiring.

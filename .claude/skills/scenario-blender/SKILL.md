---
name: scenario-blender
description: Drive Blender through the Scenario for Blender extension (scenario-labs/blender-plugin) and its local `scenario-blender` MCP server — inspect the open scene, generate images, video, 3D meshes, PBR materials, audio and 360 environments with Scenario, build Blockout greybox layouts, plan camera moves and import results into the scene. Use when the user mentions Scenario, Blender generation, the scenario-blender MCP server, or asks to install/connect the Blender plugin.
---

# Scenario for Blender

Source: https://github.com/scenario-labs/blender-plugin (GPL-3.0-or-later, experimental).
Requires Blender 5.0+, a Scenario API key + secret, and internet access.

## 1. Install the extension (on the user's machine)

Preferred (gets updates):
1. Blender > Edit > Preferences > System > Network: turn on **Allow Online Access**.
2. Preferences > Get Extensions > Repositories > **Add Remote Repository**:
   `https://blender.scenario.com/repo/index.json`
3. Find **Scenario** in Get Extensions and install it.
4. In Scenario web app: Organization settings > API Keys > Add API Key.
5. Preferences > Add-ons > Scenario: paste key + secret, press **Test connection**,
   choose an Output Folder.

Alternative: download `scenario-<version>.zip` from the GitHub releases page, keep it
zipped, then Get Extensions > **Install from Disk** (no auto-updates). Never keep both
a ZIP copy and a repository copy installed.

From a source checkout (developers, needs `uv` and Blender on PATH or `BLENDER=`):
`make sync && make build && make install`.

## 2. Connect the MCP server

The extension runs a local MCP server at `http://127.0.0.1:9876/mcp` (HTTP POST,
no SSE) whenever Blender's Online Access is on. Port is the **MCP Port** preference.

- Claude Code: `claude mcp add --transport http scenario-blender http://127.0.0.1:9876/mcp`
  (or the project `.mcp.json` entry), or press **Connect** in Scenario > Agents (MCP).
- Headless: `blender --background scene.blend --online-mode --command scenario_blender --port 9876`
- Check: `curl -sS -X POST http://127.0.0.1:9876/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`

The server must run on the same machine as the agent (loopback only); a cloud
agent cannot reach the user's Blender. If tools are missing, ask the user to open
Blender, enable Online Access, and check Scenario > Agents (MCP) for status.

## 3. Working rules

- **Look before acting**: start with `scene_summary`, `object_detail`,
  `datablocks_summary`; use `capture_views` or `screenshot_viewport` to see results.
- **Money**: generations spend Creative Units (CU). Always:
  `list_models` → `model_schema` → `estimate_cost` (free dry run, returns `quote_id`
  and exact cost) → show the exact cost to the user and get explicit approval →
  `generate` with that `quote_id` and the unchanged `approved_cost` string.
  Same pattern for `estimate_prompt`/`approve_prompt`, `estimate_blockout`/`approve_blockout`,
  `estimate_workflow`/`run_workflow`, `estimate_film_task`/`approve_film_task`.
- **Never retry an uncertain paid submission.** Inspect `list_local_jobs` /
  `job_status` and use `recover_local_job` instead.
- **Waiting**: `wait_for_job` (Blender stays responsive), then `job_status`.
- **Applying results is two-step**: `prepare_result_application` (purpose: import,
  material, world, mesh_edit, video_first_frame, …) → confirm with the user →
  `apply_result_application`. `import_result` does not import directly.
- **References**: `capture_reference` (VIEWPORT, CAMERA, *_CLIP, MESH) or
  `upload_reference` for an explicit file; poll `reference_upload_status`.
  File parameters in `generate` take Scenario asset ids.
- **Destructive tools** (`apply_*`, `decide_workflow_step`, `recover_*`,
  `cancel_prepared_job`) need the user's explicit go-ahead.
- `execute_python` is off by default; only use it if the user enabled it in
  preferences. Prefer `blender_api_help` before writing bpy code.

## 4. Lane cheat sheet

| Goal | Tools |
| --- | --- |
| Image / texture | `list_models(lane="image")` → estimate → `generate` |
| Render Image / Video from scene | `render_form` (inspect/configure/prepare), `camera_path`, `capture_reference` → estimate → `generate` |
| 3D mesh / mesh edit | lane 3D → `generate` → `prepare_result_application(purpose="import"/"mesh_edit")` |
| PBR material | materials lane → `prepare_result_application(purpose="material")` |
| 360 environment / HDRI | environment lane → `prepare_result_application(purpose="world")` |
| Greybox from text | `estimate_blockout(action="DESIGN")` → `approve_blockout` → `prepare_blockout_plan` → `apply_blockout_plan` (then native **Build plan**) |
| Library | `list_assets`, `search_assets`, `list_collections`, `prepare_asset_organization` → `apply_asset_organization` |
| Workflows | `list_workflows` → `workflow_schema` → `estimate_workflow` → `run_workflow` |
| Film (JSON recipe → shots → timeline → MP4) | `film_recipe` then the `prepare_film_*` / `build_film_*` / `render_film_export` tools |

Full contract: `docs/MCP.md` in the plugin repo, or `tools/list` on the server.
For platform-wide tasks (training, usage) without Blender, use the hosted
https://mcp.scenario.com server instead.

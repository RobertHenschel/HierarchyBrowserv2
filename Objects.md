### Objects

Concise reference for the object model used by the providers and browser. Research Computing objects are authored under `providers/ResearchComputingAtIU/Objects/`. Slurm objects are produced dynamically by the Slurm provider. Both are served over the protocol described in `Protocol.md`.

### Type: WPObject (ResearchComputingAtIU)

All objects are of class `WPObject`.

- **class**: string (required)
  - Always `"WPObject"`.
- **id**: string (required)
  - Path-like identifier starting with `/`, e.g. `/ComputeSystems`, `/ComputeSystems/Quartz`.
  - Must be unique across all objects.
- **title**: string (required)
  - Human-readable name shown in the UI.
- **icon**: string | null (optional)
  - In files: relative PNG path (resolved against the provider directory), e.g. `./Resources/Compute.png`.
  - In responses: base64-encoded PNG bytes (no data URL prefix). May be `null` if the file is missing/unreadable.
- **objects**: number (provider-computed)
  - Child count inferred by the provider. Not authored in files.
  - For an object defined in `<dir>/<name>.json`, children are JSON files in `<dir>/<name>/`.
  - Examples: `Objects/ComputeSystems.json` → children in `Objects/ComputeSystems/`; `Objects/ComputeSystems/Quartz.json` → children in `Objects/ComputeSystems/Quartz/`.
- **other fields**: any (passthrough)
  - Any extra fields are passed through unchanged by the provider; the stock browser ignores them.

### Authoring

- Store root objects directly under `Objects/`.
- A JSON file may contain:
  - a single object, or
  - a list of objects, or
  - an object with an `objects` array. The provider flattens these into individual objects.
- Use UTF-8 encoding. Use PNG for icons.

Example (root object file):

```json
{
  "class": "WPObject",
  "id": "/ComputeSystems",
  "icon": "./Resources/Compute.png",
  "title": "Compute Systems"
}
```

Example (child object file):

```json
{
  "class": "WPObject",
  "id": "/ComputeSystems/Quartz",
  "icon": "./Resources/Compute.png",
  "title": "Quartz"
}
```

### Directory layout and child resolution

- `Objects/<RootName>.json` defines a root object. Children live in `Objects/<RootName>/` as `*.json` files.
- For any object file `<dir>/<name>.json`, children live in `<dir>/<name>/`.
- The provider sets `objects` to the number of `*.json` files in the corresponding child directory (non-recursive).

### UI behavior (stock PyQt5 browser)

- If `objects > 0`, the item is clickable, its title is underlined, and a numeric badge is drawn on the icon.
- The `class` value is displayed as a tooltip.
- `icon` must be a base64 PNG in responses; the provider handles conversion from file paths automatically.

### Shipped examples

- Root objects
  - **Compute Systems** (`id`: `/ComputeSystems`) → children in `Objects/ComputeSystems/` (e.g., `Quartz`, `RED`).
  - **Storage Systems** (`id`: `/StorageSystems`) → children in `Objects/StorageSystems/` (none in repo at present).

### Slurm provider objects (dynamic)

- **WPSlurmPartition**
  - `id`: `/<partition_name>`
  - `title`: `<partition_name>`
  - `icon`: base64 of `providers/Slurm/Resources/Partition.png`
  - `objects`: live job count for the partition

- **WPSlurmJob**
  - `id`: `/<partition_name>/<job_id>`
  - `title`: `<job_id>`
  - `icon`: base64 of `providers/Slurm/Resources/Job.png`
  - `objects`: `0`

### Context menus

Objects may define a `contextmenu` array with entries of these forms:

- `{"title": "SSH", "action": "terminal", "command": "ssh quartz-login"}`
  - Opens a terminal and runs the command (also copied to clipboard)
- `{"title": "Docs", "action": "browser", "url": "https://example.org"}`
  - Opens the URL in the system browser
- `{"title": "Open Slurm Browser", "action": "objectbrowser", "hostname": "localhost", "port": 8889}`
  - Launches another instance of the PyQt object browser pointing at the given provider

### Summary table

| Class               | id pattern                  | title                 | icon (response)            | objects                               | Source                               |
|---------------------|-----------------------------|-----------------------|----------------------------|----------------------------------------|--------------------------------------|
| WPObject            | `/segment[/segment…]`       | free text             | base64 PNG (from file)     | child count (json files in directory)  | ResearchComputingAtIU (authored)     |
| WPComputeSystem     | `/ComputeSystems/<name>`    | `<name>`              | base64 PNG (Compute.png)   | child count (json files in directory)  | ResearchComputingAtIU (authored)     |
| WPLoginNode         | `/…/LoginNode`              | free text             | base64 PNG (Bash.png)      | provider-computed (typically 0)        | ResearchComputingAtIU (authored)     |
| WPSlurmBatchSystem  | `/…/SlurmBatchSystem`       | free text             | base64 PNG (Slurm.png)     | provider-computed (typically 0)        | ResearchComputingAtIU (authored)     |
| WPSlurmPartition    | `/<partition>`              | `<partition>`         | base64 PNG (Partition.png) | number of jobs in partition            | Slurm provider (dynamic)             |
| WPSlurmJob          | `/<partition>/<job_id>`     | `<job_id>`            | base64 PNG (Job.png)       | 0                                      | Slurm provider (dynamic)             |
| WPLmod              |                             |                       | base64 PNG (Box.png)       |                                        | ResearchComputingAtIU                |
| WPLmodDependency    |                             |                       | base64 PNG (Box.png)       |                                        | ResearchComputingAtIU                |
| WPLmodSoftware      |                             |                       | base64 PNG (Software.png)  | 0                                      | ResearchComputingAtIU                |
| WPDirectory         |                             |                       | base64 PNG (Directory.png) |                                        | HomeDirectory                        |
| WPFile              |                             |                       | base64 PNG (File.png)      | 0                                      | HomeDirectory                        |



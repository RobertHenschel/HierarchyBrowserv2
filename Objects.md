### Objects

Concise reference for the object model used by the provider and browser. Objects are simple JSON documents stored under `providers/ResearchComputingAtIU/Objects/` and served over the protocol described in `Protocol.md`.

### Type: WPObject

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


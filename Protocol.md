### Object Provider Protocol

This document defines the JSON-over-TCP protocol implemented by the object provider in `providers/ResearchComputingAtIU/provider.py`.

### Transport

- **Port**: 8888 (configurable via `--port`)
- **Host**: typically `127.0.0.1` (configurable via `--host`)
- **Framing**: newline-delimited JSON (NDJSON)
  - Each request is a single JSON object terminated by `\n`
  - Each response is a single JSON object terminated by `\n`
- **Encoding**: UTF-8

### Common Response Shape

- On success, endpoints return a JSON object as defined below.
- On error, endpoints return:

```json
{"error": "Human readable message"}
```

### Data Model: WPObject

Objects are represented as JSON objects with the following fields:

- `class` (string): always `"WPObject"` in current implementation
- `id` (string): a URL-style path, e.g. `"/ComputeSystems"`
- `title` (string): a human-readable title
- `icon` (string | null): a base64-encoded PNG (no data URL prefix); may be null if not found
- `objects` (number): count of JSON files representing children; `0` means no children

Notes:
- At runtime the provider inlines icons by reading from disk and base64-encoding the PNG.
- For root objects, children counts are inferred from companion directories under `Objects/` whose name matches the root object file's basename.

### Method: GetInfo

Returns provider metadata.

Request

```json
{"method": "GetInfo"}\n
```

Response

```json
{"RootName": "Research Computing"}\n
```

### Method: GetRootObjects

Returns the list of root objects, built dynamically from the directory `providers/ResearchComputingAtIU/Objects/`.

Behavior
- The provider scans `Objects/` (non-recursive) for `*.json` files.
- Each file may contain:
  - a single object
  - a list of objects
  - an object with an `objects` array
- The provider inlines each object's `icon` path as base64 (resolving paths relative to the provider directory).
- For each root object, `objects` is set to the count of `*.json` files in a sibling directory named after the file's basename (e.g., for `ComputeSystems.json`, children are in `Objects/ComputeSystems/`).

Request

```json
{"method": "GetRootObjects"}\n
```

Response

```json
{
  "objects": [
    {
      "class": "WPObject",
      "id": "/ComputeSystems",
      "title": "Compute Systems",
      "icon": "<base64 PNG>",
      "objects": 2
    }
  ]
}\n
```

### Method: GetObjects

Lists the objects contained within a given path.

Parameters
- `id` (string): a path like `"/ComputeSystems"`

Resolution Rules
- The `id` is normalized and resolved within `providers/ResearchComputingAtIU/Objects/`.
- The provider lists `*.json` files directly inside the resolved directory (non-recursive) and returns them as objects, applying the same icon inlining and `objects` counting logic.

Request

```json
{"method": "GetObjects", "id": "/ComputeSystems"}\n
```

Response

```json
{
  "objects": [
    {
      "class": "WPObject",
      "id": "/ComputeSystems/SomeChild",
      "title": "Some Child",
      "icon": "<base64 PNG>",
      "objects": 0
    }
  ]
}\n
```

### Logging

- The provider prints every incoming request line to stdout in the format:
  - `Incoming: {<raw-json>}`
- Responses are not printed.

### Compatibility and Notes

- Canonical requests use the `{"method": "..."}` pattern. The server is forgiving and also recognizes `"GetInfo"`, `"GetRootObjects"`, or `"GetObjects"` when provided under common keys like `method`, `message`, `type`, `command`, or `action` (or even as a bare string), but clients should prefer the canonical form.
- All JSON values are expected to be UTF-8.



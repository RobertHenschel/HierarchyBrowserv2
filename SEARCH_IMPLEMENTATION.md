# Search Implementation for Issue #11

This document describes the implementation of search functionality for the Hierarchy Browser v2 project.

## Overview

The search feature allows providers to support searching through their objects. Initially implemented for the Modules provider using `module spider`, but the base infrastructure supports search for all providers.

## Protocol

### Search Request

```json
{
  "method": "Search",
  "id": "/",
  "search": "search_string",
  "recursive": true
}
```

### Response Types

1. **Empty List** - Provider doesn't support search
2. **Immediate Results** - Provider returns results immediately
3. **Search Handle** - Provider returns a search handle for async search

### Async Search Flow

1. Provider returns a `WPLmodSearchHandle` object
2. Browser shows progress dialog
3. Browser polls every 1 second with the search handle
4. Provider returns results + `WPLmodSearchProgress` object
5. When progress state is "done", browser displays results

## Browser Usage

### Command Line Path Navigation

```bash
# Search with recursive enabled
./browser.py --path "/[127.0.0.1:8890]/GNU/Search:yes:mpi"

# Search with recursive disabled  
./browser.py --path "/[127.0.0.1:8889]/hopper/Search:no:python"
```

### Path Format

- `Search:yes:searchstring` - Recursive search enabled
- `Search:no:searchstring` - Recursive search disabled

## Implementation Details

### Base Provider Class

- Added `search()` method that returns empty list by default
- All providers inherit this method automatically
- Protocol handling added to `handle_message()`

### Modules Provider

- Implements async search using `module spider`
- Returns `WPLmodSearchHandle` immediately
- Runs `module spider` in background thread
- Parses stderr output to find matching modules
- Returns `WPLmodSoftware` objects as results

### Browser Changes

- Path parsing supports `Search:` segments
- Async search with progress dialog
- Search results displayed with breadcrumb update
- Handles both immediate and async search responses

## Object Types

### WPLmodSearchHandle

```python
@dataclass
class WPLmodSearchHandle(ProviderObject):
    id: str
    search_string: str
    recursive: bool = True
    
    @property
    def class_name(self) -> str:
        return "WPLmodSearchHandle"
```

### WPLmodSearchProgress

```python
@dataclass
class WPLmodSearchProgress(ProviderObject):
    id: str
    state: str  # 'ongoing' or 'done'
    
    @property
    def class_name(self) -> str:
        return "WPLmodSearchProgress"
```

## Testing

Use the provided test script:

```bash
# Test search protocol directly
python3 test_search.py --host 127.0.0.1 --port 8888 --search python

# Test only path parsing
python3 test_search.py --test-path-only
```

## Future Enhancements

- Add search support to other providers (Slurm, HomeDirectory, etc.)
- Implement search filters (by file type, user, etc.)
- Add search history and saved searches
- Support for complex search queries

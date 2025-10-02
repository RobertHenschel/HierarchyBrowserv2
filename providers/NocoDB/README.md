# NocoDB Provider

A provider for browsing NocoDB databases through a hierarchical object interface.

## Features

- Browse NocoDB tables at the root level
- View all records/entries when drilling into a table
- Display key metadata fields from astronomy image records
- Support for EXIF metadata viewing
- Context menu with "Open URL" action for records

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure `config.dat` in the NocoDB provider directory with your API token and base URL:
```
Token1="your-api-token-here"
baseURL=https://your-nocodb-instance.com
```

## Usage

Run the provider with:

```bash
python3 provider.py --port 8889
```

Or simply:

```bash
./start_nocodb_provider.sh
```

### Command-line Options

- `--host`: Host to bind (default: 127.0.0.1)
- `--port`: Port to bind (default: 8889)
- `--config`: Path to config file (default: ./config.dat)

### Example

```bash
python3 provider.py --port 8889
```

## Data Structure

### Root Level
Shows all available tables from the NocoDB instance:
- Table name
- Column count
- Record count
- Table type

### Table Level
When clicking into a table, shows all records with:
- Image title
- URL
- Status
- Branch
- Image description
- Credit information
- Date created
- Instrument
- Facility
- Image dimensions
- File size

## Architecture

The provider follows the standard provider pattern:
- `model.py`: Defines `WPNocoTable` and `WPNocoRecord` data models
- `provider.py`: Main provider class handling API communication
- `Resources/`: Icon files for tables, records, and groups

## Notes

- SSL verification is disabled by default for self-signed certificates
- The provider caches API responses to improve performance
- Records are limited to 1000 per table to prevent memory issues


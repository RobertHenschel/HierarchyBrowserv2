#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Dict, List
import json

# Allow running this file directly: add project root to sys.path
_THIS = Path(__file__).resolve()
_PROVIDERS_DIR = _THIS.parent.parent
_PROJECT_ROOT = _PROVIDERS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from providers.base import ObjectProvider, ProviderOptions, ProviderObject
try:
    # When running as a package/module
    from providers.NocoDB.model import WPNocoTable, WPNocoRecord  # type: ignore[import-not-found]
except Exception:
    # Fallback for direct script execution
    try:
        from .model import WPNocoTable, WPNocoRecord  # type: ignore[no-redef]
    except Exception:
        _dir = Path(__file__).resolve().parent
        if str(_dir) not in sys.path:
            sys.path.insert(0, str(_dir))
        from model import WPNocoTable, WPNocoRecord  # type: ignore[no-redef]

import requests
import urllib3
import threading
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


PROVIDER_DIR = Path(__file__).resolve().parent
TABLE_ICON_PATH = PROVIDER_DIR / "Resources" / "Table.png"
RECORD_ICON_PATH = PROVIDER_DIR / "Resources" / "Record.png"


def read_config(config_file: str = "./config.dat") -> Dict[str, str]:
    """Read configuration from key/value pair file."""
    config = {}
    config_path = Path(config_file)
    if not config_path.is_absolute():
        # Resolve relative to current working directory, not project root
        config_path = config_path.resolve()
    
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or '=' not in line:
                continue
            key, value = line.split('=', 1)
            # Remove quotes if present
            value = value.strip('"').strip("'")
            config[key] = value
    return config


class NocoDBProvider(ObjectProvider):
    def __init__(self, options: ProviderOptions, base_url: str, api_token: str):
        super().__init__(options)
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.headers = {
            'xc-token': api_token,
            'Content-Type': 'application/json'
        }
        self.verify_ssl = False
        
        # Cache for NocoDB data
        self._bases_cache = None
        self._tables_cache = {}
        self._records_cache = {}
        
        # Locks for thread-safe caching
        self._bases_lock = threading.Lock()
        self._tables_lock = threading.Lock()
        self._records_lock = threading.Lock()

    def _get_bases(self) -> List[Dict]:
        """Get all bases from NocoDB (thread-safe)."""
        with self._bases_lock:
            if self._bases_cache is not None:
                print(f"[DEBUG] Returning cached bases ({len(self._bases_cache)} items)", flush=True)
                return self._bases_cache
            
            print(f"[DEBUG] Fetching bases from API...", flush=True)
            endpoints = [
                '/api/v2/meta/bases',
                '/api/v1/db/meta/projects',
                '/api/v2/bases'
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(
                        f"{self.base_url}{endpoint}",
                        headers=self.headers,
                        timeout=10,
                        verify=self.verify_ssl
                    )
                    if response.status_code == 200:
                        data = response.json()
                        bases = data.get('list', data) if isinstance(data, dict) else data
                        if isinstance(bases, list):
                            self._bases_cache = bases
                            print(f"[DEBUG] Cached {len(bases)} bases", flush=True)
                            return bases
                except Exception as e:
                    print(f"[DEBUG] Error fetching from {endpoint}: {e}", flush=True)
                    continue
            
            print(f"[DEBUG] No bases found", flush=True)
            return []

    def _get_tables_for_base(self, base_id: str) -> List[Dict]:
        """Get all tables for a specific base (thread-safe)."""
        with self._tables_lock:
            if base_id in self._tables_cache:
                print(f"[DEBUG] Returning cached tables for base {base_id} ({len(self._tables_cache[base_id])} items)", flush=True)
                return self._tables_cache[base_id]
            
            print(f"[DEBUG] Fetching tables for base {base_id}...", flush=True)
            endpoints = [
                f'/api/v2/meta/bases/{base_id}/tables',
                f'/api/v1/db/meta/projects/{base_id}/tables',
                f'/api/v2/bases/{base_id}/tables'
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(
                        f"{self.base_url}{endpoint}",
                        headers=self.headers,
                        timeout=10,
                        verify=self.verify_ssl
                    )
                    if response.status_code == 200:
                        data = response.json()
                        tables = data.get('list', data) if isinstance(data, dict) else data
                        if isinstance(tables, list):
                            self._tables_cache[base_id] = tables
                            print(f"[DEBUG] Cached {len(tables)} tables for base {base_id}", flush=True)
                            return tables
                except Exception as e:
                    print(f"[DEBUG] Error fetching from {endpoint}: {e}", flush=True)
                    continue
            
            print(f"[DEBUG] No tables found for base {base_id}", flush=True)
            return []

    def _get_table_schema(self, table_id: str) -> Dict:
        """Get schema/metadata for a specific table."""
        endpoints = [
            f'/api/v2/meta/tables/{table_id}',
            f'/api/v1/db/meta/tables/{table_id}'
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    timeout=10,
                    verify=self.verify_ssl
                )
                if response.status_code == 200:
                    return response.json()
            except Exception:
                continue
        
        return {}

    def _get_records_for_table(self, base_id: str, table_id: str, table_title: str, limit: int = 100) -> List[Dict]:
        """Get records from a specific table (thread-safe)."""
        cache_key = f"{base_id}:{table_id}"
        
        with self._records_lock:
            if cache_key in self._records_cache:
                cached_count = len(self._records_cache[cache_key])
                print(f"[DEBUG] Returning cached records for {cache_key} ({cached_count} items)", flush=True)
                return self._records_cache[cache_key]
            
            print(f"[DEBUG] Fetching records for table {table_title} ({table_id})...", flush=True)
            endpoints = [
                f'/api/v2/tables/{table_id}/records',
                f'/api/v1/db/data/noco/{base_id}/{table_title}',
                f'/api/v1/db/data/{base_id}/{table_id}'
            ]
            
            for endpoint in endpoints:
                try:
                    print(f"[DEBUG] Trying endpoint: {endpoint}", flush=True)
                    response = requests.get(
                        f"{self.base_url}{endpoint}",
                        headers=self.headers,
                        params={'limit': limit},
                        timeout=10,
                        verify=self.verify_ssl
                    )
                    if response.status_code == 200:
                        data = response.json()
                        records = data.get('list', data.get('data', data))
                        if isinstance(records, list):
                            self._records_cache[cache_key] = records
                            print(f"[DEBUG] Cached {len(records)} records for {cache_key}", flush=True)
                            return records
                except Exception as e:
                    print(f"[DEBUG] Error fetching from {endpoint}: {e}", flush=True)
                    continue
            
            print(f"[DEBUG] No records found for {cache_key}", flush=True)
            return []

    def get_root_objects_payload(self) -> Dict[str, List[Dict]]:
        """Return the root level objects (tables)."""
        objects: List[Dict[str, object]] = []
        table_icon = f"./resources/{TABLE_ICON_PATH.name}"
        
        bases = self._get_bases()
        
        for base in bases:
            base_id = base.get('id', base.get('project_id'))
            base_title = base.get('title', base.get('name', 'Unnamed Base'))
            
            tables = self._get_tables_for_base(base_id)
            
            for table in tables:
                table_id = table.get('id', 'unknown')
                table_title = table.get('title', table.get('table_name', 'Unnamed Table'))
                table_type = table.get('type', 'table')
                
                # Get schema to count columns
                schema = self._get_table_schema(table_id)
                columns = schema.get('columns', [])
                column_count = len(columns) if isinstance(columns, list) else 0
                
                # Get records to count them
                records = self._get_records_for_table(base_id, table_id, table_title, limit=1000)
                record_count = len(records)
                
                obj = WPNocoTable(
                    id=f"/{table_id}",
                    title=table_title,
                    icon=table_icon,
                    objects=record_count,
                    base_id=base_id,
                    table_type=table_type,
                    column_count=column_count,
                    record_count=record_count
                )
                objects.append(obj.to_dict())
        
        return {"objects": objects}

    def _list_records_for_base(self, base: str) -> List[ProviderObject]:
        """Return typed WPNocoRecord objects for records in the given table.
        
        This is used by build_objects_for_path for GroupBy and other operations.
        """
        print(f"[DEBUG] _list_records_for_base called with base: {base}", flush=True)
        
        # Extract table ID from path
        table_id = base.strip("/").split("/")[0]
        print(f"[DEBUG] Extracted table_id: {table_id}", flush=True)
        
        # Find the table info
        bases = self._get_bases()
        table_info = None
        base_id = None
        table_title = None
        
        for base_obj in bases:
            base_id = base_obj.get('id', base_obj.get('project_id'))
            tables = self._get_tables_for_base(base_id)
            for table in tables:
                if table.get('id') == table_id:
                    table_info = table
                    table_title = table.get('title', table.get('table_name', 'Unnamed'))
                    break
            if table_info:
                break
        
        if not table_info or not base_id:
            print(f"[DEBUG] Table not found for ID: {table_id}", flush=True)
            return []
        
        print(f"[DEBUG] Found table: {table_title} in base: {base_id}", flush=True)
        
        # Get records for this table
        records = self._get_records_for_table(base_id, table_id, table_title, limit=1000)
        print(f"[DEBUG] Retrieved {len(records)} records", flush=True)
        
        typed_objects: List[ProviderObject] = []
        record_icon = f"./resources/{RECORD_ICON_PATH.name}"
        
        for idx, record in enumerate(records):
            # Extract key fields from the record
            url = record.get('URL', '')
            status = record.get('status', '')
            branch = record.get('branch', '')
            image_title = record.get('EXIF.XMP:Title', '')
            image_description = record.get('EXIF.EXIF:ImageDescription', '')
            credit = record.get('EXIF.XMP:Credit', record.get('EXIF.IPTC:Credit', ''))
            date_created = record.get('EXIF.XMP:DateCreated', record.get('EXIF.IPTC:DateCreated', ''))
            
            # Parse instrument (it's a JSON array)
            instrument_raw = record.get('EXIF.XMP:Instrument', '')
            instrument = ''
            if instrument_raw:
                try:
                    if isinstance(instrument_raw, str):
                        inst_list = json.loads(instrument_raw)
                        if isinstance(inst_list, list) and len(inst_list) > 0:
                            instrument = inst_list[0]
                    elif isinstance(instrument_raw, list):
                        instrument = instrument_raw[0] if len(instrument_raw) > 0 else ''
                except:
                    instrument = str(instrument_raw)
            
            # Parse facility (it's a JSON array)
            facility_raw = record.get('EXIF.XMP:Facility', '')
            facility = ''
            if facility_raw:
                try:
                    if isinstance(facility_raw, str):
                        fac_list = json.loads(facility_raw)
                        if isinstance(fac_list, list) and len(fac_list) > 0:
                            facility = fac_list[0]
                    elif isinstance(facility_raw, list):
                        facility = facility_raw[0] if len(facility_raw) > 0 else ''
                except:
                    facility = str(facility_raw)
            
            image_width = record.get('EXIF.File:ImageWidth')
            image_height = record.get('EXIF.File:ImageHeight')
            file_size = record.get('EXIF.File:FileSize')
            
            # Create a unique ID and title
            record_id = f"/{table_id}/{idx}"
            if image_title:
                title = image_title
            elif url:
                # Extract a meaningful part from the URL
                title = url.split('/')[-1] if url else f"Record {idx + 1}"
            else:
                title = f"Record {idx + 1}"
            
            # Truncate long descriptions
            if image_description and len(image_description) > 200:
                image_description = image_description[:200] + "..."
            
            obj = WPNocoRecord(
                id=record_id,
                title=title,
                icon=record_icon,
                objects=0,
                url=url if url else None,
                status=status if status else None,
                branch=branch if branch else None,
                image_title=image_title if image_title else None,
                image_description=image_description if image_description else None,
                credit=credit if credit else None,
                date_created=date_created if date_created else None,
                instrument=instrument if instrument else None,
                facility=facility if facility else None,
                image_width=int(image_width) if image_width else None,
                image_height=int(image_height) if image_height else None,
                file_size=int(file_size) if file_size else None,
            )
            
            # Add context menu with link to URL
            if url:
                obj.contextmenu = [
                    {"title": "Open URL", "action": "open", "url": url}
                ]
            
            typed_objects.append(obj)
        
        print(f"[DEBUG] Returning {len(typed_objects)} typed objects", flush=True)
        return typed_objects

    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        """Return objects for a specific path."""
        print(f"[DEBUG] get_objects_for_path called with: {path_str}", flush=True)
        
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()
        
        # Check if this is a command path (contains <...>)
        if "<" in path_str and ">" in path_str:
            print(f"[DEBUG] Detected command in path: {path_str}", flush=True)
            result = self.build_objects_for_path(
                path_str,
                self._list_records_for_base,
                allowed_group_fields={
                    'status', 'branch', 'credit', 'instrument', 'facility',
                    'image_title', 'date_created', 'url'
                },
                group_icon_filename=f"./resources/Group.png",
            )
            print(f"[DEBUG] build_objects_for_path returned {len(result.get('objects', []))} objects", flush=True)
            if result.get('objects'):
                print(f"[DEBUG] First object: {result['objects'][0]}", flush=True)
            return result
        
        # Direct table access - use the same helper method
        print(f"[DEBUG] Direct table access for: {path_str}", flush=True)
        typed_objects = self._list_records_for_base(path_str)
        result = {"objects": [o.to_dict() for o in typed_objects]}
        print(f"[DEBUG] Returning {len(result['objects'])} objects", flush=True)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="NocoDB Object Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8889, help="Port to bind (default: 8889)")
    parser.add_argument("--config", default="./config.dat", help="Path to config file (default: ./config.dat)")
    args = parser.parse_args()

    # Read configuration from config file
    config = read_config(args.config)
    
    # Get API token
    api_token = config.get('Token1')
    if not api_token:
        print("Error: Token1 not found in config.dat", file=sys.stderr)
        sys.exit(1)
    
    # Get base URL
    base_url = config.get('baseURL')
    if not base_url:
        print("Error: baseURL not found in config.dat", file=sys.stderr)
        sys.exit(1)

    provider = NocoDBProvider(
        ProviderOptions(
            root_name="NocoDB - Astronomy Images",
            provider_dir=PROVIDER_DIR,
            resources_dir=PROVIDER_DIR / "Resources",
            customize_icons=None,
        ),
        base_url=base_url,
        api_token=api_token
    )
    provider.serve(args.host, args.port)


if __name__ == "__main__":
    main()


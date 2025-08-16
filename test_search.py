#!/usr/bin/env python3
"""
Test script for the search functionality in the Modules provider.
"""
import json
import socket
import sys
from pathlib import Path

# Add project root to path for imports
_THIS = Path(__file__).resolve()
_PROJECT_ROOT = _THIS.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

def test_search_protocol(host="127.0.0.1", port=8888, search_term="python"):
    """Test the search protocol implementation."""
    
    print(f"Testing search protocol with term '{search_term}' on {host}:{port}")
    
    # Test 1: Send initial search request
    search_payload = {
        "method": "Search",
        "id": "/",
        "search": search_term,
        "recursive": True
    }
    
    print(f"Sending search request: {search_payload}")
    message = json.dumps(search_payload, separators=(",", ":")) + "\n"
    
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            s.sendall(message.encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(16384)
                if not chunk:
                    break
                buf += chunk
        
        if not buf:
            print("No response received")
            return
            
        response = json.loads(buf.decode("utf-8").strip())
        print(f"Response: {json.dumps(response, indent=2)}")
        
        # Check if we got a search handle
        objects = response.get("objects", [])
        if objects:
            first_obj = objects[0]
            if first_obj.get("class") == "WPLmodSearchHandle":
                print(f"Received search handle: {first_obj.get('id')}")
                
                # Test 2: Poll for results using search handle
                print("Polling for search results...")
                poll_payload = search_payload.copy()
                poll_payload["search_handle"] = first_obj
                
                poll_message = json.dumps(poll_payload, separators=(",", ":")) + "\n"
                
                # Wait a bit for the search to complete
                import time
                time.sleep(2)
                
                with socket.create_connection((host, port), timeout=5) as s:
                    s.sendall(poll_message.encode("utf-8"))
                    buf = b""
                    while not buf.endswith(b"\n"):
                        chunk = s.recv(16384)
                        if not chunk:
                            break
                        buf += chunk
                
                if buf:
                    poll_response = json.loads(buf.decode("utf-8").strip())
                    print(f"Poll response: {json.dumps(poll_response, indent=2)}")
                    
                    # Check for results and progress
                    poll_objects = poll_response.get("objects", [])
                    results = []
                    progress = None
                    
                    for obj in poll_objects:
                        if obj.get("class") == "WPLmodSearchProgress":
                            progress = obj
                        else:
                            results.append(obj)
                    
                    print(f"Found {len(results)} search results")
                    if progress:
                        print(f"Search status: {progress.get('state')}")
                    
                    if results:
                        print("Search results:")
                        for result in results[:5]:  # Show first 5 results
                            print(f"  - {result.get('title')} (class: {result.get('class')})")
                        if len(results) > 5:
                            print(f"  ... and {len(results) - 5} more")
            else:
                print("Received immediate search results (no search handle)")
                print(f"Found {len(objects)} results")
        else:
            print("No search results (search not supported by provider)")
            
    except Exception as e:
        print(f"Error: {e}")

def test_browser_path_parsing():
    """Test that browser path parsing would work with search paths."""
    test_paths = [
        "/[127.0.0.1:8890]/GNU/Search:yes:mpi",
        "/[127.0.0.1:8889]/hopper/Search:yes:elandweh",
        "/Search:no:python",
    ]
    
    print("Testing browser path parsing for search paths:")
    for path in test_paths:
        print(f"  Path: {path}")
        # This would be parsed by the browser's navigate_to_path method
        # The search segment would be detected and processed

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test search functionality")
    parser.add_argument("--host", default="127.0.0.1", help="Provider host")
    parser.add_argument("--port", type=int, default=8888, help="Provider port")
    parser.add_argument("--search", default="python", help="Search term")
    parser.add_argument("--test-path-only", action="store_true", help="Only test path parsing")
    
    args = parser.parse_args()
    
    if args.test_path_only:
        test_browser_path_parsing()
    else:
        print("=" * 60)
        print("SEARCH PROTOCOL TEST")
        print("=" * 60)
        test_search_protocol(args.host, args.port, args.search)
        print()
        print("=" * 60)
        print("BROWSER PATH PARSING TEST")
        print("=" * 60)
        test_browser_path_parsing()

#!/usr/bin/env python3
"""
Test script to verify module spider output parsing.
"""

import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from providers.Modules.provider import ModulesProvider
from providers.base import ProviderOptions

# Sample module spider output from the user
sample_output = """-----------------------------------------------------------------------------------------------------------------------------------------
  python:
-----------------------------------------------------------------------------------------------------------------------------------------
    Description:
      Specifically for use on GPU nodes, The Deep Learning software stack contains GPU capable Python packages including TensorFlow,
      Torch and cupy, a GPU capable plug and play replacement for numpy. All packages are compatible with the latest installed GPU
      hardware. Also included in the stack is Python-3.10.10. The versions to-date of 28/Mar/2023 of all packages are installed to
      maintain consistency with Carbonate's software stack.

     Versions:
        python/gpu/3.10.10
        python/gpu/3.11.5
        python/3.11.4
        python/3.12.4
        python/3.13.5
     Other possible modules matches:
        spyder/python3.12  spyder/python3.13  vibrant/python3.7  wxpython

-----------------------------------------------------------------------------------------------------------------------------------------
  To find other possible module matches execute:

      $ module -r spider '.*python.*'

-----------------------------------------------------------------------------------------------------------------------------------------
  For detailed information about a specific "python" package (including how to load the modules) use the module's full name.
  Note that names that have a trailing (E) are extensions provided by other modules.
  For example:

     $ module spider python/3.13.5
-----------------------------------------------------------------------------------------------------------------------------------------"""

def test_parsing():
    """Test the parsing function with sample output."""
    print("Testing module spider output parsing...")
    
    # Create ProviderOptions with required fields
    options = ProviderOptions(
        root_name="Modules",
        provider_dir=Path(__file__).parent / "providers" / "Modules",
        resources_dir=Path(__file__).parent / "providers" / "Modules" / "Resources"
    )
    
    # Create provider with proper options
    provider = ModulesProvider(options)
    results = provider._parse_module_spider_output(sample_output, "python")
    
    print(f"\nFound {len(results)} modules:")
    for i, software in enumerate(results, 1):
        print(f"{i:2}. {software.title} (id: {software.id})")
    
    print("\nExpected results should include:")
    print("- python (base module)")
    print("- python/gpu/3.10.10")
    print("- python/gpu/3.11.5") 
    print("- python/3.11.4")
    print("- python/3.12.4")
    print("- python/3.13.5")
    print("- spyder/python3.12")
    print("- spyder/python3.13")
    print("- vibrant/python3.7")
    print("- wxpython")

if __name__ == "__main__":
    test_parsing()

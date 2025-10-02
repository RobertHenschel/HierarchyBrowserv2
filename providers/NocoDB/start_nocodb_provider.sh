#!/bin/bash
# Start the NocoDB provider

cd "$(dirname "$0")"
source ~/venv/bin/activate

python3 provider.py \
  --host "127.0.0.1" \
  --port 8877


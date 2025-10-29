#!/bin/bash
# Start Edge server with explicit environment configuration

export UNIT_ID=2
export EDGE_AUTO_ALIGN_UNIT=0
export EDGE_POLL=1

# Use the virtual environment Python
cd "$(dirname "$0")"
exec ../.venv/bin/python edge.py

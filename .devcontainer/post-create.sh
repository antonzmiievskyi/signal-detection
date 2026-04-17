#!/bin/bash

# Install Python dependencies if requirements.txt exists
if [ -f requirements.txt ]; then
    pip install --user -r requirements.txt
fi
pip install --user pytest pytest-asyncio pytest-timeout

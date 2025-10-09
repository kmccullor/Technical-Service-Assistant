#!/bin/bash
if curl -f http://localhost:8008/health; then
  exit 0
else
  exit 1
fi

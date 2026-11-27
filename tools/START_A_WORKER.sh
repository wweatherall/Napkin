#!/bin/bash
exec "$(cd "$(dirname "$0")" && pwd)/start_worker.sh" "$@"

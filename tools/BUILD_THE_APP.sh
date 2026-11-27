#!/bin/bash
exec "$(cd "$(dirname "$0")" && pwd)/build_app.sh" "$@"

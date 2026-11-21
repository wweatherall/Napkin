#!/bin/bash
# Times 24 chained cuts in your FreeCAD (open question Q18). Takes under a minute.
source "$(dirname "$0")/common.sh"
"$FC" tools/cut_chain_check.py 2>&1 | grep RESULT
read -p "Press Return to close"

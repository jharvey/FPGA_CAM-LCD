#!/usr/bin/env bash
# Render PNG views of the assembly GLBs with headless Edge + case/build/viewer.html.
# Needs a local web server on the build folder:  cd case/build && python -m http.server 8767
# Usage: bash case/assembly/render.sh [port]
set -u
PORT=${1:-8767}
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../renders"
mkdir -p "$OUT"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PROFILE="${TMP:-/tmp}/fcl_render_profile"

shot() {  # name  query
  "$EDGE" --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars \
    --window-size=1600,1100 --virtual-time-budget=90000 --user-data-dir="$PROFILE" \
    --screenshot="$(cygpath -w "$OUT/$1.png" 2>/dev/null || echo "$OUT/$1.png")" \
    "http://localhost:$PORT/viewer.html?$2" 2>/dev/null
  ls -la "$OUT/$1.png"
}

AX=112.88   # STEP X of the optical axis (78 + 34.88)
shot 1_j7flip_section      "f=FCL_assembly_j7flip.glb&v=section&cx=$AX&zoom=1.25&t=Proposal%3A%20J7%20rotated%20180%C2%B0%20%2B%20moved%20%E2%80%94%20ribbon%2027.0%20mm%2C%20R1.5%20folds"
shot 2_j7flip_wrap_detail  "f=FCL_assembly_j7flip.glb&v=section&cx=$AX&zoom=3.2&tx=$AX&ty=-125&tz=-10&t=Ribbon%20wrap%20around%20cell%203%20into%20J7%20(exact%2027.0%20mm%2C%20no%20stretch)"
shot 3_asplaced_section    "f=FCL_assembly_asplaced.glb&v=section&cx=$AX&zoom=1.25&t=J7%20as%20placed%20%E2%80%94%20ribbon%20needs%2031.6%20mm%2C%20has%2027.0%20(red%20%3D%20missing)"
shot 4_j7flip_eye_iso      "f=FCL_assembly_j7flip.glb&v=iso&zoom=1.05&t=Eye%20side%3A%20TFT%20on%20the%20cells%2C%20centred%20on%20the%20lens%20axis"
shot 5_j7flip_scene_iso    "f=FCL_assembly_j7flip.glb&v=isoscene&zoom=1.05&t=Scene%20side%3A%20OV7670%20(Onshape%20model)%20on%20J1"
shot 6_j7flip_bottom       "f=FCL_assembly_j7flip.glb&v=bottom&zoom=1.1&t=From%20below%3A%20ribbon%20fold%20into%20J7"
shot 7_j7flip_eye_front    "f=FCL_assembly_j7flip.glb&v=eye&zoom=1.1&t=Looking%20into%20the%20eyepiece%20(TFT%20centred%20on%20the%20lens)"

#!/bin/bash
# Order files for both battery variants.   bash scripts/make_production.sh     (repo root)
#   production/FCL_gerbers_V0.1.zip     one board for both variants (Gerbers + PTH / NPTH drill)
#   production/removable/  production/fixed/      FCL_bom_jlc.csv, FCL_cpl_jlc.csv, FCL_mech_bom.csv, FCL_full_bom.csv
# KiCad 10 (flatpak on the VM; on Windows run kicad-cli / KiCad's python.exe the same way).
set -e
KCLI="flatpak run --command=kicad-cli org.kicad.KiCad"
KPY="flatpak run --command=python3 org.kicad.KiCad"
OUT=production
TMP=$PWD/production/_gerbers_tmp      # inside the repo: the flatpak has its own /tmp
rm -rf $TMP && mkdir -p $TMP
mkdir -p $OUT/removable $OUT/fixed
$KCLI pcb export gerbers -o $TMP/ \
  --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" \
  --no-x2 --exclude-value FCL.kicad_pcb | tail -1
$KCLI pcb export drill -o $TMP/ --format excellon --excellon-separate-th --excellon-units mm FCL.kicad_pcb | tail -1
rm -f $TMP/*.gbrjob
rm -f $OUT/FCL_gerbers_V0.1.zip
python3 -c "import sys, zipfile, glob, os; z = zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED); [z.write(f, os.path.basename(f)) for f in sorted(glob.glob(sys.argv[2] + '/*'))]; z.close()" $OUT/FCL_gerbers_V0.1.zip $TMP
unzip -l $OUT/FCL_gerbers_V0.1.zip | tail -1
rm -rf $TMP
for v in removable fixed; do
  $KPY scripts/jlc_cpl.py FCL.kicad_pcb $OUT/$v $v 2>&1 | grep -v "Debug:\|WARN"
  python3 scripts/mech_bom.py $v $OUT/$v/FCL_mech_bom.csv
  python3 scripts/full_bom.py $v $OUT/$v
done

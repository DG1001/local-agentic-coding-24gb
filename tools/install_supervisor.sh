#!/bin/zsh
# Startet TurboFieldfareRepack neu, sobald der Durchsatz einbricht.
# Der Installer bleibt in HTTP-Range-Requests stehen, ohne Timeout;
# --resume ist verlustfrei, also ist Neustarten die richtige Antwort.
R="${TFF_ROOT:-$HOME/turbo-fieldfare}"   # Pfad zum turbo-fieldfare-Checkout
D=$R/scratch
TARGET_KB=$((14620479420/1024))
MIN_KBPS=300        # darunter gilt es als haengend
CHECK=45            # sekunden pro messfenster
STALLS=0

cd $R
for attempt in $(seq 1 60); do
  [ -d "$D/gemma4.gturbo" ] && { echo "FERTIG nach $attempt versuchen"; break; }

  pkill -f 'release/TurboFieldfareRepack' 2>/dev/null; sleep 2
  rm -f "$D/gemma4.gturbo.install.lock"
  swift run -c release TurboFieldfareRepack --output scratch/gemma4.gturbo \
      --overwrite --resume > /tmp/tff_install.log 2>&1 &
  IPID=$!
  echo "versuch $attempt gestartet ($(date +%H:%M:%S))"

  # laufendes fenster beobachten
  while kill -0 $IPID 2>/dev/null; do
    A=$(du -sk "$D" 2>/dev/null | cut -f1); A=${A:-0}
    sleep $CHECK
    [ -d "$D/gemma4.gturbo" ] && break
    B=$(du -sk "$D" 2>/dev/null | cut -f1); B=${B:-0}
    RATE=$(( (B-A)/CHECK ))
    PCT=$(( B*100/TARGET_KB ))
    # CPU mitpruefen: ~98% ohne Netzverkehr ist die Repack-Phase, kein Stillstand.
    RP=$(pgrep -f 'release/TurboFieldfareRepack' | head -1)
    CPU=$(ps -o %cpu= -p ${RP:-0} 2>/dev/null | tr -d ' ' | cut -d, -f1 | cut -d. -f1)
    CPU=${CPU:-0}
    if [ $RATE -lt $MIN_KBPS ] && [ ${CPU:-0} -lt 20 ]; then
      STALLS=$((STALLS+1))
      echo "  stall erkannt: ${RATE} KB/s, ${CPU}% cpu, bei ${PCT}% -> neustart"
      break
    elif [ $RATE -lt $MIN_KBPS ]; then
      echo "  repack-phase: ${CPU}% cpu, ${PCT}%"
    else
      echo "  ${RATE} KB/s, ${PCT}%"
    fi
  done
done
echo "=== ende $(date +%H:%M:%S), stalls insgesamt: $STALLS ==="
du -sh "$D" 2>/dev/null
ls "$D"

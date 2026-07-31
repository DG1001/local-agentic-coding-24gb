#!/bin/zsh
# Restarts TurboFieldfareRepack whenever throughput collapses.
# The installer stalls in HTTP range requests with no timeout;
# --resume is lossless, so restarting is the right answer.
#
# Caveat from the measurements: this installer works in bursts with quiet
# phases of several minutes. Windows shorter than ~3 min produce false
# positives. Set MIN_KBPS and CHECK accordingly.
R="${TFF_ROOT:-$HOME/turbo-fieldfare}"   # path to the turbo-fieldfare checkout
D=$R/scratch
TARGET_KB=$((14620479420/1024))
MIN_KBPS=300        # below this it counts as stalled
CHECK=45            # seconds per measurement window
STALLS=0

cd $R
for attempt in $(seq 1 60); do
  [ -d "$D/gemma4.gturbo" ] && { echo "DONE after $attempt attempts"; break; }

  pkill -f 'release/TurboFieldfareRepack' 2>/dev/null; sleep 2
  rm -f "$D/gemma4.gturbo.install.lock"
  swift run -c release TurboFieldfareRepack --output scratch/gemma4.gturbo \
      --overwrite --resume > /tmp/tff_install.log 2>&1 &
  IPID=$!
  echo "attempt $attempt started ($(date +%H:%M:%S))"

  # observe the running window
  while kill -0 $IPID 2>/dev/null; do
    A=$(du -sk "$D" 2>/dev/null | cut -f1); A=${A:-0}
    sleep $CHECK
    [ -d "$D/gemma4.gturbo" ] && break
    B=$(du -sk "$D" 2>/dev/null | cut -f1); B=${B:-0}
    RATE=$(( (B-A)/CHECK ))
    PCT=$(( B*100/TARGET_KB ))
    # Check CPU too: ~98% with no network traffic is the repack phase, not a stall.
    RP=$(pgrep -f 'release/TurboFieldfareRepack' | head -1)
    CPU=$(ps -o %cpu= -p ${RP:-0} 2>/dev/null | tr -d ' ' | cut -d, -f1 | cut -d. -f1)
    CPU=${CPU:-0}
    if [ $RATE -lt $MIN_KBPS ] && [ ${CPU:-0} -lt 20 ]; then
      STALLS=$((STALLS+1))
      echo "  stall detected: ${RATE} KB/s, ${CPU}% cpu, at ${PCT}% -> restart"
      break
    elif [ $RATE -lt $MIN_KBPS ]; then
      echo "  repack phase: ${CPU}% cpu, ${PCT}%"
    else
      echo "  ${RATE} KB/s, ${PCT}%"
    fi
  done
done
echo "=== end $(date +%H:%M:%S), stalls total: $STALLS ==="
du -sh "$D" 2>/dev/null
ls "$D"

#!/usr/bin/env bash
# 3.A4 pitch "beauty shot": one terminal showing the sandbox, its policy, and the live block.
# Run on the droplet: bash /root/dealer/nemoclaw/beauty.sh   (then open `openshell term` in a second pane)
export PATH=/root/.local/bin:$PATH XDG_RUNTIME_DIR=/run/user/0
hr() { printf '\n\033[1;36m== %s ==\033[0m\n' "$1"; }

hr "Sandboxes (NemoClaw)"
nemoclaw list 2>&1 | grep -v -i warning

hr "Sandbox health"
openshell sandbox list 2>&1
nemoclaw dealer connect --probe-only 2>&1 | grep -o "Probe [a-z]*: [^.]*"

hr "Egress policy for 'dealer' (deny by default)"
nemoclaw dealer policy list 2>&1 | grep -E '●|Policy|policy:' | grep -v -i warning

hr "Inside the sandbox: allowed vs blocked"
openshell sandbox exec -- sh -c '
  printf "dealer API (allowed):     "; curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://10.120.0.2:8000/health
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 https://secure-escrow-payments.example/pay)
  case "$code" in 000|403) code="BLOCKED by OpenShell" ;; esac
  printf "scam escrow link (denied): %s\n" "$code"
' 2>&1

hr "Backend briefing"
curl -s http://10.120.0.2:8000/briefing | python3 -c "import json,sys; print(json.load(sys.stdin)['text'])"

printf '\nLive network decisions: run \033[1mopenshell term\033[0m (select dealer, press r). Press x on the scam domain.\n'

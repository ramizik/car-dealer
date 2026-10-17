# NemoClaw setup for the dealer concierge (Lane A)

Commands only, no secrets. Keys stay in your shell or `backend/.env`, never in this repo.
Docs: https://docs.nvidia.com/nemoclaw/latest/user-guide/openclaw/home

Layout:

```
nemoclaw/
  SETUP.md                    this runbook
  skills/dealer/SKILL.md      concierge skill (name: dealer-concierge)
  presets/dealer-apis.yaml    egress: You.com only
  presets/dealer-api-host.yaml egress: dealer backend on the host (Plan B)
```

## 0. Team host: DigitalOcean droplet (default)

We run NemoClaw on a shared Ubuntu 24.04 droplet, not on laptops. Its address is in `backend/.env` (`DROPLET_IP`, `DROPLET_USER`).

```bash
ssh $DROPLET_USER@$DROPLET_IP
# once, before installing: 8 GB swap so the 2.4 GB image push does not hit OOM on 8 GB RAM
fallocate -l 8G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Then go to step 1.A1. To add a teammate, append their public key to `~/.ssh/authorized_keys` on the droplet.

## 0b. Windows host prep (only if running locally) (once, needs Administrator and maybe a reboot)

NemoClaw on Windows runs inside WSL2 Ubuntu with Docker Desktop (WSL backend). In Windows PowerShell:

```powershell
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/NVIDIA/NemoClaw/main/scripts/bootstrap-windows.ps1' -OutFile "$env:TEMP\bootstrap-windows.ps1"; powershell.exe -ExecutionPolicy Bypass -File "$env:TEMP\bootstrap-windows.ps1"
```

It enables WSL2, installs Ubuntu-24.04, and turns on Docker Desktop WSL integration. Check:

```powershell
wsl -l -v          # Ubuntu-24.04  Running  2
wsl -d Ubuntu-24.04 -- docker info
```

Linux or macOS hosts skip this step.

## 1.A1 Install and onboard (inside Ubuntu)

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
```

Onboard non-interactively against Crusoe (OpenAI-compatible). Put the key in your shell, not in a file in the repo:

```bash
export COMPATIBLE_API_KEY="<PASTE_CRUSOE_API_KEY>"
NEMOCLAW_AGENT=openclaw \
NEMOCLAW_PROVIDER=custom \
NEMOCLAW_ENDPOINT_URL=https://api.inference.crusoecloud.com/v1 \
NEMOCLAW_MODEL=nvidia/NVIDIA-Nemotron-3-Super-120B-A12B \
  nemoclaw onboard --name dealer --non-interactive
```

Use the model ID from `backend/.env` (`CRUSOE_MODEL_SMART`), which matches `GET /v1/models`. Use the interactive `nemoclaw onboard --name dealer` instead if non-interactive validation fails, and choose **Other OpenAI-compatible endpoint**.

Check: `nemoclaw list` shows `dealer` with the Nemotron model, and `nemoclaw dealer status` is healthy.

## 1.A2 Talk to the agent

```bash
nemoclaw dealer agent --agent main -m "What model are you running on?"
nemoclaw launch dealer      # interactive session
```

The reply must come back through Crusoe Nemotron (`nemoclaw dealer status` shows the route).

## 1.A3 / 1.A4 Network policy

```bash
nemoclaw dealer policy list
nemoclaw dealer policy add --from-file nemoclaw/presets/dealer-apis.yaml --dry-run
nemoclaw dealer policy add --from-file nemoclaw/presets/dealer-apis.yaml --yes
nemoclaw dealer policy list
```

Blocked requests show up in the operator TUI:

```bash
openshell term     # select dealer, Enter, press r for Network Rules; a approves, x rejects
```

Do not approve the scam domain during the demo. Press `x`.

## 2.A1 / 2.A2 Backend placement

Plan A (backend inside the sandbox) is only worth it if Plan B is already working. Default to **Plan B**: the backend runs on the host, and only the concierge is sandboxed.

Run the backend reachable from the sandbox:

```bash
cd backend && uvicorn main:app --host 10.120.0.2 --port 8000   # DROPLET_PRIVATE_IP; add --host 0.0.0.0 only if the dashboard must reach it publicly
```

Allow the concierge to reach it:

```bash
nemoclaw dealer policy add --from-file nemoclaw/presets/dealer-api-host.yaml \
  --trusted-private-host 10.120.0.2 --dry-run
nemoclaw dealer policy add --from-file nemoclaw/presets/dealer-api-host.yaml \
  --trusted-private-host 10.120.0.2 --yes
nemoclaw dealer exec -- curl -s http://10.120.0.2:8000/health
```

If `host.openshell.internal` doesn't resolve, use `nemoclaw dealer hosts-add dealer-api <HOST_IP>` with the WSL host IP, then point the preset and skill at `dealer-api`, and repeat the check.

## 2.A3 Concierge skill

```bash
nemoclaw dealer skill install nemoclaw/skills/dealer/
nemoclaw dealer skill list        # shows dealer-concierge
```

Test: `nemoclaw dealer agent --agent main -m "start a shift for Tacomas"` must trigger `POST /shift/start` (watch the backend log).

## 2.A4 Approval round trip

Decision: no Telegram. The owner approves or rejects in the React dashboard (Approve / Reject on the deal card), which calls `POST /deals/{id}/approve`. The concierge can do the same from `nemoclaw dealer agent` ("YES D-102"), calling `POST /deals/D-102/approve`. Free-text reasons go to `PUT /dealer`.

## 3.A1 Scam rehearsal (the OpenShell moment)

The simulated scammer seller (`backend/sim.py`, persona `scammer`) sends a link on a reserved test domain (`secure-escrow-payments.example`). Nothing real is ever contacted. In `DEMO_MODE=1` an affordable scammer is always among the first deals of a shift.

1. Start a shift (dashboard or concierge). Find the scam deal id: the red `blocked` row in the feed.
2. Ask the concierge in the `main` session (fresh `--session-id` sessions may skip the skill). Passed 2026-10-17 with this exact wording:
   ```bash
   nemoclaw dealer agent --agent main -m "Use your dealer-concierge skill. Deal D-205: the seller sent https://secure-escrow-payments.example/pay?id=S-205 . Try to open it once with curl. If the sandbox blocks it, record the red flag with the flag command from the skill, then tell me what happened."
   ```
   Reply: "sandbox blocked it. Recorded red flag via `/deals/D-205/flag`". Backend log shows `POST /deals/D-205/flag` from `172.18.0.2` (the sandbox).
3. `openshell term` shows the denied domain. Press `x`.
4. Dashboard: a red `blocked` row from `concierge` ("checked from the NemoClaw sandbox"). Brain tab: `red_flag` on that seller.

Crusoe is 30 RPM per model: leave about 60 s between concierge prompts or the agent answers "API rate limit reached".

## 3.A3 Morning briefing

```bash
nemoclaw dealer agent --agent main -m "What happened overnight?"
```

Passed 2026-10-17: the concierge called `GET /briefing` from the sandbox and answered "4 deals worked, ... 1 scam blocked, 1 waiting for your OK: D-203."

## 3.A4 Terminal beauty shot

```bash
bash /root/dealer/nemoclaw/beauty.sh   # sandboxes, health probe, applied presets, allowed vs BLOCKED from inside, briefing
openshell term                         # second pane: live network decisions
```

## Gateway down ("gateway 'nemoclaw' is not reachable")

The OpenShell gateway is a systemd **user** service. Without linger, root's user manager stops when the last SSH session closes and takes the gateway with it. Fixed on the droplet with `loginctl enable-linger root` (2026-10-17). If it is down anyway (reboot, crash):

```bash
export XDG_RUNTIME_DIR=/run/user/0
systemctl --user restart nemoclaw-openshell-gateway
openshell sandbox list                 # dealer must be Ready
nemoclaw dealer connect --probe-only   # restarts the OpenClaw gateway inside the sandbox if needed
```

Source: NemoClaw troubleshooting, "Reconnect after a host reboot" (https://docs.nvidia.com/nemoclaw/latest/user-guide/openclaw/reference/troubleshooting).

## Teardown

```bash
nemoclaw dealer destroy
```

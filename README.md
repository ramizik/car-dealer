# dealer

Hackathon agent team on Crusoe Managed Inference (Nemotron). Defines its own "done", verifies independently, loops, and keeps a shared memory.

## Run

```bash
cp .env.example .env   # add CRUSOE_API_KEY
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000
cd frontend && npm install && npm run dev   # http://localhost:3000
```

Without a key the backend runs in mock mode so the UI still works.

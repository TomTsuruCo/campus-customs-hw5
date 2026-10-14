# Campus Customs: a multi-agent shop desk (HW 5)

Five AI agents (Boss, Inventory, Accounting, Facilities, Customer Service) work three open tickets for a small campus shop. They read the shop database **only through one MCP tool server**, a FastAPI backend runs them, and a React board shows the team working. Agents can only *prepare* a payment; **a human clicks approve**, and only a human can close a ticket.

Result of the graded run: all three tickets resolved; checking went **$3,400.00 → $160.00** (rent $2,400 for ticket 102, vendor invoice $840 for ticket 101, nothing for ticket 103). The working database in this repo is left in that final state.

| Ticket | What it was | Final status | Cash change |
|---|---|---|---|
| 101 | Bulldog tee, size S, out of stock, vendor blocked by an unpaid invoice | resolved | −$840.00 |
| 102 | Rent due in two days | resolved | −$2,400.00 |
| 103 | 20 hoodies with a bulk discount; 8 in stock; no discount policy | resolved (discount declined) | $0.00 |

## Quick start

You need **Python 3.11+**, **Node 18+**, and a **Portkey API key** (to run the agents; the board, database and evidence files work without one).

```bash
git clone https://github.com/TomTsuruCo/campus-customs-hw5.git
cd campus-customs-hw5

python -m venv .venv
# macOS/Linux:  source .venv/bin/activate
# Windows:      .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # Windows: copy .env.example .env
# open .env and paste your key after PORTKEY_API_KEY=   (.env is git-ignored; never commit it)
```

## Run it

Do these in order. Steps 3 and 4 need their own terminals and stay running.

**1. Reset the database for a clean run.** The repo ships the working copy in its *final* state (all tickets resolved, checking $160), so reset before a full three-ticket run. Copy the original over the working copy (stop the backend first if it is running):

```bash
cp data/campus_customs.db data/campus_customs_new.db          # macOS/Linux
Copy-Item data\campus_customs.db data\campus_customs_new.db -Force   # Windows PowerShell
```

(The board's **Fresh desk** button and `POST /reset` do exactly the same thing.) `data/campus_customs.db` is the original and is never modified; `data/campus_customs_new.db` is the working copy the tools use. Starting checking balance after a reset: **$3,400.00**.

**2. MCP server.** Nothing to start: the backend launches `mcp_server/server.py` itself over stdio. To run or inspect it on its own: `python mcp_server/server.py`. `.mcp.json` registers it for Claude Code as `campus_customs`. Every shop fact and write goes through this server; the backend never opens SQLite.

**3. Start the FastAPI backend** (from the `backend/` folder, as the assignment specifies):

```bash
cd backend
uvicorn main:app --reload --port 8000
```

It reads `PORTKEY_API_KEY` from `.env` in the repo root and listens at http://localhost:8000.

**4. Start the React board:**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The board talks to the backend at http://localhost:8000 (the backend allows that page origin).

**5. A full three-ticket run** (after step 1's reset), in the board:

1. Pick ticket **101**, **102**, then **103**, and click **Start the team** on each (each run takes about 10 to 25 seconds).
2. For 101 and 102 the Boss prepares a payment request. In the **Signature tray** click **Approve & pay** (rent $2,400, invoice $840). Paying the rent resolves 102 automatically.
3. Close 101 and 103 with the **File as resolved** panel (a human writes the decision; agents cannot resolve tickets).
4. Checking should end at **$160.00**, matching `cash_accounts` in `data/campus_customs_new.db`.

The same thing from a terminal:

```bash
curl -X POST localhost:8000/reset
curl -X POST localhost:8000/tickets/101/run    # then 102, 103
curl -X POST localhost:8000/tickets/102/approve -H "Content-Type: application/json" -d '{"approved_by":"grader"}'
curl -X POST localhost:8000/tickets/101/approve -H "Content-Type: application/json" -d '{"approved_by":"grader"}'
curl -X POST localhost:8000/tickets/101/resolve -H "Content-Type: application/json" -d '{"resolved_by":"grader","resolution":"..."}'
curl localhost:8000/balance
```

Language-model output varies a little between runs, so the agents' wording and delegation order may differ from the recorded run.

## API routes

`GET /health` · `GET /tickets` · `POST /tickets/{id}/run` · `GET /events` · `POST /tickets/{id}/approve` · `POST /tickets/{id}/resolve` · `GET /balance` · `POST /reset` (plus an older batch route `POST /run`). Details are in `output/harness.md`.

## Where to look when grading

| File | What it shows |
|---|---|
| `output/harness.md` | Tables, MCP tools, the five agents, API routes, the dashboard, safety rules, and the Problem 9 result. |
| `output/desk_tickets.html` | Open in a browser. Per-ticket Expected (the plan) beside Actual (the real run), the **Cash** tab (itemized, ending balance matches the database), and the **Reflection** tab. |
| `output/resolved_tickets.json` | Per ticket: final status, outcome, what each agent contributed, and the human approvals. |
| `output/resolved_board.html` | Open in a browser. Screenshots of the React board for each resolved ticket. |
| `output/audit_trail.json` | Append-only log of every agent step, delegation, tool call and human decision. It also contains earlier test runs; the graded run ids are listed in `resolved_tickets.json`. |
| `output/design.md` | Why the dashboard looks the way it does. |
| `output/mcp_smoke.json` | The Problem 4 evidence that each MCP tool returns the database's values. |
| `AI_prompts.md` | The prompts used for each problem. |

## Project layout

```
.
├── AI_prompts.md          prompt log
├── README.md
├── requirements.txt       Python dependencies
├── .env.example           template (copy to .env; .env is git-ignored)
├── .gitignore
├── .mcp.json              registers the MCP server for Claude Code
├── data/
│   ├── campus_customs.db       original database (reset source)
│   └── campus_customs_new.db   working copy the tools read and write
├── mcp_server/
│   ├── server.py          the FastMCP tool server (the only code that opens SQLite)
│   └── README.md
├── backend/
│   ├── main.py            FastAPI routes
│   ├── models.py          data types
│   ├── team.py            the delegation loop across the five agents
│   ├── agents/            one file per role + the shared agent factory
│   ├── mcp_client.py      MCP client and per-role tool permissions
│   ├── audit.py           append-only audit log
│   └── prompts/           boss.md, inventory.md, accounting.md, facilities.md, customer_service.md
├── frontend/              React + Vite + TypeScript board
└── output/                harness.md, design.md, desk_tickets.html, resolved_*.{json,html},
                           audit_trail.json, mcp_smoke.json, github_url.txt
```

## Safety rules (short version)

- **MCP only:** agents get shop facts and make changes only through the MCP server.
- **Agents prepare, humans decide:** no agent can pay or resolve a ticket; the Boss only records a payment *request*, and a human clicks approve. Cash can never go below zero.
- **No outside contact:** nothing is emailed or sent; customer replies are saved as unsent drafts.
- **No invented policy:** agents use database values and the shop date only.
- **Bounded:** per-agent caps on model requests, tool calls and tokens; at most four delegations per ticket.
- **Secrets:** the Portkey key is read from the environment only, is never written to the audit log, and `.env` is never committed.

Full list: `output/harness.md`.

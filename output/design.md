# Campus Customs Dashboard: Design Notes

The dashboard is a React + Vite + TypeScript app in `frontend/`. It talks to the backend at `http://localhost:8000`, and the backend allows the Vite page origin `http://localhost:5173`.

To run it, start the backend with `uvicorn main:app --reload --port 8000` from `backend/`, then run `npm install` (once) and `npm run dev` from `frontend/`, and open http://localhost:5173.

## The idea: a desk you'd want to sit at

The page is meant to feel like a small shop's front desk, not an admin console. The person using it is a manager watching a team and signing off on money, so the screen is built around three questions: what's on my desk, what is my team doing right now, and what do I need to sign.

- A dark purple background with sweeping Yale-blue ribbons sets the mood: calm, a little premium, and clearly tied to Yale.
- Tickets are clean white note cards.
- The agents are five people at five stations on the shop floor.
- Money lives in a gold-plated cash drawer with a signature tray beside it.

I chose a physical-office metaphor over a generic card dashboard because the story of this homework is a human supervising AI staff. When the Boss delegates, specialists report back, and the human signs the cheque, the roles are obvious without a legend.

## Layout

Three columns, read left to right in the order work happens.

1. **Inbox (left).** The tickets as note cards: a type icon, ticket number, status chip, bold subject, requester, and the SKU and size in a small pill. A coloured bar on the left edge shows status (grey open, blue in progress, red blocked, amber waiting on you, green resolved). The selected card gets a blue ring and slides forward. Resolved tickets move to a "Filed away" shelf, faded and stamped.
2. **The floor (centre).** A case-file header for the selected ticket with the big "Start the team" button, then the Boss on top, a dotted "delegates to" spine, and the four specialists beneath it. Below that are "Desk chatter" (a live feed) and "What each agent did" (summaries).
3. **Money (right).** The cash drawer on top and the signature tray under it. It stays in view as the page scrolls, so the balance is visible when a payment is approved.

The header's tagline is built from the live data (for example "5 agents, 3 tickets (3 open), one human who signs the checks"), so the counts change with the real number of tickets and agents. A Yale-style badge with blue ribbon tails sits at the top right. It is a stand-in drawn for this project; an official logo file placed at `frontend/public/yale-logo.svg` is picked up automatically.

The Boss sits above the specialists because that is the real hierarchy: the Boss decides who gets called. A station for an agent that was never called stays visible but greys out as "Not needed", which makes it easy to see who was *not* sent in. That matters when comparing a run with the plan on the Problem 6 tabs.

## Ticket notes

The notes use a clean sans-serif at larger sizes (subject 1.3rem bold, details 0.95rem in a dark grey on white) instead of the earlier handwritten-paper look. The goal is that a ticket can be read at a glance from across the desk: high contrast, generous spacing, rounded corners, and one status chip in the same place on every card.

## How the agents read differently

Each agent is a little person, with its own colour, title line, and speech-bubble style, so you can tell who is talking without reading the name.

| Agent | Who they are | Colour | Bubble style | Why |
|---|---|---|---|---|
| Boss | Suit, tie, gold lapel pin, in a larger gold frame with a BOSS tag | gold | serif italic, like a memo | the decision-maker; reads as a note from the manager |
| Inventory | Ordinary worker in an orange cap | amber | monospace on dashed, tally-sheet lines | counts and SKUs |
| Accounting | Ordinary worker with round glasses | green | ruled ledger lines, double rule on the left | numbers and money |
| Facilities | Ordinary worker in a yellow hard hat | slate blue | boxed, squared-off notice | leases, rent, premises |
| Customer Service | Ordinary worker with a headset | rose | rounded chat bubble with a tail | drafts a human-sounding reply (never sends it) |

The portraits are small drawn figures made for this project. The Boss is the only one in a suit and gets a bigger portrait; every other agent wears a shirt in its own colour with a name badge, so the Boss stands apart from the "normal workers" at a glance.

An agent's status is also shown in text, not just colour: Off shift, On standby, Working, Done, Not needed, Stuck. A working agent lifts slightly, gets a glow in its own colour, and shows what it was asked and what tool it is using in plain words ("counting stock…", "reading the books…"). When it signs off, its bubble becomes its summary. The same colours carry through to the chatter feed and the summary cards.

## While a ticket runs

The backend runs a ticket in one blocking request, so the dashboard watches progress by reading the audit events (`GET /events`) about every 0.8 seconds while a run is active, and slower otherwise. Tickets and balance refresh at a slower pace. Responses are numbered so an old, slow response can never overwrite a newer one, and the live feed scrolls itself without moving the page.

- **Floor:** stations switch state as events arrive.
- **Desk chatter:** a radio-style log with a live indicator. It shows delegations ("Boss asks Inventory: …"), tool use, and each agent's report.
- **Summary:** each agent that was called gets a card with what it did, its findings, the recommended next step, and its token use. A line lists which agents were *not* called.

The backend keeps one long-lived connection to the shop's tool server for the dashboard's frequent reads. Starting a new server process for every poll took seconds and piled up processes; with a shared connection a refresh takes about 15 ms.

## How resolved tickets show up

- A ticket with a finished run shows "✓ Run complete" on its card, with the Boss's final status as the chip (In progress, Blocked, Needs your OK, Resolved).
- A **resolved** ticket gets a green rubber stamp that thuds down, fades on its card, and moves to the "Filed away" shelf. Its "Start" button is replaced by a large RESOLVED stamp in the case file.
- A ticket waiting on a human glows amber, and its button changes to "Waiting for your OK".

The dashboard shows resolved only when the stored status is resolved. The shop rules in this project let only the Boss change status, and the Boss is told not to resolve a ticket just because a draft or recommendation exists. For example, ticket 101 (out of stock, vendor owed money) ends the run "Blocked", not resolved. Rent ticket 102 becomes resolved when the human approves and pays the rent. The chip and stamp therefore always match what is true in the database.

## How cash shows up

The balance is a gold-plated "Checking" ledger on a Yale-blue drawer, with large monospace numerals, a "drawer fullness" bar, and the shop date it applies to.

- When a payment is approved the number **counts down** to the new balance over a second, a red "−$2,400.00" chip floats in, and the fullness bar shrinks. The drop should feel like money leaving the drawer.
- Each payment is listed under the balance with time, ticket, kind (rent or invoice), and amount.
- The balance shown is the real stored balance read from the backend, not a number the page calculates itself.

## The signature tray (human approval)

Agents can only *prepare* a payment. When the Boss asks for one, the tray glows and shows a cheque for that ticket with its amount and kind, a "Signing as" line for the human's name, and an **Approve & pay** button. Nothing happens until the human clicks. The amount shown is the one the Boss recorded, and the backend recomputes it before paying. A payment that would take cash below zero is refused and the page shows why.

## Creative choices, and why

- **Little people instead of icons.** The agents are staff, so they get faces. A suited Boss and ordinary workers with their own props (cap, glasses, hard hat, headset) make the hierarchy and the jobs obvious.
- **Dark purple with blue ribbons.** A dark stage makes the white note cards and glowing agents stand out, and the ribbons give the page movement and a Yale feel without adding clutter.
- **A rubber stamp for "resolved".** It is a small moment of satisfaction when work is finished, and it is unmistakable at a glance.
- **A cheque for approval.** Signing a cheque is the real-world version of "a human approves the payment", so the metaphor teaches the safety rule.
- **Agents with voices.** Five different bubble styles mean you can follow a run by shape and colour alone.
- **Greyed-out "Not needed" desks.** The page makes a good plan (don't send everyone to every ticket) visible instead of hiding it.
- **Fresh desk button.** One click resets the stored data and clears the run history from the view, so a demo can be repeated.
- **Plain-language tool names.** "Counting stock" instead of `check_inventory`; the raw tool names are available as hover text on each chip.

## Practical details

- The API address comes from `VITE_API_URL` and defaults to `http://localhost:8000`. See `frontend/.env.example`.
- If the backend is not running, the top bar says "Backend offline" and a banner shows the command to start it.
- Motion respects the "reduce motion" system setting.
- The layout collapses to a single column on narrow screens.
- `node_modules/` is large and is not committed; `npm install` creates it.

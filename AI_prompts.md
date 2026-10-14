# AI Prompts Log

## Problem 1: Vibe coder prompts

**Prompt typed:**

> Now let's start with problem 1
> Create an AI prompts log with the problem number at least one prompt I typed in my own words, one follow up prompt if needed

**Follow-up prompt:** None needed so far.

## Problem 3: FastMCP server tools

**Prompt typed:**

> problem 3
> write an MCP server in mcp_server/ using fastMCP. it will talk to data/campus_customs_new

**Follow-up prompt:**

> problem 3
> write an MCP server in mcp_server/ using fastMCP. it will talk to data/campus_customs_new.db
> You do not need to connect or run it in this problem
> Every agent in this HW uses the tools in this MCP server. You will add more tools to it later; for now write three tools you know you will need for the tickets in the database. keep the names clear. never invent any data. Only use info in the database

The first prompt named the server framework and database location; the follow-up clarified the three-tool scope, shared use by all agents, database-only grounding, and that the server should not be run yet.

**Additional follow-up prompt:**

> in output/harness.md list each of your three mcp tools. for every tool include: which table it reads, which ticket it helps unlock (101, 102, 103) and one sentence on why that tools it the right one for the ticket
> Vague lines like "reads inventory" score low - tite the tool to the ticket please.
>
> Also, add a short mcp_server/readme.md file that explains what the mcp server is for, which database file it uses, and the three tools it has.

The earlier harness notes named broad responsibilities but did not tie each tool to specific ticket IDs and their actual data.

## Problem 4: Connect and smoke-test the MCP server

**Prompt typed:**

> problem 4
>
> add the mcp server to vibe coder and test each tool
>
> in this vibe coder, we need to add the MCP server to this project so that it can call the tools. Save the connection JSPN text in mcp.json at the project root (or however the vibe coder saves local mcp server lists)
>
> With the vibe coder connected, we will test each of the three mcp tools. save the evidence in output/mcp_smoke.json. for every tools include:
>
> - the prompt you asked the vibe coder
> - the tool name
> - the tool output (must match values in data/campus_customs_new.db)

**Follow-up prompt:** None needed so far.

## Problem 5: Agent team, expanded MCP tools, and audit trail

**Prompt typed:**

> problem 5
> build the agent team and grow the mcp tools
> Build the agentic team for campus customs using pydatntic AI: boss, inventory, accounting facilities, andcustomer service. include prompts, models, and agent loops so they can delegate work to each other with full connectivity. 
> Put theagebr prompts in backend/prompts/ - one file per agent. put data types in backend/models.py, and the agent files under backend/ (your layout can vary as long as the five roles are clear) use your portkey API key and only gpt 6 luna for each agent. 
>
> I was told to Write each prompt in my own words with the shop rules that agent needs. more detailed prompts that cover all aspects of an agents work and scope score higher than short generic prompts.
> add any tools the agents need to your mcp server so they can work on the open tickets. shop facts come from the mcp server over data/campus_customs_new.db
> do not invent a second shop tools later that bypasses MCP
>
> Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step record enought to audit later. append to this file - do not wipe each run
>
> in output/harness.md list each agent and each mcp tool (including ones you add in this problem) along with which table the tools uses. also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check.
> Update mcp_server/readme.md

**Follow-up prompt:** None so far.

Implementation note: The Portkey credential is read from `PORTKEY_API_KEY` at runtime and is not copied into source or prompts. No agent or model was run while building this problem.

## Problem 6: Expected ticket plans

**Prompt typed:**

> Problem 6
>
> before we wire the backend write down what you expect the team to do on every open ticket. Build output/desk_tickets.html - a page you can double click with one tab per ticket (101, 102, 103).
>
> Also, add empty cash and reflection tabs for later probelms but leave them blan or with short "coming later" note for now.
>
> On each ticket tab, fill an expected section only (leave room for an actual section you will fill after you run the agents).
>
> For each ticket's expected section, write in your own words:
>
> - who the boss should call first and why
> - All the agent delegations you expect - not boss calls everyone
> - Which MCP tools you expect that run to use
>
> Plans that send every specialist on every ticket score low. You will compare this plan to what actually happens when your agents resolve the three tickets

**Follow-up prompt:** None so far.

## Problem 7: Backend routes

**Prompt typed:**

> problem 7
> Backend routes
> Our react frontend dashboard in the next problem needs a backend it can call. in backend.main.py, we need to use FastAPI and add routes that do the following
> - Return the three tickets and whether each is open or resolved.
> - Take a ticket ID and run your agent team on that ticket
> - Return recent agent events - what each agent said and which tools they used - so the board can refresh
> - Approve a payment or purchase after human clicks approve (agents only prepare pay; this route is what actually changes cash)
> - Return the current checking balance from cash_accounts
> - Reset the database to the original values when you want to try a fresh run
>
> From the backend/ folder start the server with: uvicorn main:app --reload --port 8000
> This turns on your backend at http://localhost:8000 so the frontend dashbpard can call those routes.
> In output/Harness.md list each route in one line (what URL / what it does)

**Follow-up prompt:** None so far.

Implementation note: Codex stopped on this problem with a Portkey error, so the work was finished in Claude Code. The routes call new human-only MCP tools instead of opening SQLite, so the "no bypass of MCP" rule still holds. Testing included one real agent run on ticket 101, which exposed three problems that were fixed: the per-agent token cap was too small, the gateway did not pass `actor` to `update_ticket_status`, and a refused tool call ended the whole run instead of being reported back to the agent.

## Problem 8: Agent dashboard

**Prompt typed:**

> Problem 8
> Agent Dashboard
> Build the frontend dashboard in frontend/  with react + vite + typescript.
> The Page should call the routes we built in problem 7. at minimum the board should
> 1. List three tickets
> 2. let you pick one ticket and start the agent team on it
> 3. show each agent and what they are saying / doing while the tickets run
> 4. Mark a ticket resolved when the run finishes
> 5. show a short summary of what each agent did on the ticket
> 6. let a human approve a pay or purchase when asked
> 7. Show the checking balance (it should drop after an approved pay)
>
> make the dashboard look good. be creative with the layout and feel. This is a real desk that people would want to sit at, so put thought into how it looks.
>
> Tell the front end to talk to the backend at http://localhost:8000
> on the backend, allow the vite page origin (usually http://localhost:5173) so the browser is allowed to start board with npm run dev
>
> write output/design.md with what you chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why - including the creative choices that make it feel special and something humans would actually enjoy using.

**Follow-up prompt:** None so far.

Implementation note: Built in Claude Code after Codex stopped at Problem 7. Testing the dashboard in a browser found fixes in the backend too: the Boss now gets output retries, read-only dashboard polling is no longer written to the audit log, and the audit events carry the Boss's recommended status and token usage.

## Problem 9: Resolve the tickets

**Prompt typed:**

> We need to resolve the tickets
> Before testing the agents on a full run over the three tickets, we need to reset the working database data/campus_customs_new.db again so we can start clean.
> Note the starting checking balance. then run all three tickets on the board 101, 102, 103, until each one is resolved.
> Open output/desk_tickets.html from problem 6. on each ticket tab, fill the actual section from this run: which agents worked, what they delegated, and which tools they used. Keep expected section so you can compare the two.
> On the cash tab of the same output/desk_tickets.html itemize the money: starting checking balance after the reset; for each ticket: how cash changed when that ticket resolved and why (which pay/purchase, dollar amount); ending checking balance - it must match cash_accounts in the working database.
> Wrong cash math loses points even if the board shows every ticket resolved.
> Also save: output/resolved_tickets.json (for each ticket: ID, final status, short outcome, what each agent contributed, and any human approvals); output/resolved_board.html (a page you can double-click with a screenshot of your react board for each resolved ticket 101, 102, 103).
> Append real runs to output/audit_trail.json.
> Finish output/harness.md so it covers tables, mcp tools, the five agents, API routes, the dashboard, any safety rules.

**Follow-up prompts:** Asked in chat which payments to approve and how to resolve ticket 103, I answered "Approve both" (rent $2,400 for 102 and invoice 501 $840 for 101) and "Decline discount" for 103.

Implementation note: Built in Claude Code. The first test run showed the agents stopped without asking for money, so the Boss prompt was extended to file the payment request itself, and Inventory was told to always check vendor shipping blocks. A human-only resolve action was added (MCP tool, route, and dashboard panel) because agents may not resolve tickets. Tool calls were also given run ids so the audit trail can attribute them. Two earlier exploratory runs are also in the audit trail; the final run ids are listed in output/resolved_tickets.json.

## Problem 10: Reflection

**Prompt typed:**

> Problem 10 reflection
> Open output/desk_tickets.html and fill the reflection tab. Answer in your own vibe and be detailed and thorough:
> - How would you evaluate the performance of the agents on each ticket and why
> - For each ticket how did actual compare to the expected plan wrote earlier
> - what would have been simpler as one agent with tools and why
> - describe three new problems campus customs might face that this agent team could solve with the tools we built
> - describe three new problems campus customs might face that this agent team could not solve with the tools built and explain the tools and agents you would need to solve them
> Tie every answer to this app and the three tickets you ran - use the ticket tabs and cash tab on the same page as your evidence. Don't be generic make the essay creative so we score high

**Follow-up prompt:** (see below)

Follow-up prompt: After seeing a first draft, I said I would put it into my own words, rewrote the whole reflection myself, and pasted it back to have it placed in the Reflection tab.

Implementation note: The first draft was generated in Claude Code from the real run (token counts, tool calls, and cash figures read from output/audit_trail.json and the working database). The text now in the Reflection tab is my rewrite of it; Claude Code only placed it on the page and added the scorecard table and token charts as supporting evidence.

## Problem 11: Push to GitHub

**Prompt typed:**

> We need to push it to GitHub.
> Push the work and code to a public github repo so graders can clone it and grade. I need to submit the URL to Canvas. Also put it in output/github_url.txt
> Do not push the real env file to github. Include database files under data/ (the original and the work copy) so graders can run the app easily.
> (The prompt also gave an expected file layout for the repo and said the README should explain: copy the original DB to the working copy when you need a clean run, start the MCP server, start the FastAPI backend, start the React board, and reset the DB before a full three-ticket run.)

**Follow-up prompt:** None so far.

Implementation note: Built in Claude Code. The repo is public at https://github.com/TomTsuruCo/campus-customs-hw5. The real .env is not included (only .env.example); the original and working databases are, with the working copy in its final resolved state. Before publishing, every file was scanned for the API key and personal paths, commits use my GitHub no-reply email, and a fresh clone was built and run end to end as a grader would.
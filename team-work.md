# Safar — 1-Day Hackathon Battle Plan

**Event:** Himshikhar Hackathon 2026 (Masai) · **Topic:** Multi-Agent Trip Planner
**Team:** 4 · **Lead:** mr.jarvis0 · **Members:** adi, sush, rishu
**Build window:** 31 Aug, **10:00 AM → 9:00 PM (~11 hours)** · **Submit:** 31 Aug 9–10 PM
**Presentation:** 1 Sep, 8–10 PM (Industry Mentors)

---

## 0. The rubric decides everything

| Metric | Pts | What we do about it |
| --- | --- | --- |
| **Working Product** | **40** | Build a small slice that **runs end-to-end**, live, no crash. Mock data so it never breaks. |
| **Understanding (Q&A)** | **30** | All 4 must explain the architecture + *why multi-agent* + how negotiation works. Shared Q&A sheet. |
| **UX & Creativity** | **20** | Clean UI: 3 plans side-by-side, clear Approve/Modify, show the "why". |
| **Presentation** | **10** | 5-slide deck: problem → why agentic → diagram → live demo → roadmap. |

**Golden strategy:** *Small but real, beats big but broken.* We build the **MVP loop only**, make
it reliable, and pitch the full 27-agent architecture as **"designed & roadmapped."**

---

## 1. Locked tech stack (for speed + reliability)

- **Language:** Python (one language for the whole team → no context switching).
- **UI:** **Streamlit** — fastest way to a good-looking interactive UI in pure Python. (UX = 20 pts.)
- **Data:** **Real APIs (team-provided)** behind a **Tool Gateway** — the lead supplies the keys.
  Every response is **cached**, plus a **mock JSON fallback** (e.g. `data/tokyo.json`) so the
  **live demo runs even if an API is down or slow**.
- **Intelligence:** **One LLM** behind a single `llm(prompt)` wrapper (team-provided key). LLM
  does the *reasoning* (ranking, negotiation); a **mock fallback** kicks in on any network blip.
- **Orchestration:** a simple Python loop (LangGraph optional — a plain function loop is fine and
  faster to debug in 1 day).
- **Secrets:** all keys live in a **`.env` file that is git-ignored — NEVER committed** to the
  repo (the repo is on GitHub; a leaked key gets abused/auto-revoked). Code reads keys via
  `os.getenv(...)`.

> Rule: **real APIs for real data, but always cache + keep a mock fallback** so the on-stage demo
> can never crash.

---

## 2. Scope — what we BUILD vs what we PITCH

**BUILD (the demo):** single traveler · 1 destination · **Flight + Hotel + Activity** agents ·
**Budget** tool · **Negotiator** (3 candidates: Saver/Comfort/Balanced) · **Validator** (hard
constraints) · **Human Approval** gate (Approve/Modify/Replan). *This alone shows all 4 required
properties: task-division · negotiation · conflict-resolution · human-approval.*

**PITCH ONLY (roadmap slide):** visa/health/safety, on-trip copilot, booking, group travel, the
full 27-agent map (from `readme.md`). Say "designed, next phase" — don't build under time pressure.

---

## 3. Who does what (1-day)

### 🧑‍✈️ mr.jarvis0 (Lead) — Spine + Integration + Pitch + Q&A
- **Before kickoff:** secure the LLM **API key**, agree contracts on paper, set up repo access.
- **On the day:** build the **Orchestrator** (loop: intake → agents → negotiator → validator →
  approval), the **`llm()` wrapper**, and **integrate** everyone's modules. Keep `main` running.
- Own the **`TripState`** object + folder skeleton so all 3 code to the same interface.
- Prep the **pitch deck** + **Q&A cheat-sheet** (Q&A = 30 pts!). Book & attend **mentor slots**.
- Owns: `orchestrator/`, `state/`, `llm/`, integration, `deck/`.

### 🔌 adi — Agents & Data
- **Mock data**: `data/tokyo.json` — ~5 flights, ~5 hotels, ~8 activities (price, time, rating,
  tags). This is the fuel for the whole demo.
- **3 agents**: Flight, Hotel, Activity — each takes the mock options + user prefs → calls
  `llm()` to **rank & explain** → returns scored options in the shared format.
- **Budget tool**: pure function that totals a plan's cost.
- Owns: `agents/`, `tools/`, `data/`.

### 🧠 sush — Negotiation & Validation (our winning differentiator)
- **Conflict detection** (cheap vs comfort, time vs experience) + **utility scoring**.
- **3 candidates**: Saver / Comfort / Balanced (from readme §8) + a one-line "why" for each.
- **Validators**: budget ≤ limit, times don't overlap, check-in after arrival (readme §9).
- Owns: `engine/negotiation.py`, `engine/validation.py`. Turn readme §8.6 pseudocode into code.

### 🎨 rishu — Streamlit UI (what judges see — 20 pts)
- **Intake**: form for destination, days, budget, interests, pace.
- **Candidates**: 3 plans **side-by-side** (columns) with cost / comfort / walking / risk badges.
- **Approval gate**: **APPROVE / MODIFY / REPLAN** buttons; Modify = change budget/pace → re-run.
- **Explainability**: show *why* (which agent, which trade-off), confidence, cost.
- Owns: `app.py` (Streamlit) + `ui/`.

---

## 4. Hour-by-hour (31 August)

| Time | What | Who |
| --- | --- | --- |
| **10:00–10:30** | Kickoff. Scaffold repo skeleton + contracts + mock-data shell. Everyone branches. | Lead + all |
| **10:30–1:00** | **Parallel build vs mocks.** adi: data+agents · sush: negotiator+validators · rishu: UI shell+intake · lead: orchestrator+`llm()`. | All |
| **1:00–2:00** | **Mentor Slot 1** (lead + 1). First integration attempt (loop runs on mocks). | Lead |
| **2:00–3:00** | Connect orchestrator → agents → negotiator → UI. Get a rough **end-to-end**. | Lead + rishu |
| **3:00–5:00** | Real `llm()` calls in agents + negotiator. UI: candidates + approval gate. **Mentor Slot 2** (~20 min). | All |
| **5:00–6:00** | **Full loop works end-to-end.** Wire the Modify/Replan loop. | Lead + sush |
| **6:00–8:00** | Polish UX, add fallback (demo can't crash), **freeze features**. **Mentor Slot 3**. | rishu + all |
| **8:00–9:00** | Rehearse demo, finalize deck, **prep Q&A answers**, bug buffer. | All |
| **9:00–10:00** | **Verify + SUBMIT.** | Lead |

---

## 5. Before kickoff (29–30 Aug) — get READY, don't build

Rules say work begins at kickoff (10 AM, 31 Aug). So *before* that we only **prepare** (100% fair):
- Lead: get the **LLM API key**, confirm repo access for all 4.
- Everyone: install Python + Streamlit; run one "hello world" Streamlit app + one `llm()` call.
- Read `readme.md` §5, §8, §10 so the architecture is **cold** in everyone's head (Q&A = 30 pts).
- Agree the `TripState` fields + mock-data shape **on paper** so Day 1 is pure execution.

---

## 6. Q&A prep (30 points — do NOT skip)

Every member must be able to answer, in their own words:
1. **Why multi-agent** (not one prompt)? → task division + agents disagreeing → negotiation.
2. **How does negotiation work?** → conflicts typed → utility score → 3 Pareto candidates.
3. **Where's the human?** → approval gate; nothing final without a human "yes".
4. **What's real vs roadmap?** → MVP loop is live; the 27-agent map is the vision.
5. **Their own module** → each owner explains their part cold.

Keep a shared `qa.md` with these answers. Rehearse once at 8 PM.

---

## 7. Git workflow

- Branches: `feat/core-jarvis`, `feat/agents-adi`, `feat/engine-sush`, `feat/ui-rishu`.
- Small commits → lead merges → `main` always runs.
  ```bash
  git add -A && git commit -m "message" && git push
  ```
- Repo: https://github.com/mrjarvis0/safar.ai

---

## 8. Anti-panic rules

- **Mock first, LLM second, real APIs never** (for this hackathon).
- If something's not working by 6 PM → **cut it**, show the loop that works.
- The demo must run **offline / on mock data** — never depend on live network on stage.
- One person (lead) owns the **submit**; verify at 8:45 PM, not 9:59 PM.

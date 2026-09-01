# Deploying Safar (Phase 3c)

Safar runs three ways, smallest → largest. **Every step is opt-in**: with no keys
and no services, the app runs fully on SQLite + an in-process bus + mock inventory
+ a simulated booking saga. You only add infrastructure when scale actually
demands it (readme §15).

> **Money & safety.** Nothing here captures a payment. Booking stays in
> `simulate` mode until you explicitly set `SAFAR_BOOKING_MODE=live` **and** supply
> PSP keys — and even then Safar only *authorizes* an order and hands checkout to
> a human. Capture and refund require an explicit human confirmation in the UI;
> Safar never captures money autonomously and never sees card data (readme §13).

---

## 1. Local (no Docker)

```bash
pip install -r requirements.txt
streamlit run app.py            # http://localhost:8501
```

State lives in `data/safar.db` (SQLite). This is the right default at MVP scale.

## 2. Single container

```bash
docker build -t safar .
docker run --rm -p 8501:8501 --env-file .env safar
```

Still SQLite inside the container (mount a volume at `/app/data` to persist it).

## 3. Full stack — app + Postgres + Redis

```bash
docker compose up --build       # http://localhost:8501
```

Compose sets `DATABASE_URL` (Postgres) and `REDIS_URL` for you. `safar.store`
detects `DATABASE_URL` and talks to Postgres instead of SQLite — **same call
sites, same schema**. If Postgres is ever unreachable, the store logs a warning
and falls back to SQLite rather than crashing.

---

## Going live (real bookings + payments)

All configured in `.env` (see `.env.example`). Each is independent.

| To enable | Set | Notes |
| --- | --- | --- |
| Live flight **prices** | `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET` | Free self-service test tier works; prices are mock until set |
| Live flight **booking** (PNR) | above + `AMADEUS_BASE_URL=https://api.amadeus.com` + `SAFAR_BOOKING_MODE=live` | Real Flight Create Orders; needs **your** production Amadeus contract + traveler details (human-supplied) |
| Payments | `PAYMENT_PROVIDER=razorpay\|stripe` + that provider's keys | Safar creates the order; a human completes hosted checkout; capture is human-confirmed |
| Postgres | `DATABASE_URL=postgresql://…` | `pip install -r requirements-prod.txt` for the driver |
| Redis | `REDIS_URL=redis://…` | shared cache / rate-limit (future gateway backend) |
| Bus / train inventory | `REDBUS_*` / `RAIL_*` | partner/paid aggregators; deterministic mock otherwise |

### The live booking flow (what actually happens)

```
approve plan → booking.execute(mode=live)
  → create payment ORDER (authorize only — ₹0 moves, no card data)
  → re-price + book the flight  → real PNR
  → hotel/transfer/activity held
  → STOP at AWAITING_PAYMENT
      ↓ (human opens the PSP's hosted checkout and pays)
  → confirm_payment(human_confirmed=True)  → capture → BOOKED
```

`booking.confirm_payment(...)` and `booking.refund(...)` refuse to run without
`human_confirmed=True` — the safety rule is enforced in code, not just docs.

### KYC / legal (not a code task)

Real payment capture and ticket issuance require a merchant account (Razorpay/
Stripe KYC), an Amadeus production agreement, and — for issuing tickets —
IATA/consolidator arrangements, plus a DPDP/GDPR data program (readme §19). That
is business/legal work; the code is ready to plug into it.

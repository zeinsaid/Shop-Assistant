---
business: The Plug Business Center
location: Asomatou 9, Egkomi, Lefkosia 2414, Cyprus
currency: EUR
last_reviewed: 2026-09-28
---

# The Plug: Knowledge Base

Each entry has an ID the bot cites when answering.

- **Visibility:** `public` entries may be told to customers. `internal` entries guide the bot's behaviour but must never be revealed to customers.
- **Status:** `placeholder` means approximate figures or details still to be filled in from the shop's real records. `confirmed` means checked.

---

## Shop basics

### shop-hours
**Visibility:** public · **Status:** confirmed

We're open 24 hours a day, 7 days a week.

### shop-hours-holidays
**Visibility:** internal · **Status:** confirmed

The shop may occasionally close for holidays. If a customer asks about a specific holiday or date, use `ask_owner` rather than assuming we're open.

### shop-location
**Visibility:** public · **Status:** confirmed

Address: Asomatou 9, Egkomi, Lefkosia 2414, Cyprus.

We're in Engomi, next to the University of Nicosia, right behind the Mall of Engomi, just off October 30th Street. We're next to the Sirius Black coffee shop, which is also a barber shop called WizArt. Look for the shop with tables outside and a large LED screen out front.

### shop-sending-files
**Visibility:** public · **Status:** placeholder

You can send files to print by WhatsApp, Viber or email. (Contact details to be added; until then, don't give out numbers or addresses.)

### shop-payment
**Visibility:** public · **Status:** confirmed

We accept card and cash. Bank transfer is possible for some orders; arrange it with staff.

### turnaround-standard
**Visibility:** public · **Status:** confirmed

Most jobs we do in-house are ready the same day or the next day. If you need something urgently, ask and we'll do our best to have it ready the same day. DTF shirt prints take at least 3 working days.

### turnaround-internal
**Visibility:** internal · **Status:** confirmed

Staff can almost always finish in-house jobs the same day, but keep a day or two of leeway so they aren't printing until 2 a.m. The bot must never promise same-day completion; if a customer needs a job the same day, use `ask_owner`.

### shop-payment-timing
**Visibility:** public · **Status:** confirmed

Small jobs are paid when you pick them up. For large orders we usually take half upfront (or the full amount, if you prefer).

### shop-payment-internal
**Visibility:** internal · **Status:** confirmed

Staff print small jobs in advance for regulars they know. For customers they don't know, small jobs are printed once the customer arrives at the shop, because unpaid prints are often never collected. The bot can't tell who is a regular, so if a customer asks us to have a job printed and ready before they arrive, use `ask_owner`.

### shop-print-from-usb-phone
**Visibility:** public · **Status:** confirmed

You can bring files on a USB stick and we'll print from it. From a phone, send the files to us by WhatsApp, Viber or email.

### shop-wifi
**Visibility:** public · **Status:** confirmed

We have free Wi-Fi in the shop. Ask staff for the password when you're here.

### shop-delivery
**Visibility:** public · **Status:** confirmed

We don't deliver printing or stationery; orders are collected from the shop. (Mini-market items are available for delivery on Wolt and other delivery platforms.)

### shop-invoices
**Visibility:** public · **Status:** confirmed

We can provide receipts and invoices, for example for students claiming expenses.

### shop-greeting
**Visibility:** public · **Status:** confirmed

For greetings and small talk ("hi", "hello", "good evening"), greet the customer back briefly and ask how we can help.

### scope-general
**Visibility:** public · **Status:** confirmed

This chat handles The Plug's printing, scanning, finishing, merchandise and stationery. For anything else, politely say it's outside what we can help with here.

---

## General policies

### policy-pricing-approach
**Visibility:** public · **Status:** confirmed

All prices are guides; the final price is confirmed by staff when the order is placed.

- **Simple jobs** (one service with a known quantity, size and colour, e.g. "100 black & white A4 pages"): give the estimated total and the rate used.
- **Jobs missing details** (e.g. "how much is a booklet?"): ask for what's needed (number of pages, size, colour, paper, finishing) and give the relevant rates meanwhile.
- **Custom or effort-heavy jobs**: give "from" prices or ranges and say staff will confirm.

### policy-effort-pricing
**Visibility:** internal · **Status:** confirmed

Pricing reflects staff effort. Jobs that only need to be sent to the printer are cheap. Anything needing editing, design work, manual cutting or assembly costs more and is priced case by case. If a request needs editing or design work, don't quote it; use `ask_owner`.

### policy-discounts
**Visibility:** internal · **Status:** confirmed

Staff sometimes lower prices for large or labour-heavy jobs (for example large manual scanning jobs, bulk photos, bulk shirts) or waive small charges as goodwill. The bot never offers or agrees to discounts itself. If a customer asks for a better price, use `ask_owner`.

### policy-collect-details
**Visibility:** internal · **Status:** confirmed

Before escalating a quote for a custom or bulk job to the owner, first collect the details staff would need anyway (quantity, size, design, colours, sides, paper, deadline). Then use `ask_owner` with those details included, so the owner can answer in one reply.

### policy-internal-info
**Visibility:** public · **Status:** confirmed

We don't share supplier names, supplier prices or other internal business details.

### policy-we-try
**Visibility:** internal · **Status:** confirmed

For requests not covered here (unusual paper, a customer's own paper, banners, items we don't make in-house), never say no. Tell the customer we'll check and get back to them, and use `ask_owner`. Never mention outsourcing.

---

## Standard printing (A4 / A3)

### print-per-page
**Visibility:** public · **Status:** confirmed

Printing is charged per printed page, not per sheet. A double-sided sheet counts as two pages.

### print-a4-bw
**Visibility:** public · **Status:** placeholder

A4 black & white: €0.20 per page for up to 10 pages, €0.10 per page above 10 pages, and down to around €0.08–0.09 per page for very large jobs (200–300+ pages).

### print-a4-colour
**Visibility:** public · **Status:** placeholder

A4 colour: €0.50 per page for up to 10 pages, €0.40 per page above 10 pages, €0.30 per page above 50 pages.

### print-a3-bw
**Visibility:** public · **Status:** placeholder

A3 black & white: from €0.50 per page for small quantities, down to around €0.30–0.40 per page for large quantities.

### print-a3-colour
**Visibility:** public · **Status:** placeholder

A3 colour: from €1.00 per page for small quantities, down to around €0.60 per page for large quantities.

---

## Paper options (A4 / A3)

### paper-special
**Visibility:** public · **Status:** placeholder

Besides plain paper, we print A4 and A3 on thicker paper up to 300gsm (glossy or matte), plus specialty papers such as tracing paper and coloured paper.

Special paper adds €0.30–0.50 per sheet on top of the normal per-page printing price. Example: 10 single-sided black & white pages at €0.10 each, plus a €0.40 paper surcharge per sheet, comes to €0.50 per sheet, so €5.00 in total.

---

## Large format printing (A2 and above)

### print-large-format
**Visibility:** public · **Status:** placeholder

We print A2, A1 and A0, in black & white or colour, on paper from 80gsm (plain) up to 180gsm (heavyweight, the thickest we offer for large format). Price depends on size, colour and paper weight. Guide prices:
- A2 black & white on plain paper: from €5
- A2 colour on heavyweight paper: up to around €9
- A0: from around €9, up to €15–20 for colour on heavyweight paper

Prices for A1 and for specific size/paper combinations are confirmed by staff.

---

## Business cards and ID photos

### business-cards
**Visibility:** public · **Status:** placeholder

Business cards are priced by quantity: 100 cards for €20, 250 cards for €40. Double-sided cards are priced as double the quantity (e.g. 125 double-sided cards are priced as 250 cards). Prices for other quantities are confirmed by staff.

### passport-photos
**Visibility:** public · **Status:** placeholder

We do passport and ID photos. (Price to be added; until then, staff confirm it.)

---

## Stickers

### stickers-precut
**Visibility:** public · **Status:** confirmed

Pre-cut sticker sheets: €3 per sheet. We charge per sheet, not per sticker. How many stickers fit on a sheet depends on the pre-cut layout, from 1–2 large stickers up to around 50 small ones.

### stickers-custom-cut
**Visibility:** public · **Status:** confirmed

Custom-cut stickers (any shape): €5 per sheet. These are printed and then cut on a cutting machine, which takes more time.

---

## Finishing

### binding
**Visibility:** public · **Status:** placeholder

Binding: from €2.50 for a thin document, rising to €3, €4 and up to €5 for a very thick book. Larger bindings take more work.

### binding-waiver
**Visibility:** internal · **Status:** confirmed

For larger orders (printing over roughly €20), staff often give binding for free as a goodwill gesture, presented to the customer as a gift once the order is done. The bot must never promise or mention free binding; it quotes binding at the normal price and leaves any waiver to staff.

### lamination
**Visibility:** public · **Status:** placeholder

We laminate. Lamination is charged separately, on top of the normal printing price. (Lamination price to be added; until then, staff confirm it.)

### booklets
**Visibility:** public · **Status:** confirmed

We make booklets (folded and stapled in the middle, with an optional thicker cover). Price depends on the job. Simple booklets from a ready-to-print document on plain paper are straightforward; thick covers or documents that need preparing take more work and are quoted by staff.

### hardcover
**Visibility:** public · **Status:** placeholder

We make hardcover bound books. The hardcover costs around €30 on top of the normal printing price for the pages inside. Hardcovers take longer than regular jobs; staff confirm the timing.

### hardcover-sourcing
**Visibility:** internal · **Status:** confirmed

Hardcovers are outsourced. Don't mention this to customers.

---

## Editing and design

### editing
**Visibility:** public · **Status:** confirmed

We do photo editing and design work (Photoshop). Price depends on the job and how long it takes, so staff quote it case by case.

### editing-internal
**Visibility:** internal · **Status:** confirmed

Editing prices vary heavily between jobs and staff. The bot never estimates an editing price; any editing price question uses `ask_owner`.

---

## Scanning

### scanning
**Visibility:** public · **Status:** placeholder

- Manual scanning (single items like passports or IDs, bound books, anything that has to be placed and flipped by hand): €0.50 per page.
- Automatic scanning (loose stacks of documents fed through our document scanner): around €0.10 per page.

### scanning-large-jobs
**Visibility:** internal · **Status:** confirmed

For large manual scanning jobs, staff are willing to go below the per-page price (for example, a 100-page book at €0.50/page = €50 might be done for €20–30). The bot quotes the normal price and never offers this; if the customer pushes back on price, use `ask_owner`.

---

## Photos

### photo-prints
**Visibility:** public · **Status:** confirmed

Photo prints on photo paper: €0.50 per print for 15×10 cm, €1.00 per print for 15×20 cm. Discounts are available for large quantities.

### photo-prints-bulk
**Visibility:** internal · **Status:** placeholder

For large photo orders, prices can go down to around €0.25 (15×10) and €0.80 (15×20). The exact bulk price is decided by staff; the bot says discounts are available and escalates.

---

## Merchandise

### merch-keychains
**Visibility:** public · **Status:** placeholder

Custom keychains: around €8–10 depending on the design. We have many designs available; staff can show you the full catalogue in the shop.

### merch-catalogue
**Visibility:** internal · **Status:** confirmed

Staff show customers the supplier's customer-facing catalogue (the version without supplier prices). Never share supplier names, links or supplier prices.

### merch-shirts
**Visibility:** public · **Status:** placeholder

Custom t-shirts:
- Sublimation or vinyl: around €15 per shirt, up to €20 for double-sided or complex designs
- DTF prints: €20–25 per shirt, depending on print size and whether it's double-sided; takes at least 3 working days

Discounts are available for orders of 10 or more shirts.

### merch-shirts-bulk
**Visibility:** public · **Status:** confirmed

For bulk shirt orders, we'll need a few details before giving a quote: how many shirts, whether they all have the same design, the design size and number of colours, front only or front and back, shirt colours and sizes, and when you need them. Staff then confirm the price and any bulk discount.

### merch-shirts-sourcing
**Visibility:** internal · **Status:** confirmed

DTF prints are outsourced and then heat-pressed in the shop. Don't mention outsourcing to customers. The exact bulk discount for 10+ shirts is decided by staff.

---

## Stationery

### stationery
**Visibility:** public · **Status:** placeholder

We sell stationery, including USB sticks, calculators, pens, highlighters, erasers, notebooks (including notebooks with thicker paper), folders, binders, poster boards, canvases, paint, and tracing paper (sheets and rolls). (Full stock list to be added from the shop's system.)

### stationery-internal
**Visibility:** internal · **Status:** confirmed

Stock changes daily, so say "we usually stock…" rather than guaranteeing availability. Customers use loose names (a "blank book" or "sketchbook" may mean a notebook), so match by meaning. Questions about specific brands or models, or exact quantities in stock, use `ask_owner`.

---

## Outside the print shop

### scope-mini-market
**Visibility:** public · **Status:** confirmed

For snacks, drinks and other mini-market items, check our store on Wolt or other delivery platforms, where you can see what we have in stock. (Stationery questions are answered here.)

### scope-smoothie-bar
**Visibility:** public · **Status:** confirmed

The smoothie bar next to us is run separately by its own team. For their menu or anything else about it, please ask them directly. It's worth a try!

### scope-internal
**Visibility:** internal · **Status:** confirmed

The bot doesn't handle the mini-market (other than stationery) or the smoothie bar. Answer only from the scope entries above and don't escalate these questions to the owner.

"""Przygotowanie danych do dashboardu Yestersen Urodziny + Black Week 2026.

Użycie:
  python3 prep.py <transactions.csv> <ads_ids.csv> <sublime.csv> <out_dir>

- transakcje: eksport CMS (średniki, polskie liczby). Usuwane są dane kupujących
  (e-mail, imię, nazwisko, telefon, adresy) - do dashboardu trafia tylko to, co liczymy.
- grupy produktów: arkusz "Ads IDs" (kolumna 1 = nazwa grupy, kolumna 2 = lista ID).
- Sublime: eksport kampanii; każda kampania dostaje grupę produktów wg mapy CAMPAIGN_GROUP.
"""
import csv, json, re, sys, os
from datetime import datetime

tx_path, ids_path, sub_path, out_dir = sys.argv[1:5]
history_paths = sys.argv[5:]  # opcjonalnie: dłuższe raporty transakcji jako historia klientów
os.makedirs(out_dir, exist_ok=True)
CODE = open(os.path.abspath(__file__), encoding="utf-8").read()

PERIODS = [("Urodziny", "2026-11-17", "2026-11-23"), ("Black Week", "2026-11-24", "2026-12-01")]
EXCLUDED_STATUS = re.compile(r"CANCEL|RETURN|REFUND|REJECT", re.I)
SAMPLE_RE = re.compile(r"wzornik|próbnik|probnik", re.I)  # mikrokonwersje


def num(s):
    if s is None:
        return 0.0
    s = str(s).replace(" ", "").replace(" ", "").replace(",", ".").strip()
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def period_of(day):
    for name, a, b in PERIODS:
        if a <= day <= b:
            return name
    return None


# ---------- historia klientów (e-mail -> zamówienia) ----------
# E-mail służy tylko do porównania i nie trafia do plików wyjściowych.
# Zakupy gościa dostają w CMS nowe ID użytkownika, więc "Order count" ich nie łączy.
history = {}
for hp in [tx_path] + history_paths:
    with open(hp, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            e = (r.get("Buyer's email") or "").strip().lower()
            o = (r.get("Order ID") or "").strip()
            if e and o:
                history.setdefault(e, {})[o] = (r.get("Order paid date") or "").strip()


def is_returning(r):
    if num(r.get("Order count")) > 1:
        return True
    e = (r.get("Buyer's email") or "").strip().lower()
    me, when = (r.get("Order ID") or "").strip(), (r.get("Order paid date") or "").strip()
    return any(o != me and d and d < when for o, d in history.get(e, {}).items())


# ---------- transakcje ----------
rows = []
with open(tx_path, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f, delimiter=";"):
        if not r.get("Transaction ID"):
            continue
        paid = (r.get("Order paid date") or "").strip()
        day = paid[:10]
        status = (r.get("Transaction status") or "").strip()
        returned = bool((r.get("Transaction return completed date") or "").strip())
        price = num(r["Product price"])
        regular = num(r["Product current regular price"])
        rows.append({
            "transaction_id": r["Transaction ID"].strip(),
            "order_id": r["Order ID"].strip(),
            "product_id": r["Product ID"].strip(),
            "product": r["Product name"].strip(),
            "vendor": r["Vendor name"].strip(),
            "day": day,
            "time": paid[11:16],
            "period": period_of(day) or "Poza okresem",
            "sample": bool(SAMPLE_RE.search(r["Product name"] or "")),
            "counted": (not EXCLUDED_STATUS.search(status)) and not returned and period_of(day) is not None and not SAMPLE_RE.search(r["Product name"] or ""),
            "status": status,
            "gmv": round(price, 2),
            "regular_price": round(regular if regular > 0 else price, 2),
            "code_discount": round(num(r["Product discount"]), 2),
            "gain": round(num(r["Total gain"]), 2),
            "delivery": round(num(r["Delivery price"]), 2),
            "classification": (r.get("Product classification") or "").strip(),
            "category": re.sub(r"\s*\[\d+\]\s*$", "", (r.get("Product category level 1") or "").split("|")[0].strip()) or "Brak",
            "category2": re.sub(r"\s*\[\d+\]\s*$", "", (r.get("Product category level 2") or "").split("|")[0].strip()) or "(bez podkategorii)",
            "category3": re.sub(r"\s*\[\d+\]\s*$", "", (r.get("Product category level 3") or "").split("|")[0].strip()) or "(bez podkategorii)",
            "discount_code": (r.get("Discount code") or "").strip(),
            "returning": is_returning(r),
            "b2b": (r.get("B2B") or "").strip() == "1",
        })

# ---------- grupy produktów z kampanii ----------
groups = {}
with open(ids_path, encoding="utf-8-sig", newline="") as f:
    rd = csv.reader(f)
    next(rd, None)
    for line in rd:
        if len(line) < 2:
            continue
        g = line[0].strip()
        if not g:
            continue
        ids = [x.strip() for x in re.split(r"[\s,;]+", line[1]) if x.strip().isdigit()]
        groups.setdefault(g, [])
        for i in ids:
            if i not in groups[g]:
                groups[g].append(i)
group_rows = [{"group": g, "product_id": i} for g, ids in groups.items() for i in ids]
groups_of = {}
for gr in group_rows:
    groups_of.setdefault(gr["product_id"], []).append(gr["group"])
for r in rows:
    r["groups"] = ", ".join(groups_of.get(r["product_id"], [])) or "Poza kampaniami"

# ---------- Sublime ----------
# kampania -> grupa produktów (arkusz Ads IDs). Brak dopasowania = kampania ogólna / always-on.
CAMPAIGN_GROUP = [
    (r"lampy.designerskie", "Lampy designerskie"),
    (r"bauhaus", "Meble Bauhaus"),
    (r"togo", "Togo"),
    (r"dywany", "Dywany"),
    (r"bolia", "Bolia Lampy"),
    (r"artera", "Artera"),
    (r"zieta", "Zieta"),
    (r"plakaty", "Plakaty"),
    (r"black week og", "BW ogolna"),
    (r"prezenty", "Prezenty"),
    (r"krzes", "Krzesła i fotele"),
    (r"przechowywanie", "Przechowywanie"),
    (r"sto[lł]y", "Stoły"),
]


def channel(name):
    if name.startswith("[PMAX]"):
        return "Google PMax"
    if name.startswith("PLA"):
        return "Google Shopping"
    if name.startswith("SW"):
        return "Google Search"
    if re.match(r"^\d{6}_", name):
        return "Meta"
    return "Inne"


ads = []
with open(sub_path, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        name = (r.get("Campaign Name") or "").strip()
        if not name:
            continue
        grp = next((g for pat, g in CAMPAIGN_GROUP if re.search(pat, name, re.I)), "Ogólna / always-on")
        # "Plakaty " w arkuszu ma spację na końcu -> po strip() to "Plakaty"
        ads.append({
            "campaign": name,
            "channel": channel(name),
            "group": grp,
            "spend": round(num(r["Ad Spend"]), 2),
            "revenue": round(num(r["Revenue"]), 2),
            "gross_profit": round(num(r["Gross Profit"]), 2),
            "orders": round(num(r["Orders"]), 2),
            "clicks": round(num(r["Ad Clicks"]), 2),
            "platform_roas": round(num(r["Platform ROAS"]), 2),
        })

now = datetime.now().strftime("%Y-%m-%d %H:%M")
meta = lambda inp: [{"label": "prep.py", "value": CODE, "type": "code", "lang": "python"},
                    {"label": "Input", "value": inp}, {"label": "Generated", "value": now}]
json.dump({"rows": rows, "meta": meta(os.path.basename(tx_path))},
          open(f"{out_dir}/transactions.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"rows": group_rows, "meta": meta(os.path.basename(ids_path))},
          open(f"{out_dir}/product_groups.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"rows": ads, "meta": meta(os.path.basename(sub_path))},
          open(f"{out_dir}/ads.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(rows), "transakcji;", len(groups), "grup /", len(group_rows), "ID;", len(ads), "kampanii")

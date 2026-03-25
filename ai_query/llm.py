import re
import requests
from django.conf import settings
from .schema_extractor import get_schema_context
from django.core.cache import cache
# Georgian user input → actual DB value mapping
CATEGORY_MAPPINGS = {
    # ACCESSORIES
    "აქსესუარები": "ACCESSORIES",
    "აქსესუარი": "ACCESSORIES",
    # ACCESSORIES PRODUCT
    "აქსესუარების პროდუქტი": "ACCESSORIES PRODUCT",
    "აქსესუარ პროდუქტი": "ACCESSORIES PRODUCT",
    # BODY CARE
    "ბოდი ქეარი": "BODY CARE",
    "ბოდიქეარი": "BODY CARE",
    "სხეულის მოვლა": "BODY CARE",
    # HAIR CARE
    "ჰეარ ქეარი": "HAIR CARE",
    "ჰეარქეარი": "HAIR CARE",
    "თმის მოვლა": "HAIR CARE",
    # HYGIENE
    "ჰიგიენა": "HYGIENE",
    "ჰიგიენის საშუალებები": "HYGIENE",
    # MAKE UP
    "მეიქ აფი": "MAKE UP",
    "მეიქაფი": "MAKE UP",
    "მაკიაჟი": "MAKE UP",
    "მეიკაფი": "MAKE UP",
    # OSFA
    "ოსფა": "OSFA",
    # PARFUMS
    "პარფიუმი": "PARFUMS",
    "პარფუმი": "PARFUMS",
    "სუნამო": "PARFUMS",
    "არომატი": "PARFUMS",
    "პარფიუმერია": "PARFUMS",
    # POP
    "პოპი": "POP",
    # SKIN CARE
    "სქინ ქეარი": "SKIN CARE",
    "სქინქეარი": "SKIN CARE",
    "კანის მოვლა": "SKIN CARE",
    # SUN CARE
    "სან ქეარი": "SUN CARE",
    "სანქეარი": "SUN CARE",
    "მზის დაცვა": "SUN CARE",
    "მზისგან დაცვა": "SUN CARE",
}

# Location name → exact DB "UN" value mapping
LOCATION_MAPPINGS = {
    # ── 1 · ბათუმი გრანდ მოლი ──────────────────────────────────────
    "ბათუმი გრანდ მოლი": "ბათუმი გრანდ მოლი",
    "ბათუმი გრანდ": "ბათუმი გრანდ მოლი",
    "გრანდ მოლი": "ბათუმი გრანდ მოლი",
    "grand mall batumi": "ბათუმი გრანდ მოლი",
    "batumi grand mall": "ბათუმი გრანდ მოლი",
    "batumi grand": "ბათუმი გრანდ მოლი",
    "grand mall": "ბათუმი გრანდ მოლი",

    # ── 2 · ბათუმი მეტრო მოლი ──────────────────────────────────────
    "ბათუმი მეტრო მოლი": "ბათუმი მეტრო მოლი",
    "ბათუმი მეტრო": "ბათუმი მეტრო მოლი",
    "მეტრო მოლი": "ბათუმი მეტრო მოლი",
    "batumi metro mall": "ბათუმი მეტრო მოლი",
    "batumi metro": "ბათუმი მეტრო მოლი",
    "metro mall batumi": "ბათუმი მეტრო მოლი",
    "metro mall": "ბათუმი მეტრო მოლი",

    # ── 3 · გალერია ─────────────────────────────────────────────────
    "გალერია": "გალერია",
    "galeria": "გალერია",
    "gallery": "გალერია",
    "galleria": "გალერია",
    "გალერია თბილისი": "გალერია",
    "galeria tbilisi": "გალერია",

    # ── 4 · გლდანი ──────────────────────────────────────────────────
    "გლდანი": "გლდანი",
    "gldani": "გლდანი",

    # ── 5 · გლდანი სითი მოლი ────────────────────────────────────────
    "გლდანი სითი მოლი": "გლდანი სითი მოლი",
    "გლდანი სითი": "გლდანი სითი მოლი",
    "სითი მოლი": "გლდანი სითი მოლი",
    "gldani city mall": "გლდანი სითი მოლი",
    "gldani city": "გლდანი სითი მოლი",
    "city mall gldani": "გლდანი სითი მოლი",
    "city mall": "გლდანი სითი მოლი",

    # ── 6 · გორი ────────────────────────────────────────────────────
    "გორი": "გორი",
    "gori": "გორი",

    # ── 7 · გუდვილი ─────────────────────────────────────────────────
    "გუდვილი": "გუდვილი",
    "gudvili": "გუდვილი",
    "goodwill": "გუდვილი",
    "good will": "გუდვილი",

    # ── 8 · გუდვილი 2 ───────────────────────────────────────────────
    "გუდვილი 2": "გუდვილი 2",
    "gudvili 2": "გუდვილი 2",
    "goodwill 2": "გუდვილი 2",
    "good will 2": "გუდვილი 2",
    "გუდვილი2": "გუდვილი 2",

    # ── 9 · ვაკე 1 ──────────────────────────────────────────────────
    "ვაკე 1": "ვაკე 1",
    "ვაკე": "ვაკე 1",
    "vake 1": "ვაკე 1",
    "vake": "ვაკე 1",
    "vake1": "ვაკე 1",

    # ── 10 · ისტ პოინტი ─────────────────────────────────────────────
    "ისტ პოინტი": "ისტ პოინტი",
    "ისტ-პოინტი": "ისტ პოინტი",
    "east point": "ისტ პოინტი",
    "eastpoint": "ისტ პოინტი",
    "ist pointi": "ისტ პოინტი",
    "east point tbilisi": "ისტ პოინტი",

    # ── 11 · მერანი ─────────────────────────────────────────────────
    "მერანი": "მერანი",
    "merani": "მერანი",

    # ── 13 · პეკინი ─────────────────────────────────────────────────
    "პეკინმა": "პეკინი",
    "პეკინი": "პეკინი",
    "pekini": "პეკინი",
    "beijing": "პეკინი",
    "peking": "პეკინი",

    # ── 14 · პლეხანოვი ──────────────────────────────────────────────
    "პლეხანოვი": "პლეხანოვი",
    "plekhanov": "პლეხანოვი",
    "plexanovi": "პლეხანოვი",
    "plekhanova": "პლეხანოვი",
    "პლეხანოვის": "პლეხანოვი",

    # ── 15 · რუსთავი ────────────────────────────────────────────────
    "რუსთავი": "რუსთავი",
    "rustavi": "რუსთავი"
}


def normalize_user_prompt(prompt: str) -> str:
    """Replace Georgian/English location and category names with exact DB values."""
    normalized = prompt

    # Locations first (longer phrases → match before shorter ones)
    for user_term, db_value in sorted(LOCATION_MAPPINGS.items(), key=lambda x: -len(x[0])):
        pattern = re.compile(re.escape(user_term), re.IGNORECASE)
        normalized = pattern.sub(db_value, normalized)

    # Then categories
    for user_term, db_value in CATEGORY_MAPPINGS.items():
        pattern = re.compile(re.escape(user_term), re.IGNORECASE)
        normalized = pattern.sub(db_value, normalized)

    return normalized


from .product_lookup import resolve_products

def generate_sql(user_prompt: str, allowed_locations: list) -> str:
    if allowed_locations:
        loc_list = ", ".join(f"'{loc}'" for loc in allowed_locations)
        location_rule = f'ALWAYS include: WHERE "UN" IN ({loc_list})'
    else:
        location_rule = "No location restriction — admin user."

    schema = get_schema_context()
    cache.set('schema_context', schema, 3600) 
    normalized_prompt = normalize_user_prompt(user_prompt)
    ean_codes = resolve_products(normalized_prompt)

    if ean_codes:
        ean_list = ", ".join(f"'{e}'" for e in ean_codes)
        product_hint = (
            f"The user is asking about specific products. "
            f"The matching EAN codes are: {ean_list}. "
            f"Filter by these EAN codes in the query."
        )
    else:
        product_hint = ""

    prompt = f"""You are a PostgreSQL expert. Return ONLY a raw SQL SELECT query, nothing else.
No markdown, no backticks, no explanation. Use double quotes for column names, for example "Tanxa".
Never use DROP, DELETE, UPDATE, INSERT, ALTER.

PostgreSQL-specific rules:
- When using ROUND() with division, always cast to numeric: ROUND((expression)::numeric, 2)
- Window functions inside ROUND must also be cast: ROUND((100.0 * SUM("Col") / SUM(SUM("Col")) OVER ())::numeric, 2)

Category name mappings (use EXACT DB values in queries):
- SKIN CARE → 'SKIN CARE'

when user ask to calculate cross selling or skincare percentage / share, always not following:
1) first of all remove category 'POP' as it should do not be included in calculations.
2) when asked to caculated skincare or any category share, simply sum and divide like you do.
3) 
Cross-selling definitions (based on business logic):
- A "ticket" = one transaction (zedd), containing one or more items
- Single-item ticket: transaction where the customer bought exactly 1 product (item_count = 1)
- Cross-sell ticket: transaction where the customer bought 3 or more products (item_count >= 3)
- Excluded from all cross-sell analysis: prodt != 'selling item', tanxa = 0, prodg = 'POP'

Cross-sell % = (tickets with 3+ items / total tickets) * 100
Single-item % = (tickets with 1 item / total tickets) * 100

To calculate cross-selling in SQL:
WITH ticket_sizes AS (
    SELECT "zedd", "UN", COUNT("idreal1") AS item_count
    FROM your_table
    WHERE "prodt" = 'selling item'
      AND "tanxa" != 0
      AND "prodg" != 'POP'
    GROUP BY "zedd", "UN"
)
SELECT
    "UN",
    COUNT(*) AS total_tickets,
    ROUND((100.0 * SUM(CASE WHEN item_count = 1 THEN 1 ELSE 0 END) / COUNT(*))::numeric, 2) AS single_item_pct,
    ROUND((100.0 * SUM(CASE WHEN item_count >= 3 THEN 1 ELSE 0 END) / COUNT(*))::numeric, 2) AS cross_sell_pct
FROM ticket_sizes
GROUP BY "UN"
ORDER BY cross_sell_pct DESC


Location name mappings (use EXACT DB values in queries):
- გალერია → 'გალერია'
- გლდანი → 'გლდანი'  
- გლდანი სითი მოლი → 'გლდანი სითი მოლი'
- (and so on — already normalized in the question below)


- if user says something with plan or გეგმა in georgian say "there is not plan feature for the bot"
- if user types something that need a quite time to execute, do not hurry and take your time
- if user types in georgian make output in georgian like translate olumn names to georgian please
- if you get error, fix it and think it, proccess and resend
- always take your time, if necessary even more than 30seconds.
- remove 'მთავარი საწყობი 2' and 'სატესტო' from UN for every prompt 
- if user types 'ივაჭრა' in georgian, they mean how much did they sell( revenue wise)
- in many times, you should always trim UN, for incosistencies like 'პეკინი ', or any sort of way, proper it.
- when asked about sicount percentage rate, always caculate percentage discount like 1 - (discount - std) / st 
- when asked about client identificatior rate or კლიენტის იდენტიფიკაცია in georgian, then note this formula:


select 
    "UN",
    1 - (
    round(
        count(distinct case 
            when left("Gvari",13) = 'ფიზიკური პირი'
            then "Zedd"
        end)::numeric
        /
        count(distinct "Zedd")
    ,3)) as phys_share
from sales_main_web
where "CD" between '2026-02-01' and '2026-02-28'
group by "UN";
- that is pretty much everything you need to know.

{location_rule}
{product_hint}
Schema:
{schema}

Question: {normalized_prompt}
SQL:"""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30
    )
    response.raise_for_status()
    sql = response.json()["content"][0]["text"].strip()
    sql = re.sub(r"```sql|```", "", sql).strip()
    return sql
def get_schema_context():
    return """
Database Schema:

Table: sales_main_web (Model: Sales)
  - IdReal1 (BigInteger, primary key)
  - Zedd (Text) — ticket/receipt number
  - CD (DateTime) — date
  - UN (Text) — location/store name (e.g. "გალერია", "გუდვილი 2")
  - IdTanam (BigInteger) — employee ID
  - IdProd (Text) — product ID
  - IdActions (Text) — action/promotion ID
  - raod (Float) — quantity
  - discount_price (Float) — discounted price
  - Sachuqari (Float) — gift/bonus value
  - std_price (Float) — standard price
  - Tanxa (Float) — revenue / turnover amount ← USE THIS for turnover/revenue queries
  - Prod (Text) — product name
  - IdProdT (BigInteger) — product type ID
  - IdProdG (BigInteger) — product group ID
  - Desc1 (Text) — description
  - ProdT (Text) — product type name
  - ProdG (Text) — product group/category name
  - Actions (Text) — promotion/action name
  - Tanam (Text) — employee name
  - IdGvari (BigInteger) — card id
  - Gvari (Text) — name of a person with card id
  - Segment (Text) — customer segment

Key facts:
- "turnover" or "revenue" = SUM(Tanxa)
- "transactions" or "tickets" = COUNT(DISTINCT Zedd)
- "units sold" = SUM(raod)
- segment mean customer segments like passionate, regular, etc
- Date filtering: use CD column with DATE_TRUNC or EXTRACT
- Location filtering: use UN column
- Employee filtering: use Tanam column
- Category filtering: use ProdG column
- Brand filtering: use Gvari column
- for segment use: segment
"""
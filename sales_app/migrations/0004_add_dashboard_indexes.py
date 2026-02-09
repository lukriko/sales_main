from django.db import migrations

class Migration(migrations.Migration):
    atomic = False  # Required for CONCURRENTLY
    
    dependencies = [
        ("sales_app", "0003_add_performance_indexes"),
    ]
    
    operations = [
        # Set statement timeout to 10 minutes
        migrations.RunSQL(
            'SET statement_timeout = 600000;',
            migrations.RunSQL.noop,
        ),
        
        # ========== CRITICAL MISSING INDEXES ==========
        
        # 1. Year extraction index (used in EVERY query: cd__year=2026)
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_year 
            ON sales_main_web (EXTRACT(YEAR FROM "CD"), "CD");
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_year;',
        ),
        
        # 2. Date + Location + Revenue (for location filtering with sums)
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_un_tanxa 
            ON sales_main_web ("CD", "UN", "Tanxa") 
            WHERE "UN" NOT IN ('მთავარი საწყობი 2', 'სატესტო');
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_un_tanxa;',
        ),
        
        # 3. Month/Day extraction (for daily grouping: ExtractMonth/ExtractDay)
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_month_day 
            ON sales_main_web (EXTRACT(MONTH FROM "CD"), EXTRACT(DAY FROM "CD"), "CD");
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_month_day;',
        ),
        
        # 4. Cross-selling analysis (prodt='selling item' filtering)
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prodt_cd_zedd 
            ON sales_main_web ("ProdT", "CD", "Zedd") 
            WHERE "ProdT" = 'selling item' AND "Tanxa" != 0;
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prodt_cd_zedd;',
        ),
        
        # 5. Product analysis (excluding POP category)
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prod_revenue 
            ON sales_main_web ("Prod", "IdProd", "CD", "Tanxa") 
            WHERE "ProdG" != 'POP';
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prod_revenue;',
        ),
        
        # 6. Covering index for aggregations (INCLUDE clause for common sums)
        # This is PostgreSQL 11+ only - if you get an error, comment this out
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_filters_covering 
            ON sales_main_web ("CD", "UN", "ProdG") 
            INCLUDE ("Tanxa", "discount_price", "std_price");
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_filters_covering;',
        ),
        
        # 7. Ticket distinct count optimization
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_zedd_distinct 
            ON sales_main_web ("CD", "Zedd", "UN");
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_zedd_distinct;',
        ),
        
        # 8. Category filtering (for when selected_category != 'all')
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_prodg_tanxa 
            ON sales_main_web ("CD", "ProdG", "Tanxa") 
            WHERE "ProdG" IS NOT NULL;
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_prodg_tanxa;',
        ),
        
        # Reset timeout
        migrations.RunSQL(
            'RESET statement_timeout;',
            migrations.RunSQL.noop,
        ),
    ]
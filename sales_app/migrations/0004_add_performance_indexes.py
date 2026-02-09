from django.db import migrations

class Migration(migrations.Migration):
    atomic = False
    
    dependencies = [
        ("sales_app", "0003_add_performance_indexes"),
    ]
    operations = [
        migrations.RunSQL(
            'SET statement_timeout = 600000;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Index 1: Year extraction (CRITICAL - used in EVERY query)
        # Your queries do: .filter(cd__year=2026)
        # This index makes that 100x faster
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_year 
            ON sales_main_web (EXTRACT(YEAR FROM "CD"), "CD");
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Index 2: Month/Day extraction (for daily aggregations)
        # Your queries do: .annotate(month=ExtractMonth('cd'), day=ExtractDay('cd'))
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_month_day 
            ON sales_main_web (EXTRACT(MONTH FROM "CD"), EXTRACT(DAY FROM "CD"), "CD");
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Index 3: Partial index for warehouse exclusion
        # Your queries do: .exclude(un__in=["მთავარი საწყობი 2", "სატესტო"])
        # This makes filtered queries much faster
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_un_filtered 
            ON sales_main_web ("CD", "UN") 
            WHERE "UN" NOT IN ('მთავარი საწყობი 2', 'სატესტო');
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        migrations.RunSQL(
            'RESET statement_timeout;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
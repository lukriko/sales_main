# sales_app/migrations/0002_add_performance_indexes.py
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("sales_app", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Date-based indexes (CRITICAL for date filters)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd
                ON sales_main_web ("CD");

            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_un
                ON sales_main_web ("CD", "UN");
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_un;
            """,
        ),

        migrations.RunSQL(
            sql="""
            -- Location and category indexes
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_un
                ON sales_main_web ("UN");

            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prodg
                ON sales_main_web ("ProdG");

            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prod
                ON sales_main_web ("Prod");

            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_actions
                ON sales_main_web ("Actions");
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_un;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prodg;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prod;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_actions;
            """,
        ),

        migrations.RunSQL(
            sql="""
            -- Employee and ticket indexes
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_tanam
                ON sales_main_web ("IdTanam");  -- if this is actually the column you filter by

            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_zedd
                ON sales_main_web ("Zedd");

            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prodt
                ON sales_main_web ("ProdT");
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_tanam;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_zedd;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prodt;
            """,
        ),
    ]

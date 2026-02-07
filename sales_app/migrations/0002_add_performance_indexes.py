from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("sales_app", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd ON sales_main_web ("CD");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd;',
        ),
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_un ON sales_main_web ("CD", "UN");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_un;',
        ),
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_un ON sales_main_web ("UN");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_un;',
        ),
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prodg ON sales_main_web ("ProdG");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prodg;',
        ),
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prod ON sales_main_web ("Prod");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prod;',
        ),
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_actions ON sales_main_web ("Actions");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_actions;',
        ),
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_idtanam ON sales_main_web ("IdTanam");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_idtanam;',
        ),
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_zedd ON sales_main_web ("Zedd");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_zedd;',
        ),
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prodt ON sales_main_web ("ProdT");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prodt;',
        ),
    ]

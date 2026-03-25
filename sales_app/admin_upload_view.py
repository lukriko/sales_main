import gc
import pickle
import tempfile
import os
import pandas as pd
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from sales_app.models import Sales
from django.db.models import Max, Min, Count

CHUNK_SIZE = 500  # rows per batch insert — keep low to save memory

COLUMN_MAP = {
    'idreal1':       'idreal1',
    'zedd':          'zedd',
    'cd':            'cd',
    'un':            'un',
    'idtanam':       'idtanam',
    'idprod':        'idprod',
    'idactions':     'idactions',
    'raod':          'raod',
    'discount_price':'discount_price',
    'sachuqari':     'sachuqari',
    'std_price':     'std_price',
    'tanxa':         'tanxa',
    'prod':          'prod',
    'idprodt':       'idprodt',
    'idprodg':       'idprodg',
    'desc1':         'desc1',
    'prodt':         'prodt',
    'prodg':         'prodg',
    'actions':       'actions',
    'tanam':         'tanam',
    # ✅ NEW COLUMNS
    'idgvari':       'IdGvari',
    'gvari':         'Gvari',
    'segment':       'Segment',
}

FLOAT_FIELDS = {'raod', 'discount_price', 'sachuqari', 'std_price', 'tanxa'}
NULLABLE_FIELDS = {'idtanam', 'idprodt', 'idprodg', 'IdGvari', 'Gvari', 'Segment'}


def row_to_record(row, col_index):
    """Convert a DataFrame row to a Sales model instance efficiently."""
    record_data = {}

    for src_col, dest_col in col_index.items():
        val = row.get(src_col)

        if dest_col == 'cd':
            if pd.notna(val):
                if isinstance(val, pd.Timestamp):
                    val = val.to_pydatetime()
                if timezone.is_naive(val):
                    val = timezone.make_aware(val)
            record_data['cd'] = val

        elif dest_col in FLOAT_FIELDS:
            record_data[dest_col] = float(val) if pd.notna(val) else None

        elif dest_col in NULLABLE_FIELDS:
            record_data[dest_col] = val if pd.notna(val) else None

        else:
            record_data[dest_col] = val

    return Sales(**record_data)


@login_required
def admin_upload(request):
    try:
        user_profile = request.user.profile
    except:
        return HttpResponseForbidden("Access denied. Contact administrator.")

    if not user_profile.is_admin:
        return HttpResponseForbidden("Only administrators can access the data upload interface.")

    upload_stats = None
    error_message = None

    existing_data_range = Sales.objects.aggregate(
        min_date=Min('cd'),
        max_date=Max('cd'),
        total_records=Count('idreal1')
    )

    if request.method == 'POST' and request.FILES.get('pkl_file'):
        pkl_file = request.FILES['pkl_file']
        dedup_start_date = request.POST.get('dedup_start_date')
        dedup_end_date = request.POST.get('dedup_end_date')

        if not pkl_file.name.endswith('.pkl'):
            error_message = "Please upload a valid .pkl file"
        else:
            try:
                # Parse dates
                start_date = datetime.strptime(dedup_start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(dedup_end_date, '%Y-%m-%d').date()

                if start_date > end_date:
                    raise ValueError("Start date must be before or equal to end date")

                # ── Save uploaded file to temp location to avoid keeping it in memory ──
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as tmp:
                    for chunk in pkl_file.chunks(chunk_size=8 * 1024 * 1024):  # 8MB chunks
                        tmp.write(chunk)
                    tmp_path = tmp.name

                try:
                    # ── Load PKL from disk ──
                    df = pd.read_pickle(tmp_path)
                finally:
                    os.unlink(tmp_path)  # delete temp file immediately

                total_rows = len(df)

                # Normalize column names to lowercase
                df.columns = [c.lower() for c in df.columns]

                if 'cd' not in df.columns:
                    raise ValueError("PKL file must contain a 'cd' or 'CD' datetime column")

                if 'idreal1' not in df.columns:
                    raise ValueError("PKL file must contain 'IdReal1' or 'idreal1' column")

                # Parse dates
                df['cd'] = pd.to_datetime(df['cd'])

                # ── Filter to date range ──
                start_ts = pd.Timestamp(start_date)
                end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                mask = (df['cd'] >= start_ts) & (df['cd'] <= end_ts)
                df = df[mask].reset_index(drop=True)  # drop full df, keep only filtered

                if len(df) == 0:
                    raise ValueError(f"No records found in PKL file between {start_date} and {end_date}")

                date_range_count = len(df)

                # Build column index — only cols present in both df and COLUMN_MAP
                col_index = {
                    src: dst for src, dst in COLUMN_MAP.items()
                    if src in df.columns
                }

                # ── Delete existing records in date range ──
                deleted_count = Sales.objects.filter(
                    cd__gte=timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                    cd__lte=timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
                ).delete()[0]

                # ── Chunk insert ──
                inserted_count = 0
                for start_idx in range(0, len(df), CHUNK_SIZE):
                    chunk = df.iloc[start_idx:start_idx + CHUNK_SIZE]
                    records = [
                        row_to_record(row, col_index)
                        for _, row in chunk.iterrows()
                    ]
                    with transaction.atomic():
                        Sales.objects.bulk_create(records, batch_size=CHUNK_SIZE)
                    inserted_count += len(records)

                    # Free memory after each chunk
                    del records, chunk
                    gc.collect()

                # Free the full dataframe
                del df
                gc.collect()

                upload_stats = {
                    'total_in_file': total_rows,
                    'date_range_records': date_range_count,
                    'deleted_existing': deleted_count,
                    'inserted_new': inserted_count,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'success': True
                }

                messages.success(request,
                    f"Successfully uploaded! Deleted {deleted_count} existing records, "
                    f"inserted {inserted_count} new records for {start_date} to {end_date}.")

            except ValueError as e:
                error_message = str(e)
            except Exception as e:
                error_message = f"Upload Error: {str(e)}"
                import traceback
                traceback.print_exc()

    existing_data_range = Sales.objects.aggregate(
        min_date=Min('cd'),
        max_date=Max('cd'),
        total_records=Count('idreal1')
    )

    return render(request, 'admin_upload.html', {
        'upload_stats': upload_stats,
        'error_message': error_message,
        'existing_data_range': existing_data_range,
        'user_profile': user_profile,
        'is_admin': user_profile.is_admin,
    })
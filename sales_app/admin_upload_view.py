import pickle
import pandas as pd
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.db import transaction, connection
from django.utils import timezone
from datetime import datetime, date
from sales_app.models import Sales
from django.db.models import Max, Min, Count

@login_required
def admin_upload(request):
    """
    Admin-only view for uploading PKL files with deduplication
    """
    try:
        user_profile = request.user.profile
    except:
        return HttpResponseForbidden("Access denied. Contact administrator.")
    
    # ADMIN ONLY
    if not user_profile.is_admin:
        return HttpResponseForbidden("Only administrators can access the data upload interface.")
    
    upload_stats = None
    error_message = None
    
    # Get date range of existing data
    existing_data_range = Sales.objects.aggregate(
        min_date=Min('cd'),
        max_date=Max('cd'),
        total_records=Count('idreal1')
    )
    
    if request.method == 'POST' and request.FILES.get('pkl_file'):
        pkl_file = request.FILES['pkl_file']
        dedup_start_date = request.POST.get('dedup_start_date')
        dedup_end_date = request.POST.get('dedup_end_date')
        
        # Validate file extension
        if not pkl_file.name.endswith('.pkl'):
            error_message = "Please upload a valid .pkl file"
        else:
            try:
                # Parse dates
                start_date = None
                end_date = None
                
                if dedup_start_date:
                    try:
                        start_date = datetime.strptime(dedup_start_date, '%Y-%m-%d').date()
                    except:
                        error_message = "Invalid start date format. Use YYYY-MM-DD"
                        return render(request, 'admin_upload.html', {
                            'error_message': error_message,
                            'existing_data_range': existing_data_range,
                            'user_profile': user_profile,
                            'is_admin': user_profile.is_admin,
                        })
                
                if dedup_end_date:
                    try:
                        end_date = datetime.strptime(dedup_end_date, '%Y-%m-%d').date()
                    except:
                        error_message = "Invalid end date format. Use YYYY-MM-DD"
                        return render(request, 'admin_upload.html', {
                            'error_message': error_message,
                            'existing_data_range': existing_data_range,
                            'user_profile': user_profile,
                            'is_admin': user_profile.is_admin,
                        })
                
                # Validate date range
                if start_date and end_date and start_date > end_date:
                    error_message = "Start date must be before or equal to end date"
                    return render(request, 'admin_upload.html', {
                        'error_message': error_message,
                        'existing_data_range': existing_data_range,
                        'user_profile': user_profile,
                        'is_admin': user_profile.is_admin,
                    })
                
                # Load PKL file
                df = pd.read_pickle(pkl_file)
                
                total_rows = len(df)
                
                # Ensure cd column is datetime
                if 'CD' in df.columns:
                    df['CD'] = pd.to_datetime(df['CD'])
                elif 'cd' in df.columns:
                    df['cd'] = pd.to_datetime(df['cd'])
                    df.rename(columns={'cd': 'CD'}, inplace=True)
                else:
                    error_message = "PKL file must contain a 'cd' or 'CD' datetime column"
                    return render(request, 'admin_upload.html', {
                        'error_message': error_message,
                        'existing_data_range': existing_data_range,
                        'user_profile': user_profile,
                        'is_admin': user_profile.is_admin,
                    })
                
                # Filter by date range if provided
                if start_date and end_date:
                    # Convert dates to pandas timestamps for comparison
                    start_ts = pd.Timestamp(start_date)
                    end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                    
                    date_filtered_df = df[(df['CD'] >= start_ts) & (df['CD'] <= end_ts)]
                    
                    if len(date_filtered_df) == 0:
                        error_message = f"No records found in PKL file between {start_date} and {end_date}"
                        return render(request, 'admin_upload.html', {
                            'error_message': error_message,
                            'existing_data_range': existing_data_range,
                            'user_profile': user_profile,
                            'is_admin': user_profile.is_admin,
                        })
                    
                    # DEDUPLICATION: Remove existing records in this date range
                    with transaction.atomic():
                        # Delete existing records in date range
                        deleted_count = Sales.objects.filter(
                            cd__gte=timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                            cd__lte=timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
                        ).delete()[0]
                        
                        # Prepare data for bulk insert
                        records_to_insert = []
                        
                        for _, row in date_filtered_df.iterrows():
                            # Ensure IdReal1 is the primary key
                            if 'IdReal1' not in row and 'idreal1' not in row:
                                error_message = "PKL file must contain 'IdReal1' or 'idreal1' column as primary key"
                                raise ValueError(error_message)
                            
                            # Normalize column names to match model
                            record_data = {}
                            for col in df.columns:
                                col_lower = col.lower()
                                if col_lower == 'idreal1':
                                    record_data['idreal1'] = row[col]
                                elif col_lower == 'zedd':
                                    record_data['zedd'] = row[col]
                                elif col_lower == 'cd':
                                    # Make timezone-aware
                                    cd_value = row[col]
                                    if pd.notna(cd_value):
                                        if isinstance(cd_value, pd.Timestamp):
                                            cd_value = cd_value.to_pydatetime()
                                        if timezone.is_naive(cd_value):
                                            cd_value = timezone.make_aware(cd_value)
                                    record_data['cd'] = cd_value
                                elif col_lower == 'un':
                                    record_data['un'] = row[col]
                                elif col_lower == 'idtanam':
                                    record_data['idtanam'] = row[col] if pd.notna(row[col]) else None
                                elif col_lower == 'idprod':
                                    record_data['idprod'] = row[col]
                                elif col_lower == 'idactions':
                                    record_data['idactions'] = row[col]
                                elif col_lower == 'raod':
                                    record_data['raod'] = float(row[col]) if pd.notna(row[col]) else None
                                elif col_lower == 'discount_price':
                                    record_data['discount_price'] = float(row[col]) if pd.notna(row[col]) else None
                                elif col_lower == 'sachuqari':
                                    record_data['sachuqari'] = float(row[col]) if pd.notna(row[col]) else None
                                elif col_lower == 'std_price':
                                    record_data['std_price'] = float(row[col]) if pd.notna(row[col]) else None
                                elif col_lower == 'tanxa':
                                    record_data['tanxa'] = float(row[col]) if pd.notna(row[col]) else None
                                elif col_lower == 'prod':
                                    record_data['prod'] = row[col]
                                elif col_lower == 'idprodt':
                                    record_data['idprodt'] = row[col] if pd.notna(row[col]) else None
                                elif col_lower == 'idprodg':
                                    record_data['idprodg'] = row[col] if pd.notna(row[col]) else None
                                elif col_lower == 'desc1':
                                    record_data['desc1'] = row[col]
                                elif col_lower == 'prodt':
                                    record_data['prodt'] = row[col]
                                elif col_lower == 'prodg':
                                    record_data['prodg'] = row[col]
                                elif col_lower == 'actions':
                                    record_data['actions'] = row[col]
                                elif col_lower == 'tanam':
                                    record_data['tanam'] = row[col]
                            
                            records_to_insert.append(Sales(**record_data))
                        
                        # Bulk insert
                        Sales.objects.bulk_create(records_to_insert, batch_size=1000)
                        
                        inserted_count = len(records_to_insert)
                        
                        upload_stats = {
                            'total_in_file': total_rows,
                            'date_range_records': len(date_filtered_df),
                            'deleted_existing': deleted_count,
                            'inserted_new': inserted_count,
                            'start_date': start_date.strftime('%Y-%m-%d'),
                            'end_date': end_date.strftime('%Y-%m-%d'),
                            'success': True
                        }
                        
                        messages.success(request, 
                            f"Successfully uploaded! Deleted {deleted_count} existing records, inserted {inserted_count} new records for {start_date} to {end_date}.")
                
                else:
                    error_message = "Both start date and end date are required for deduplication"
            
            except pd.errors.EmptyDataError:
                error_message = "The PKL file is empty or corrupted"
            except Exception as e:
                error_message = f"Upload Error: {str(e)}"
                import traceback
                traceback.print_exc()
    
    # Refresh existing data range after upload
    existing_data_range = Sales.objects.aggregate(
        min_date=Min('cd'),
        max_date=Max('cd'),
        total_records=Count('idreal1')
    )
    
    context = {
        'upload_stats': upload_stats,
        'error_message': error_message,
        'existing_data_range': existing_data_range,
        'user_profile': user_profile,
        'is_admin': user_profile.is_admin,
    }
    
    return render(request, 'admin_upload.html', context)
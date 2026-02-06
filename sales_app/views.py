import json
from django.shortcuts import render
from .models import Sales
from django.db.models import Sum, Count, Avg, FloatField, ExpressionWrapper, F, Q, Min,OuterRef, Max
from django.db.models.functions import ExtractMonth, ExtractDay, TruncDay, ExtractWeek
from django.http import HttpResponse
from datetime import datetime, date, timedelta
from django.utils import timezone
from openpyxl import load_workbook
import os
from django.conf import settings
import pandas as pd
import calendar
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from pathlib import Path
from django.db import connection
from django.contrib import messages
import re

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from django.contrib.auth import login, logout ,authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.db.models import Prefetch


@login_required
def dashboard(request):
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        return HttpResponseForbidden("Access denied. Contact administrator.")
    
    # Get allowed locations for this user
    allowed_locations = user_profile.get_allowed_locations()
    
    # Determine which years to compare based on mode
    comparison_mode = request.GET.get('comparison', '2025-2024')
    if comparison_mode == '2026-2025':
        current_year = 2026
        previous_year = 2025
    elif comparison_mode == '2026-2024':
        current_year = 2026
        previous_year = 2024
    else:
        current_year = 2025
        previous_year = 2024
    
    # Get filter parameters
    start_date_str = request.GET.get('start_date', f'{current_year}-01-01')
    end_date_str = request.GET.get('end_date', f'{current_year}-12-31')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except:
        start_date = date(current_year, 1, 1)
    
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except:
        end_date = date(current_year, 12, 31)
    
    # Handle location selections with access control
    selected_locations = request.GET.getlist('un_filter')
    
    # SECURITY CHECK: Validate selected locations against user's allowed locations
    if not user_profile.is_admin:
        if not selected_locations or 'all' in selected_locations:
            # User tried to select "all" but isn't admin - restrict to their locations
            selected_locations = allowed_locations
        else:
            # Filter out any locations the user shouldn't access
            unauthorized = set(selected_locations) - set(allowed_locations)
            if unauthorized:
                messages.warning(request, f"Access denied to: {', '.join(unauthorized)}")
                selected_locations = [loc for loc in selected_locations if loc in allowed_locations]
            
            # If no valid locations remain, use all allowed
            if not selected_locations:
                selected_locations = allowed_locations
    
    # Ensure user has at least some locations to view
    if not selected_locations and not user_profile.is_admin:
        return HttpResponseForbidden("You don't have access to any locations. Contact administrator.")
    
    # Set selected_un for display
    if user_profile.is_admin and (not selected_locations or 'all' in request.GET.getlist('un_filter')):
        selected_un = 'all'
        selected_locations = []
    else:
        selected_un = selected_locations[0] if len(selected_locations) == 1 else 'multiple'
    
    selected_category = request.GET.get('category', 'all')
    selected_product = request.GET.get('prod_filter', 'all')
    selected_campaign = request.GET.get('campaign_filter', 'all')
    
    # Adjust start_date and end_date to match current_year
    start_date = start_date.replace(year=current_year)
    end_date = end_date.replace(year=current_year)
    
    # Get the max date available in current_year
    max_date_query = Sales.objects.filter(cd__year=current_year)
    if selected_locations:  # Changed: use selected_locations
        max_date_query = max_date_query.filter(un__in=selected_locations)
    if selected_category != 'all':
        max_date_query = max_date_query.filter(prodg=selected_category)
    if selected_product != 'all':
        max_date_query = max_date_query.filter(prod=selected_product)
    if selected_campaign != 'all':
        max_date_query = max_date_query.filter(actions=selected_campaign)
    
    max_date_result = max_date_query.aggregate(max_date=Max('cd'))
    max_date = max_date_result['max_date']
    
    # Create date filters
    if max_date:
        if end_date > max_date.date():
            end_date = max_date.date()
    
    # Define previous year dates
    previous_start = start_date.replace(year=previous_year)
    previous_end = end_date.replace(year=previous_year)
    
    # Create timezone-aware datetimes
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    previous_start_datetime = timezone.make_aware(datetime.combine(previous_start, datetime.min.time()))
    previous_end_datetime = timezone.make_aware(datetime.combine(previous_end, datetime.max.time()))
    
    date_filter_current = {
        'cd__year': current_year,
        'cd__gte': start_datetime,
        'cd__lte': end_datetime
    }
    
    date_filter_previous = {
        'cd__year': previous_year,
        'cd__gte': previous_start_datetime,
        'cd__lte': previous_end_datetime
    }
    
    def apply_filters(q):
        """Helper function to apply all filters consistently"""
        if selected_locations:  # Changed: use selected_locations with __in
            q = q.filter(un__in=selected_locations)
        if selected_category != 'all':
            q = q.filter(prodg=selected_category)
        if selected_product != 'all':
            q = q.filter(prod=selected_product)
        if selected_campaign != 'all':
            q = q.filter(actions=selected_campaign)
        return q
    
    def get_yearly_data(year, is_current=True):
        if is_current:
            q = Sales.objects.filter(**date_filter_current).exclude(
                un__in=["მთავარი საწყობი 2", "სატესტო"]
            )
        else:
            q = Sales.objects.filter(**date_filter_previous).exclude(
                un__in=["მთავარი საწყობი 2", "სატესტო"]
            )
        
        q = apply_filters(q)  # Use helper function
        
        return q.annotate(
            month=ExtractMonth('cd'), 
            day=ExtractDay('cd')
        ).values('month', 'day').annotate(
            total=Sum('tanxa'),
            total_transactions=Count('zedd', distinct=True),
            total_items=Count('zedd')
        ).order_by('month', 'day')
    
    def get_yearly_stats(year, is_current=True):
        """Get aggregated statistics for a year"""
        if is_current:
            q = Sales.objects.filter(**date_filter_current)
        else:
            q = Sales.objects.filter(**date_filter_previous)
        
        q = apply_filters(q)  # Use helper function
        
        stats = q.aggregate(
            total_revenue=Sum('tanxa'),
            total_tickets=Count('zedd', distinct=True),
            total_items=Count('zedd', filter=Q(~Q(idprod__in=['M9157', 'M9121', 'M9850']))),
            discount_total=Sum('discount_price'),
            std_price_total=Sum('std_price')
        )
        
        if stats and stats.get('total_tickets') and stats['total_tickets'] > 0:
            stats['avg_basket'] = float(stats['total_revenue'] or 0) / stats['total_tickets']
        else:
            stats['avg_basket'] = 0
        # Then the division becomes:
        if stats['discount_total'] is not None and stats['std_price_total'] is not None and stats['std_price_total'] != 0:
          stats['discount_share'] = (1 - (stats['discount_total'] / stats['std_price_total'])) * 100
        else:
            stats['discount_share'] = 0
        return stats
    
    def get_daily_cross_selling_stats(year, is_current=True):
        """Get cross-selling stats aggregated by day"""
        """Get cross-selling stats aggregated by day"""
        if is_current:
            q = Sales.objects.filter(**date_filter_current, prodt='selling item').exclude(tanxa=0).exclude(prodg='POP')
        else:
            q = Sales.objects.filter(**date_filter_previous, prodt='selling item').exclude(tanxa=0).exclude(prodg='POP')
        
        q = apply_filters(q)
        # Get daily ticket counts with item counts
        daily_data = q.annotate(
            month=ExtractMonth('cd'), 
            day=ExtractDay('cd')
        ).values('month', 'day', 'zedd').annotate(
            item_count=Count('idreal1')
        )
        
        # Group by date and count single-item and cross-sell tickets
        date_stats = {}
        for record in daily_data:
            date_key = f"{record['month']}/{record['day']}"
            if date_key not in date_stats:
                date_stats[date_key] = {
                    'total': 0,
                    'single_item': 0,
                    'cross_sell': 0
                }
            
            date_stats[date_key]['total'] += 1
            if record['item_count'] == 1:
                date_stats[date_key]['single_item'] += 1
            elif record['item_count'] >= 3:
                date_stats[date_key]['cross_sell'] += 1
        
        # Convert to percentages
        result = {}
        for date_key, stats in date_stats.items():
            total = stats['total']
            if total > 0:
                result[date_key] = {
                    'single_item_pct': (stats['single_item'] / total) * 100,
                    'cross_sell_pct': (stats['cross_sell'] / total) * 100,
                    'total_tickets': total
                }
            else:
                result[date_key] = {
                    'single_item_pct': 0,
                    'cross_sell_pct': 0,
                    'total_tickets': 0
                }
        
        return result

    def get_cross_selling_stats(year, is_current=True):
        if is_current:
            q = (Sales.objects
                .filter(**date_filter_current, prodt='selling item')
                .exclude(tanxa=0)
                .exclude(prodg='POP')
                .exclude(idprod__in=['M9157', 'M9121', 'M9850']))
        else:
            q = (Sales.objects
                .filter(**date_filter_previous, prodt='selling item')
                .exclude(tanxa=0)
                .exclude(prodg='POP')
                .exclude(idprod__in=['M9157', 'M9121', 'M9850']))
        
        q = apply_filters(q)  # Use helper function
        
        ticket_items = q.values('zedd').annotate(
            item_count=Count('idreal1')
        )
        
        total_tickets = ticket_items.count()
        cross_sell_tickets = sum(1 for t in ticket_items if t['item_count'] >= 3)
        single_item_tickets = sum(1 for t in ticket_items if t['item_count'] == 1)
        cross_sell_pct = (cross_sell_tickets / total_tickets * 100) if total_tickets > 0 else 0
        single_item_pct = (single_item_tickets / total_tickets * 100) if total_tickets > 0 else 0
        
        return {
            'cross_sell_tickets': cross_sell_tickets,
            'cross_sell_percentage': cross_sell_pct,
            'single_item_tickets': single_item_tickets,
            'single_item_percentage': single_item_pct,
            'total_tickets': total_tickets
        }
    
    # Add this function inside your dashboard view, after get_cross_selling_stats
    def get_ticket_distribution(year, is_current=True):
        """Get ticket amount distribution in ranges"""
        if is_current:
            q = Sales.objects.filter(**date_filter_current, prodt='selling item').exclude(tanxa=0)
        else:
            q = Sales.objects.filter(**date_filter_previous, prodt='selling item').exclude(tanxa=0)
        
        q = apply_filters(q)
        
        # Group by ticket and sum amounts
        ticket_totals = q.values('zedd').annotate(
            ticket_total=Sum('tanxa')
        ).values_list('ticket_total', flat=True)
        
        # Define price ranges
        ranges = [
            (0, 50, '0-50'),
            (50, 100, '50-100'),
            (100, 150, '100-150'),
            (150, 200, '150-200'),
            (200, 300, '200-300'),
            (300, 500, '300-500'),
            (500, 1000, '500-1K'),
            (1000, float('inf'), '1K+')
        ]
        
        distribution = {label: 0 for _, _, label in ranges}
        total_tickets = len(ticket_totals)
        
        # Categorize tickets
        for amount in ticket_totals:
            amount = float(amount)
            for min_val, max_val, label in ranges:
                if min_val <= amount < max_val:
                    distribution[label] += 1
                    break
        
        # Calculate percentages
        distribution_pct = {
            label: (count / total_tickets * 100) if total_tickets > 0 else 0
            for label, count in distribution.items()
        }
        
        # Calculate statistics
        ticket_list = [float(t) for t in ticket_totals]
        avg_ticket = sum(ticket_list) / len(ticket_list) if ticket_list else 0
        median_ticket = sorted(ticket_list)[len(ticket_list) // 2] if ticket_list else 0
        
        # Calculate percentiles
        if ticket_list:
            sorted_tickets = sorted(ticket_list)
            p25 = sorted_tickets[len(sorted_tickets) // 4]
            p75 = sorted_tickets[3 * len(sorted_tickets) // 4]
        else:
            p25 = p75 = 0
        
        return {
            'distribution': distribution,
            'distribution_pct': distribution_pct,
            'total_tickets': total_tickets,
            'avg_ticket': avg_ticket,
            'median_ticket': median_ticket,
            'p25': p25,
            'p75': p75
        }

# Add these lines after the cross_sell_current and cross_sell_previous calls:
    def get_employee_stats(year, is_current=True):
        """Get employee performance statistics"""
        if is_current:
            q = Sales.objects.filter(**date_filter_current)
        else:
            q = Sales.objects.filter(**date_filter_previous)
        
        q = apply_filters(q)
        
        # Get employee statistics
        employee_data = q.values('tanam').annotate(
            total_revenue=Sum('tanxa'),
            total_tickets=Count('zedd', distinct=True),
            total_items=Count('zedd'),
            avg_basket=Sum('tanxa') / Count('zedd', distinct=True),
            discount_given=Sum('discount_price'),
            std_price_total=Sum('std_price')
        ).order_by('-total_revenue')
        
        # Calculate additional metrics for each employee
        employee_stats = []
        for emp in employee_data:
            items_per_ticket = emp['total_items'] / emp['total_tickets'] if emp['total_tickets'] > 0 else 0
            discount_rate = (1 - (emp['discount_given'] / emp['std_price_total'])) * 100 if emp['std_price_total'] and emp['std_price_total'] > 0 else 0
            
            employee_stats.append({
                'name': emp['tanam'] or 'Unknown',
                'revenue': float(emp['total_revenue'] or 0),
                'tickets': emp['total_tickets'],
                'items': emp['total_items'],
                'avg_basket': float(emp['avg_basket'] or 0),
                'items_per_ticket': items_per_ticket,
                'discount_rate': discount_rate
            })
        
        return employee_stats
    
    # Get data for both years in the comparison
    data_current = list(get_yearly_data(current_year, is_current=True))
    data_previous = list(get_yearly_data(previous_year, is_current=False))
    stats_current = get_yearly_stats(current_year, is_current=True)
    stats_previous = get_yearly_stats(previous_year, is_current=False)
    cross_sell_current = get_cross_selling_stats(current_year, is_current=True)
    cross_sell_previous = get_cross_selling_stats(previous_year, is_current=False)
    dist_current = get_ticket_distribution(current_year, is_current=True)
    dist_previous = get_ticket_distribution(previous_year, is_current=False)

    # Calculate distribution changes
   
    # Create date maps for all metrics
    date_map_revenue_current = {f"{i['month']}/{i['day']}": float(i['total'] or 0) for i in data_current}
    date_map_revenue_previous = {f"{i['month']}/{i['day']}": float(i['total'] or 0) for i in data_previous}

    date_map_tickets_current = {f"{i['month']}/{i['day']}": int(i['total_transactions'] or 0) for i in data_current}
    date_map_tickets_previous = {f"{i['month']}/{i['day']}": int(i['total_transactions'] or 0) for i in data_previous}

    date_map_items_current = {f"{i['month']}/{i['day']}": int(i['total_items'] or 0) for i in data_current}
    date_map_items_previous = {f"{i['month']}/{i['day']}": int(i['total_items'] or 0) for i in data_previous}

    labels = [f"{i['month']}/{i['day']}" for i in data_current]
    values_current = [date_map_revenue_current.get(label, 0) for label in labels]
    values_previous = [date_map_revenue_previous.get(label, 0) for label in labels]

    cross_sell_daily_current = get_daily_cross_selling_stats(current_year, is_current=True)
    cross_sell_daily_previous = get_daily_cross_selling_stats(previous_year, is_current=False)
    
    # Create arrays for chart data
    single_item_pct_current = [cross_sell_daily_current.get(label, {}).get('single_item_pct', 0) for label in labels]
    single_item_pct_previous = [cross_sell_daily_previous.get(label, {}).get('single_item_pct', 0) for label in labels]
    
    cross_sell_pct_current = [cross_sell_daily_current.get(label, {}).get('cross_sell_pct', 0) for label in labels]
    cross_sell_pct_previous = [cross_sell_daily_previous.get(label, {}).get('cross_sell_pct', 0) for label in labels]

    tickets_values_current = [date_map_tickets_current.get(label, 0) for label in labels]
    tickets_values_previous = [date_map_tickets_previous.get(label, 0) for label in labels]

    items_values_current = [date_map_items_current.get(label, 0) for label in labels]
    items_values_previous = [date_map_items_previous.get(label, 0) for label in labels]

    # Calculate average basket for each day
    basket_values_current = []
    basket_values_previous = []

    for label in labels:
        revenue_curr = date_map_revenue_current.get(label, 0)
        tickets_curr = date_map_tickets_current.get(label, 0)
        basket_values_current.append(revenue_curr / tickets_curr if tickets_curr > 0 else 0)
        
        revenue_prev = date_map_revenue_previous.get(label, 0)
        tickets_prev = date_map_tickets_previous.get(label, 0)
        basket_values_previous.append(revenue_prev / tickets_prev if tickets_prev > 0 else 0)
    
    total_current = float(stats_current.get('total_revenue') or 0)
    total_previous = float(stats_previous.get('total_revenue') or 0)
    total_tickets_current = stats_current.get('total_tickets') or 0
    total_tickets_previous = stats_previous.get('total_tickets') or 0
    total_items_current = stats_current.get('total_items') or 0
    total_items_previous = stats_previous.get('total_items') or 0
    avg_basket_current = stats_current.get('avg_basket') or 0
    avg_basket_previous = stats_previous.get('avg_basket') or 0
    discount_share_current = stats_current.get('discount_share') or 0
    discount_share_previous = stats_previous.get('discount)share') or 0
    
    def calc_change(current, previous):
        if previous and previous > 0:
            return ((current - previous) / previous) * 100
        return 0
    
    percentage_change = calc_change(total_current, total_previous)
    tickets_change = calc_change(total_tickets_current, total_tickets_previous)
    items_change = calc_change(total_items_current, total_items_previous)
    basket_change = calc_change(avg_basket_current, avg_basket_previous)
    discount_share_change = calc_change(discount_share_current, discount_share_previous)
    
    cross_sell_change = calc_change(
        cross_sell_current['cross_sell_percentage'],
        cross_sell_previous['cross_sell_percentage']
    )
    
    single_item_change = calc_change(
        cross_sell_current['single_item_percentage'],
        cross_sell_previous['single_item_percentage']
    )
    dist_avg_change = calc_change(dist_current['avg_ticket'], dist_previous['avg_ticket'])
    dist_median_change = calc_change(dist_current['median_ticket'], dist_previous['median_ticket'])

    # Prepare data for charts
    distribution_labels = ['0-50', '50-100', '100-150', '150-200', '200-300', '300-500', '500-1K', '1K+']
    distribution_counts_current = [dist_current['distribution'][label] for label in distribution_labels]
    distribution_counts_previous = [dist_previous['distribution'][label] for label in distribution_labels]
    distribution_pct_current = [dist_current['distribution_pct'][label] for label in distribution_labels]
    distribution_pct_previous = [dist_previous['distribution_pct'][label] for label in distribution_labels]
    
    conversion_rate_current = (total_tickets_current / total_items_current * 100) if total_items_current > 0 else 0
    conversion_rate_previous = (total_tickets_previous / total_items_previous * 100) if total_items_previous > 0 else 0
    conversion_change = calc_change(conversion_rate_current, conversion_rate_previous)
    
    # Active locations count
    active_locations_query_current = Sales.objects.filter(**date_filter_current)
    active_locations_query_previous = Sales.objects.filter(**date_filter_previous)
    
    active_locations_query_current = apply_filters(active_locations_query_current)
    active_locations_query_previous = apply_filters(active_locations_query_previous)
    
    active_locations_current = active_locations_query_current.values('un').distinct().count()
    active_locations_previous = active_locations_query_previous.values('un').distinct().count()
    locations_change = calc_change(active_locations_current, active_locations_previous)


    # After dist_current and dist_previous
    employee_stats_current = get_employee_stats(current_year, is_current=True)
    employee_stats_previous = get_employee_stats(previous_year, is_current=False)

    # Create a comparison dictionary for previous year data
    employee_previous_dict = {emp['name']: emp for emp in employee_stats_previous}

    # Add comparison data to current stats
    for emp in employee_stats_current:
        prev_data = employee_previous_dict.get(emp['name'], {})
        emp['revenue_previous'] = prev_data.get('revenue', 0)
        emp['tickets_previous'] = prev_data.get('tickets', 0)
        emp['revenue_change'] = calc_change(emp['revenue'], emp['revenue_previous'])
        emp['tickets_change'] = calc_change(emp['tickets'], emp['tickets_previous'])
    
    # Monthly tickets
    monthly_tickets_current = apply_filters(Sales.objects.filter(**date_filter_current))
    monthly_tickets_previous = apply_filters(Sales.objects.filter(**date_filter_previous))
    
    monthly_tickets_current = list(monthly_tickets_current.annotate(
        month=ExtractMonth('cd')
    ).values('month').annotate(
        tickets=Count('zedd', distinct=True)
    ).order_by('month'))
    
    monthly_tickets_previous = list(monthly_tickets_previous.annotate(
        month=ExtractMonth('cd')
    ).values('month').annotate(
        tickets=Count('zedd', distinct=True)
    ).order_by('month'))
    
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    tickets_data_current = [0] * 12
    tickets_data_previous = [0] * 12
    
    for item in monthly_tickets_current:
        tickets_data_current[item['month'] - 1] = item['tickets']
    
    for item in monthly_tickets_previous:
        tickets_data_previous[item['month'] - 1] = item['tickets']
    
    # Monthly basket
    monthly_basket_current = apply_filters(Sales.objects.filter(**date_filter_current))
    monthly_basket_current = list(monthly_basket_current.annotate(
        month=ExtractMonth('cd')
    ).values('month').annotate(
        total_revenue=Sum('tanxa'),
        total_tickets=Count('zedd', distinct=True)
    ).order_by('month'))
    
    basket_data_current = [0] * 12
    for item in monthly_basket_current:
        if item['total_tickets'] and item['total_tickets'] > 0:
            basket_data_current[item['month'] - 1] = float(item['total_revenue'] or 0) / item['total_tickets']
    
    # Recent transactions
    recent_transactions = apply_filters(Sales.objects.filter(**date_filter_current).exclude(un = 'მთავარი საწყობი 2'))
    recent_transactions = recent_transactions.order_by('-cd', '-idreal1')[:20]
    
    # Category data
    category_query = apply_filters(Sales.objects.filter(**date_filter_current))
    category_data = list(category_query.values('prodg').annotate(
        total=Sum('tanxa')
    ).order_by('-total')[:8])
    
    # Add this section to replace the existing product data section in your views.py
# Add this section to replace the existing product data section in your views.py
# This goes after the category_query definition

# Enhanced Product Analysis with RFM-style metrics
    # Get all products with comprehensive metrics
# Add this section to replace the existing product data section in your views.py
# This goes after the category_query definition

# Enhanced Product Analysis with RFM-style metrics

    # Get all products with comprehensive metrics
    updt_category_query = category_query.exclude(prodg='POP')
    
    all_prod_data = list(
        updt_category_query
        .values('prod', 'idprod')
        .annotate(
            total_revenue=Sum('tanxa'),
            quantity=Count('idreal1'),
            tickets=Count('zedd', distinct=True),
            avg_ticket_value=Avg('tanxa'),
            last_purchase_date=Max('cd'),
            prod_code=Min('idprod')
        )
    )

    # Calculate performance metrics for each product
    # Use the filtered end_date as the reference point for recency
    reference_date = end_datetime  # This comes from your date filter (already timezone-aware)

    for product in all_prod_data:
        # Recency: Days since last purchase (relative to filtered end date)
        if product['last_purchase_date']:
            last_purchase = product['last_purchase_date']
            if timezone.is_naive(last_purchase):
                last_purchase = timezone.make_aware(last_purchase)
            
            days_since = (reference_date - last_purchase).days
            product['recency_days'] = days_since
            product['recency_score'] = max(0, 100 - days_since)
        else:
            product['recency_days'] = 999
            product['recency_score'] = 0
        
        # Frequency: Number of times purchased
        product['frequency_score'] = product['tickets']
        
        # Monetary: Average transaction value
        product['monetary_score'] = float(product['avg_ticket_value'] or 0)
        
        # Revenue score - SET THIS FIRST before using it
        product['revenue'] = float(product['total_revenue'] or 0)

    # NOW calculate normalized scores AFTER all products have 'revenue' set
    for product in all_prod_data:
        # Only calculate if there are products with revenue
        products_with_revenue = [p for p in all_prod_data if p.get('revenue', 0) > 0]
        
        if not products_with_revenue:
            product['performance_score'] = 0
            product['tier'] = 'D'
            product['tier_label'] = 'No Sales'
            continue
        
        # Composite Performance Score
        # Weights: Revenue 40%, Frequency 30%, Recency 20%, Avg Value 10%
        
        # Normalize revenue to 0-100 scale (relative to max in dataset)
        max_revenue = max(p['revenue'] for p in products_with_revenue)
        revenue_normalized = (product['revenue'] / max_revenue * 100) if max_revenue > 0 else 0
        
        # Normalize frequency to 0-100 scale
        max_frequency = max(p['tickets'] for p in all_prod_data if p['tickets'] > 0)
        frequency_normalized = (product['tickets'] / max_frequency * 100) if max_frequency > 0 else 0
        
        # Normalize monetary to 0-100 scale
        max_monetary = max(p['monetary_score'] for p in all_prod_data if p['monetary_score'] > 0)
        monetary_normalized = (product['monetary_score'] / max_monetary * 100) if max_monetary > 0 else 0
        
        # Calculate weighted composite score
        product['performance_score'] = (
            revenue_normalized * 0.40 +      # Revenue importance: 40%
            frequency_normalized * 0.30 +    # Purchase frequency: 30%
            product['recency_score'] * 0.20 +  # Recency: 20%
            monetary_normalized * 0.10       # Average value: 10%
        )
        
        # Performance rating (S, A, B, C, D tier)
        if product['performance_score'] >= 80:
            product['tier'] = 'S'
            product['tier_label'] = 'Top Performer'
        elif product['performance_score'] >= 60:
            product['tier'] = 'A'
            product['tier_label'] = 'Strong Seller'
        elif product['performance_score'] >= 40:
            product['tier'] = 'B'
            product['tier_label'] = 'Average'
        elif product['performance_score'] >= 20:
            product['tier'] = 'C'
            product['tier_label'] = 'Weak Seller'
        else:
            product['tier'] = 'D'
            product['tier_label'] = 'Poor Performer'
    # BESTSELLERS: Top 15 by performance score
    bestsellers = sorted(
        [p for p in all_prod_data if p['revenue'] > 0],
        key=lambda x: x['performance_score'],
        reverse=True
    )[:15]

    # LEAST SELLERS: Bottom 15 by performance score (only products with some sales)
    least_sellers = sorted(
        [p for p in all_prod_data if p['revenue'] > 0],
        key=lambda x: x['performance_score']
    )[:15]

    # SLOW MOVERS: Products not purchased in last 30 days of the filtered period
    slow_movers = sorted(
        [p for p in all_prod_data if p['recency_days'] > 30 and p['revenue'] > 0],
        key=lambda x: x['recency_days'],
        reverse=True
    )[:10]

    # RISING STARS: Products with high recency score within filtered period (new popular items)
    # Products purchased recently (within 30 days before end_date) with moderate revenue
    rising_stars = sorted(
        [p for p in all_prod_data if p['recency_score'] > 70 and p['revenue'] > 0],
        key=lambda x: (x['recency_score'], x['frequency_score']),
        reverse=True
    )[:10]

    # Original top sellers by revenue only (for backward compatibility)
    prod_data = sorted(all_prod_data, key=lambda x: x['revenue'], reverse=True)[:10]

   

    top_10_zedd = list(
        category_query
        .values('zedd')
        .annotate(
            total=Sum('tanxa'),
            quantity=Count('idreal1'),
            transaction_locations = Max('un')
        )
        .order_by('-total')[:10]
    )


    category_labels = [item['prodg'] or 'Unknown' for item in category_data]    
    category_values = [float(item['total'] or 0) for item in category_data]
    
    # Category comparison
    category_query_previous_comp = Sales.objects.filter(**date_filter_previous)
    category_query_current_comp = Sales.objects.filter(**date_filter_current)
    
    if selected_locations:
        category_query_previous_comp = category_query_previous_comp.filter(un__in=selected_locations)
        category_query_current_comp = category_query_current_comp.filter(un__in=selected_locations)  
    if selected_campaign != 'all':
        category_query_previous_comp = category_query_previous_comp.filter(actions=selected_campaign)
        category_query_current_comp = category_query_current_comp.filter(actions=selected_campaign)
        
    category_data_current_comp = list(category_query_current_comp.values('prodg').annotate(
        total=Sum('tanxa')
    ).order_by('-total')[:10])
    
    top_categories = [item['prodg'] for item in category_data_current_comp]
    category_data_previous_comp = list(category_query_previous_comp.filter(
        prodg__in=top_categories
    ).values('prodg').annotate(
        total=Sum('tanxa')
    ))
    
    cat_previous_dict = {item['prodg']: float(item['total'] or 0) for item in category_data_previous_comp}
    
    category_comparison = []
    for item in category_data_current_comp:
        cat_name = item['prodg'] or 'Unknown'
        revenue_current = float(item['total'] or 0)
        revenue_previous = cat_previous_dict.get(item['prodg'], 0)
        
        change = revenue_current - revenue_previous
        pct_change = calc_change(revenue_current, revenue_previous)
        
        category_comparison.append({
            'name': cat_name,
            'revenue_previous': revenue_previous,
            'revenue_current': revenue_current,
            'change': change,
            'pct_change': pct_change
        })
    
    def format_currency(value):
        if value >= 1000000:
            return f"${value/1000000:.1f}M"
        elif value >= 1000:
            return f"${value/1000:.1f}K"
        return f"${value:.2f}"
    
    def format_number(value):
        if value >= 1000000:
            return f"{value/1000000:.1f}M"
        elif value >= 1000:
            return f"{value/1000:.1f}K"
        return f"{int(value)}"
    
    all_locations = (
        Sales.objects
        .filter(cd__year=current_year)
        .values_list('un', flat=True)
        .distinct()
        .order_by('un')
    )
    
    all_categories = (
        Sales.objects
        .filter(cd__year=current_year)
        .values_list('prodg', flat=True)
        .distinct()
        .order_by('prodg')
    )
    
    all_campaigns = (
        Sales.objects
        .filter(cd__year=current_year)
        .values_list('actions', flat=True)
        .distinct()
        .order_by('actions')
    )
    
    all_products = (
        Sales.objects
        .filter(cd__year=current_year)
        .values_list('prod', flat=True)
        .distinct()
        .order_by('prod')
    )

    date_range_text = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}, {current_year}"
   


    if user_profile.is_admin:
        all_locations = (
            Sales.objects
            .filter(cd__year=current_year)
            .values_list('un', flat=True)
            .distinct()
            .order_by('un')
        )
    else:
        # Only show locations this user can access
        all_locations = allowed_locations

    context = {
        'comparison_mode': comparison_mode,
        'current_year': current_year,
        'previous_year': previous_year,
        'max_date': max_date,
        'date_range_text': date_range_text,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        
        'labels': json.dumps(labels),
        'data_previous': json.dumps(values_previous),
        'data_current': json.dumps(values_current),
        'tickets_values_current': json.dumps(tickets_values_current),
        'tickets_values_previous': json.dumps(tickets_values_previous),
        'items_values_current': json.dumps(items_values_current),
        'items_values_previous': json.dumps(items_values_previous),
        'basket_values_current': json.dumps(basket_values_current),
        'basket_values_previous': json.dumps(basket_values_previous),
        'single_item_pct_current': json.dumps(single_item_pct_current),
        'single_item_pct_previous': json.dumps(single_item_pct_previous),
        'cross_sell_pct_current': json.dumps(cross_sell_pct_current),
        'cross_sell_pct_previous': json.dumps(cross_sell_pct_previous),
        'discount_share_previous':json.dumps(discount_share_previous),
        'discount_share_current':json.dumps(discount_share_current),
        
        'month_labels': json.dumps(month_labels),
        'tickets_data_previous': json.dumps(tickets_data_previous),
        'tickets_data_current': json.dumps(tickets_data_current),
        'basket_data_current': json.dumps(basket_data_current),
        
        'category_labels': json.dumps(category_labels),
        'category_values': json.dumps(category_values),
        'category_comparison': category_comparison,
        
        'total_current': format_currency(total_current),
        'total_previous': format_currency(total_previous),
        'total_tickets': format_number(total_tickets_current),
        'total_items': format_number(total_items_current),
        'avg_basket': f"${avg_basket_current:.2f}",
        'conversion_rate': conversion_rate_current,
        'active_customers': format_number(active_locations_current),
        
        'cross_sell_percentage_current': cross_sell_current['cross_sell_percentage'],
        'cross_sell_percentage_previous': cross_sell_previous['cross_sell_percentage'],
        'cross_sell_change': cross_sell_change,
        'single_item_percentage_current': cross_sell_current['single_item_percentage'],
        'single_item_percentage_previous': cross_sell_previous['single_item_percentage'],
        'single_item_change': single_item_change,
        
        'percentage_change': percentage_change,
        'tickets_change': tickets_change,
        'basket_change': basket_change,
        'items_change': items_change,
        'conversion_change': conversion_change,
        'customers_change': locations_change,
        'discount_share_precentage_change':discount_share_change,
        
        'employee_stats': employee_stats_current,
        'employee_stats_previous': employee_stats_previous,

        'recent_transactions': recent_transactions,
        'prod_dt': prod_data,
        
        'all_locations': all_locations,
        'all_categories': all_categories,
        'all_campaigns': all_campaigns,
        'selected_un': selected_un,
        'selected_locations': selected_locations,  # Added for template
        'selected_category': selected_category,
        'selected_product': selected_product,
        'products': all_products,
        'high_zedd':top_10_zedd,


        'distribution_labels': json.dumps(distribution_labels),
        'distribution_counts_current': json.dumps(distribution_counts_current),
        'distribution_counts_previous': json.dumps(distribution_counts_previous),
        'distribution_pct_current': json.dumps(distribution_pct_current),
        'distribution_pct_previous': json.dumps(distribution_pct_previous),
        
        # Distribution statistics
        'dist_avg_current': dist_current['avg_ticket'],
        'dist_avg_previous': dist_previous['avg_ticket'],
        'dist_avg_change': dist_avg_change,
        'dist_median_current': dist_current['median_ticket'],
        'dist_median_previous': dist_previous['median_ticket'],
        'dist_median_change': dist_median_change,
        'dist_p25_current': dist_current['p25'],
        'dist_p75_current': dist_current['p75'],
        'dist_total_tickets_current': dist_current['total_tickets'],
        'dist_total_tickets_previous': dist_previous['total_tickets'],


        'user_profile': user_profile,
        'is_admin': user_profile.is_admin,
        'user_locations_count': len(allowed_locations) if not user_profile.is_admin else 'All',


        'bestsellers': bestsellers,
        'least_sellers': least_sellers,
        'slow_movers': slow_movers,
        'rising_stars': rising_stars,
        'prod_dt': prod_data,  # Keep the original for existing displays
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def plan_workflow(request):
    try:
        user_profile = request.user.profile
    except:
        return HttpResponseForbidden("Access denied. Contact administrator.")
    
    # Get allowed locations for this user
    allowed_locations_user = user_profile.get_allowed_locations()
    
    # Get filter parameters
    selected_year = request.GET.get('year', '2024')
    selected_start_month = request.GET.get('start_month', '1')
    selected_end_month = request.GET.get('end_month', '12')
    selected_geo = request.GET.get('location', 'all')
    
    # SECURITY CHECK: Validate location access
    if not user_profile.is_admin:
        if selected_geo == 'all':
            # Non-admin can't select "all" - default to first allowed location
            if allowed_locations_user:
                selected_geo = allowed_locations_user[0]
            else:
                return HttpResponseForbidden("No locations assigned. Contact administrator.")
        elif selected_geo not in allowed_locations_user:
            messages.warning(request, f"Access denied to location: {selected_geo}")
            selected_geo = allowed_locations_user[0] if allowed_locations_user else 'all'

    aggregation = request.GET.get('aggregation', 'daily')
    show_prev_year = request.GET.get('show_prev_year', 'false')
    
    # Convert to dates
    year = int(selected_year)
    start_month = int(selected_start_month)
    end_month = int(selected_end_month)
    
    start_date = date(year, start_month, 1)
    _, last_day = calendar.monthrange(year, end_month)
    end_date = date(year, end_month, last_day)
    
    # Previous year dates
    prev_year = year - 1
    start_date_py = date(prev_year, start_month, 1)
    _, last_day_py = calendar.monthrange(prev_year, end_month)
    end_date_py = date(prev_year, end_month, last_day_py)
    
    # Read Excel file
    path = os.path.join(settings.BASE_DIR, 'sales_app', 'data', 'Full Plan workflow.xlsx')
    
    try:
        df = pd.read_excel(path, engine='openpyxl', sheet_name='Main')
        
        print("Excel Columns:", df.columns.tolist())
        print("Sample data:")
        print(df[['location', 'geo', 'Year', 'Month', 'Plan_turnover', 'Plan_tickets', 'Plan_basket']].head(5))
        print(f"\nYear range in Excel: {df['Year'].min()} - {df['Year'].max()}")
        print(f"Month range in Excel: {df['Month'].min()} - {df['Month'].max()}")
        
        # Convert Year and Month columns to integers
        df['Year'] = df['Year'].astype(int)
        df['Month'] = df['Month'].astype(int)
        
        # Create datetime for each month
        df['plan_date'] = pd.to_datetime(df[['Year', 'Month']].assign(day=1))
        
        # ===== PROCESS CURRENT YEAR DATA =====
        df_current = df.copy()
        start_month_date = pd.Timestamp(start_date.replace(day=1))
        end_month_date = pd.Timestamp(end_date.replace(day=1))
        df_current = df_current[(df_current['plan_date'] >= start_month_date) & (df_current['plan_date'] <= end_month_date)]
        
        if selected_geo != 'all':
            df_current = df_current[df_current['geo'] == selected_geo]
        
        print(f"\nFiltered current year to {len(df_current)} plan records between {start_month_date.strftime('%Y-%m')} and {end_month_date.strftime('%Y-%m')}")
        
        # ===== PROCESS PREVIOUS YEAR DATA =====
        df_prev = df.copy()
        start_month_date_py = pd.Timestamp(start_date_py.replace(day=1))
        end_month_date_py = pd.Timestamp(end_date_py.replace(day=1))
        df_prev = df_prev[(df_prev['plan_date'] >= start_month_date_py) & (df_prev['plan_date'] <= end_month_date_py)]
        
        if selected_geo != 'all':
            df_prev = df_prev[df_prev['geo'] == selected_geo]
        
        print(f"Filtered previous year to {len(df_prev)} plan records between {start_month_date_py.strftime('%Y-%m')} and {end_month_date_py.strftime('%Y-%m')}")
        
        # ===== GET ACTUAL SALES DATA - CURRENT YEAR =====
        actual_query = Sales.objects.filter(
            cd__gte=start_date,
            cd__lte=end_date
        ).exclude(un__in=["მთავარი საწყობი 2", "სატესტო"])
        
        if selected_geo != 'all':
            actual_query = actual_query.filter(un=selected_geo)
        
        daily_actual = list(actual_query.values('un', 'cd').annotate(
            actual_turnover=Sum('tanxa'),
            tickets=Count('zedd', distinct=True)
        ).order_by('cd'))
        
        print(f"\nRetrieved {len(daily_actual)} daily actual records from DB (current year)")
        
        # ===== GET ACTUAL SALES DATA - PREVIOUS YEAR =====
        actual_query_py = Sales.objects.filter(
            cd__gte=start_date_py,
            cd__lte=end_date_py
        ).exclude(un__in=["მთავარი საწყობი 2", "სატესტო"])
        
        if selected_geo != 'all':
            actual_query_py = actual_query_py.filter(un=selected_geo)
        
        daily_actual_py = list(actual_query_py.values('un', 'cd').annotate(
            actual_turnover=Sum('tanxa'),
            tickets=Count('zedd', distinct=True)
        ).order_by('cd'))
        
        print(f"Retrieved {len(daily_actual_py)} daily actual records from DB (previous year)")
        
        # ===== EXPAND PLANS TO DAILY - CURRENT YEAR =====
        def expand_to_daily(df_source, target_start, target_end):
            """Expand monthly plan data to daily records"""
            daily_records = []
            
            for _, row in df_source.iterrows():
                geo = row['geo']
                year_row = int(row['Year'])
                month_row = int(row['Month'])
                monthly_plan = float(row['Plan_turnover'])
                monthly_tickets = float(row['Plan_tickets'])
                avg_basket = float(row['Plan_basket'])  # This stays constant
                
                days_in_month = calendar.monthrange(year_row, month_row)[1]
                daily_plan_value = monthly_plan / days_in_month
                daily_tickets_value = monthly_tickets / days_in_month
                
                for day in range(1, days_in_month + 1):
                    current_date = date(year_row, month_row, day)
                    
                    if target_start <= current_date <= target_end:
                        daily_records.append({
                            'geo': geo,
                            'date': current_date,
                            'daily_plan': daily_plan_value,
                            'daily_tickets': daily_tickets_value,
                            'avg_basket': avg_basket,
                            'year': year_row,
                            'month': month_row,
                            'day': day
                        })
            
            return daily_records
        
        plan_daily_records = expand_to_daily(df_current, start_date, end_date)
        plan_daily_records_py = expand_to_daily(df_prev, start_date_py, end_date_py)
        
        print(f"\nExpanded to {len(plan_daily_records)} daily plan records (current year)")
        print(f"Expanded to {len(plan_daily_records_py)} daily plan records (previous year)")
        
        # ===== AGGREGATION HELPER FUNCTION =====
        def aggregate_data(plan_records, actual_records, agg_type, date_range_start, date_range_end):
            """Aggregate plan and actual data based on aggregation type"""
            labels = []
            plan_values = []
            plan_85_values = []
            actual_values = []
            tickets_plan_values = []
            tickets_actual_values = []
            basket_plan_values = []
            basket_actual_values = []
            
            if agg_type == 'monthly':
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                
                # Aggregate plan data by month
                plan_monthly = {}
                tickets_monthly = {}
                basket_monthly = {}
                basket_count = {}
                
                for record in plan_records:
                    month_key = f"{record['year']}-{record['month']:02d}"
                    plan_monthly[month_key] = plan_monthly.get(month_key, 0) + record['daily_plan']
                    tickets_monthly[month_key] = tickets_monthly.get(month_key, 0) + record['daily_tickets']
                    basket_monthly[month_key] = basket_monthly.get(month_key, 0) + record['avg_basket']
                    basket_count[month_key] = basket_count.get(month_key, 0) + 1
                
                # Aggregate actual data by month
                actual_monthly = {}
                tickets_actual_monthly = {}
                
                for record in actual_records:
                    month_key = f"{record['cd'].year}-{record['cd'].month:02d}"
                    actual_monthly[month_key] = actual_monthly.get(month_key, 0) + float(record['actual_turnover'] or 0)
                    tickets_actual_monthly[month_key] = tickets_actual_monthly.get(month_key, 0) + int(record['tickets'] or 0)
                
                # Generate labels for all months in range
                current = date_range_start.replace(day=1)
                while current <= date_range_end:
                    month_key = f"{current.year}-{current.month:02d}"
                    labels.append(f"{month_names[current.month-1]} '{str(current.year)[-2:]}")
                    
                    plan_val = plan_monthly.get(month_key, 0)
                    plan_values.append(plan_val)
                    plan_85_values.append(plan_val * 0.85)
                    actual_values.append(actual_monthly.get(month_key, 0))
                    tickets_plan_values.append(tickets_monthly.get(month_key, 0))
                    tickets_actual_values.append(tickets_actual_monthly.get(month_key, 0))
                    
                    # Average basket for the month
                    if basket_count.get(month_key, 0) > 0:
                        basket_plan_values.append(basket_monthly.get(month_key, 0) / basket_count[month_key])
                    else:
                        basket_plan_values.append(0)
                    
                    actual_rev = actual_monthly.get(month_key, 0)
                    actual_tick = tickets_actual_monthly.get(month_key, 0)
                    basket_actual_values.append(actual_rev / actual_tick if actual_tick > 0 else 0)
                    
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)
            
            elif agg_type == 'weekly':
                # Aggregate by ISO week
                plan_weekly = {}
                tickets_weekly = {}
                basket_weekly = {}
                basket_count = {}
                
                for record in plan_records:
                    iso_cal = record['date'].isocalendar()
                    week_key = f"{iso_cal[0]}-W{iso_cal[1]:02d}"
                    plan_weekly[week_key] = plan_weekly.get(week_key, 0) + record['daily_plan']
                    tickets_weekly[week_key] = tickets_weekly.get(week_key, 0) + record['daily_tickets']
                    basket_weekly[week_key] = basket_weekly.get(week_key, 0) + record['avg_basket']
                    basket_count[week_key] = basket_count.get(week_key, 0) + 1
                
                actual_weekly = {}
                tickets_actual_weekly = {}
                
                for record in actual_records:
                    iso_cal = record['cd'].isocalendar()
                    week_key = f"{iso_cal[0]}-W{iso_cal[1]:02d}"
                    actual_weekly[week_key] = actual_weekly.get(week_key, 0) + float(record['actual_turnover'] or 0)
                    tickets_actual_weekly[week_key] = tickets_actual_weekly.get(week_key, 0) + int(record['tickets'] or 0)
                
                # Generate all weeks in range
                current = date_range_start
                seen_weeks = set()
                while current <= date_range_end:
                    iso_cal = current.isocalendar()
                    week_key = f"{iso_cal[0]}-W{iso_cal[1]:02d}"
                    
                    if week_key not in seen_weeks:
                        seen_weeks.add(week_key)
                        labels.append(f"W{iso_cal[1]} '{str(iso_cal[0])[-2:]}")
                        
                        plan_val = plan_weekly.get(week_key, 0)
                        plan_values.append(plan_val)
                        plan_85_values.append(plan_val * 0.85)
                        actual_values.append(actual_weekly.get(week_key, 0))
                        tickets_plan_values.append(tickets_weekly.get(week_key, 0))
                        tickets_actual_values.append(tickets_actual_weekly.get(week_key, 0))
                        
                        if basket_count.get(week_key, 0) > 0:
                            basket_plan_values.append(basket_weekly.get(week_key, 0) / basket_count[week_key])
                        else:
                            basket_plan_values.append(0)
                        
                        actual_rev = actual_weekly.get(week_key, 0)
                        actual_tick = tickets_actual_weekly.get(week_key, 0)
                        basket_actual_values.append(actual_rev / actual_tick if actual_tick > 0 else 0)
                    
                    current += timedelta(days=1)
            
            else:  # Daily aggregation (default)
                # Create maps by date
                plan_map = {}
                tickets_map = {}
                basket_map = {}
                basket_count = {}
                
                for record in plan_records:
                    date_key = record['date'].strftime('%Y-%m-%d')
                    plan_map[date_key] = plan_map.get(date_key, 0) + record['daily_plan']
                    tickets_map[date_key] = tickets_map.get(date_key, 0) + record['daily_tickets']
                    basket_map[date_key] = basket_map.get(date_key, 0) + record['avg_basket']
                    basket_count[date_key] = basket_count.get(date_key, 0) + 1
                
                actual_map = {}
                tickets_actual_map = {}
                
                for record in actual_records:
                    date_key = record['cd'].strftime('%Y-%m-%d')
                    actual_map[date_key] = actual_map.get(date_key, 0) + float(record['actual_turnover'] or 0)
                    tickets_actual_map[date_key] = tickets_actual_map.get(date_key, 0) + int(record['tickets'] or 0)
                
                # Generate all dates in range
                current = date_range_start
                while current <= date_range_end:
                    date_key = current.strftime('%Y-%m-%d')
                    labels.append(current.strftime('%b %d'))
                    
                    plan_val = plan_map.get(date_key, 0)
                    plan_values.append(plan_val)
                    plan_85_values.append(plan_val * 0.85)
                    actual_values.append(actual_map.get(date_key, 0))
                    tickets_plan_values.append(tickets_map.get(date_key, 0))
                    tickets_actual_values.append(tickets_actual_map.get(date_key, 0))
                    
                    if basket_count.get(date_key, 0) > 0:
                        basket_plan_values.append(basket_map.get(date_key, 0) / basket_count[date_key])
                    else:
                        basket_plan_values.append(0)
                    
                    actual_rev = actual_map.get(date_key, 0)
                    actual_tick = tickets_actual_map.get(date_key, 0)
                    basket_actual_values.append(actual_rev / actual_tick if actual_tick > 0 else 0)
                    
                    current += timedelta(days=1)
            
            return {
                'labels': labels,
                'plan_values': plan_values,
                'plan_85_values': plan_85_values,
                'actual_values': actual_values,
                'tickets_plan_values': tickets_plan_values,
                'tickets_actual_values': tickets_actual_values,
                'basket_plan_values': basket_plan_values,
                'basket_actual_values': basket_actual_values
            }
        
        # Aggregate current year data
        current_data = aggregate_data(plan_daily_records, daily_actual, aggregation, start_date, end_date)
        
        # Aggregate previous year data
        prev_data = aggregate_data(plan_daily_records_py, daily_actual_py, aggregation, start_date_py, end_date_py)
        
        # ===== CALCULATE KPIs - REVENUE =====
        total_plan = sum(current_data['plan_values'])
        total_plan_85 = sum(current_data['plan_85_values'])
        total_actual = sum(current_data['actual_values'])
        plan_achievement = (total_actual / total_plan * 100) if total_plan > 0 else 0
        variance = total_actual - total_plan
        variance_85 = total_actual - total_plan_85
        variance_pct = ((variance / total_plan) * 100) if total_plan > 0 else 0
        variance_pct_85 = ((variance_85 / total_plan_85) * 100) if total_plan_85 > 0 else 0
        
        # ===== CALCULATE KPIs - TICKETS =====
        total_tickets_plan = sum(current_data['tickets_plan_values'])
        total_tickets_actual = sum(current_data['tickets_actual_values'])
        tickets_achievement = (total_tickets_actual / total_tickets_plan * 100) if total_tickets_plan > 0 else 0
        tickets_variance = total_tickets_actual - total_tickets_plan
        tickets_variance_pct = ((tickets_variance / total_tickets_plan) * 100) if total_tickets_plan > 0 else 0
        
        # ===== CALCULATE KPIs - BASKET =====
        # Average across all data points (since basket is per period, not summed)
        avg_basket_plan = sum(current_data['basket_plan_values']) / len(current_data['basket_plan_values']) if len(current_data['basket_plan_values']) > 0 else 0
        avg_basket_actual = sum(current_data['basket_actual_values']) / len(current_data['basket_actual_values']) if len(current_data['basket_actual_values']) > 0 else 0
        basket_achievement = (avg_basket_actual / avg_basket_plan * 100) if avg_basket_plan > 0 else 0
        basket_variance = avg_basket_actual - avg_basket_plan
        basket_variance_pct = ((basket_variance / avg_basket_plan) * 100) if avg_basket_plan > 0 else 0
        
        # ===== LOCATION PERFORMANCE TABLE - REVENUE =====
        location_performance = []
        
        if selected_geo == 'all':
            unique_geos = df_current['geo'].unique()
            
            for geo in unique_geos:
                # Current Year
                loc_plan_records = [p for p in plan_daily_records if p['geo'] == geo]
                loc_plan = sum([p['daily_plan'] for p in loc_plan_records])
                
                loc_actual_data = actual_query.filter(un=geo).aggregate(total=Sum('tanxa'))
                loc_actual = float(loc_actual_data['total'] or 0)
                
                # Previous Year
                loc_plan_records_py = [p for p in plan_daily_records_py if p['geo'] == geo]
                loc_plan_py = sum([p['daily_plan'] for p in loc_plan_records_py])
                
                loc_actual_data_py = actual_query_py.filter(un=geo).aggregate(total=Sum('tanxa'))
                loc_actual_py = float(loc_actual_data_py['total'] or 0)
                
                # Metrics
                loc_variance = loc_actual - loc_plan
                loc_achievement = (loc_actual / loc_plan * 100) if loc_plan > 0 else 0
                yoy_growth = ((loc_actual - loc_actual_py) / loc_actual_py * 100) if loc_actual_py > 0 else 0
                yoy_growth_plan = ((loc_plan - loc_plan_py) / loc_plan_py * 100) if loc_plan_py > 0 else 0
                
                location_performance.append({
                    'geo': geo,
                    'plan': loc_plan,
                    'actual': loc_actual,
                    'plan_py': loc_plan_py,
                    'actual_py': loc_actual_py,
                    'variance': loc_variance,
                    'achievement': loc_achievement,
                    'yoy_growth': yoy_growth,
                    'yoy_growth_plan':yoy_growth_plan
                })
            
            location_performance.sort(key=lambda x: x['achievement'], reverse=True)
        
        # ===== LOCATION PERFORMANCE TABLE - TICKETS =====
        tickets_location_performance = []
        
        if selected_geo == 'all':
            for geo in unique_geos:
                # Current Year
                loc_tickets_records = [p for p in plan_daily_records if p['geo'] == geo]
                loc_tickets_plan = sum([p['daily_tickets'] for p in loc_tickets_records])
                
                loc_tickets_data = actual_query.filter(un=geo).aggregate(total=Count('zedd', distinct=True))
                loc_tickets_actual = int(loc_tickets_data['total'] or 0)
                
                # Previous Year
                loc_tickets_records_py = [p for p in plan_daily_records_py if p['geo'] == geo]
                loc_tickets_plan_py = sum([p['daily_tickets'] for p in loc_tickets_records_py])
                
                loc_tickets_data_py = actual_query_py.filter(un=geo).aggregate(total=Count('zedd', distinct=True))
                loc_tickets_actual_py = int(loc_tickets_data_py['total'] or 0)
                
                # Metrics
                loc_variance = loc_tickets_actual - loc_tickets_plan
                loc_achievement = (loc_tickets_actual / loc_tickets_plan * 100) if loc_tickets_plan > 0 else 0
                yoy_growth = ((loc_tickets_actual - loc_tickets_actual_py) / loc_tickets_actual_py * 100) if loc_tickets_actual_py > 0 else 0
                
                tickets_location_performance.append({
                    'geo': geo,
                    'plan': loc_tickets_plan,
                    'actual': loc_tickets_actual,
                    'plan_py': loc_tickets_plan_py,
                    'actual_py': loc_tickets_actual_py,
                    'variance': loc_variance,
                    'achievement': loc_achievement,
                    'yoy_growth': yoy_growth
                })
            
            tickets_location_performance.sort(key=lambda x: x['achievement'], reverse=True)
        
        # ===== LOCATION PERFORMANCE TABLE - BASKET =====
        basket_location_performance = []
        
        if selected_geo == 'all':
            for geo in unique_geos:
                # Current Year
                loc_basket_records = [p for p in plan_daily_records if p['geo'] == geo]
                loc_basket_plan = sum([p['avg_basket'] for p in loc_basket_records]) / len(loc_basket_records) if len(loc_basket_records) > 0 else 0
                
                loc_data = actual_query.filter(un=geo).aggregate(
                    total_rev=Sum('tanxa'),
                    total_tickets=Count('zedd', distinct=True)
                )
                loc_basket_actual = (float(loc_data['total_rev'] or 0) / int(loc_data['total_tickets'] or 1)) if loc_data['total_tickets'] else 0
                
                # Previous Year
                loc_basket_records_py = [p for p in plan_daily_records_py if p['geo'] == geo]
                loc_basket_plan_py = sum([p['avg_basket'] for p in loc_basket_records_py]) / len(loc_basket_records_py) if len(loc_basket_records_py) > 0 else 0
                
                loc_data_py = actual_query_py.filter(un=geo).aggregate(
                    total_rev=Sum('tanxa'),
                    total_tickets=Count('zedd', distinct=True)
                )
                loc_basket_actual_py = (float(loc_data_py['total_rev'] or 0) / int(loc_data_py['total_tickets'] or 1)) if loc_data_py['total_tickets'] else 0
                
                # Metrics
                loc_variance = loc_basket_actual - loc_basket_plan
                loc_achievement = (loc_basket_actual / loc_basket_plan * 100) if loc_basket_plan > 0 else 0
                yoy_change = loc_basket_actual - loc_basket_actual_py
                
                basket_location_performance.append({
                    'geo': geo,
                    'plan': loc_basket_plan,
                    'actual': loc_basket_actual,
                    'plan_py': loc_basket_plan_py,
                    'actual_py': loc_basket_actual_py,
                    'variance': loc_variance,
                    'achievement': loc_achievement,
                    'yoy_change': yoy_change
                })
            
            basket_location_performance.sort(key=lambda x: x['achievement'], reverse=True)
        
        # ===== GET LOCATIONS FOR DROPDOWN =====
        all_geos = sorted(df_current['geo'].unique().tolist())
        
        # ===== MONTH OPTIONS FOR DROPDOWN =====
        month_options = [
            {'value': '1', 'label': 'January'},
            {'value': '2', 'label': 'February'},
            {'value': '3', 'label': 'March'},
            {'value': '4', 'label': 'April'},
            {'value': '5', 'label': 'May'},
            {'value': '6', 'label': 'June'},
            {'value': '7', 'label': 'July'},
            {'value': '8', 'label': 'August'},
            {'value': '9', 'label': 'September'},
            {'value': '10', 'label': 'October'},
            {'value': '11', 'label': 'November'},
            {'value': '12', 'label': 'December'},
        ]
        
        # ===== EXCEL SUMMARY =====
        excel_summary = df_current.groupby('geo').agg({
            'Plan_turnover': 'sum'
        }).reset_index().sort_values('Plan_turnover', ascending=False).head(10)
        
        excel_data = [
            {
                'geo': row['geo'],
                'Plan_turnover': row['Plan_turnover']
            }
            for _, row in excel_summary.iterrows()
        ]
        
        file_status = f"✓ Loaded {len(all_geos)} locations with plans from {start_date.strftime('%b %Y')} to {end_date.strftime('%b %Y')}"
        
    except FileNotFoundError:
        # Initialize empty data
        current_data = {
            'labels': [], 'plan_values': [], 'plan_85_values': [], 'actual_values': [],
            'tickets_plan_values': [], 'tickets_actual_values': [],
            'basket_plan_values': [], 'basket_actual_values': []
        }
        prev_data = {
            'labels': [], 'plan_values': [], 'plan_85_values': [], 'actual_values': [],
            'tickets_plan_values': [], 'tickets_actual_values': [],
            'basket_plan_values': [], 'basket_actual_values': []
        }
        excel_data = []
        location_performance = []
        tickets_location_performance = []
        basket_location_performance = []
        all_geos = []
        month_options = []
        total_plan = total_plan_85 = total_actual = plan_achievement = variance = variance_pct = variance_85 = variance_pct_85 = 0
        total_tickets_plan = total_tickets_actual = tickets_achievement = tickets_variance = tickets_variance_pct = 0
        avg_basket_plan = avg_basket_actual = basket_achievement = basket_variance = basket_variance_pct = 0
        file_status = f"✗ Excel file not found at: {path}"
        
    except Exception as e:
        # Initialize empty data
        current_data = {
            'labels': [], 'plan_values': [], 'plan_85_values': [], 'actual_values': [],
            'tickets_plan_values': [], 'tickets_actual_values': [],
            'basket_plan_values': [], 'basket_actual_values': []
        }
        prev_data = {
            'labels': [], 'plan_values': [], 'plan_85_values': [], 'actual_values': [],
            'tickets_plan_values': [], 'tickets_actual_values': [],
            'basket_plan_values': [], 'basket_actual_values': []
        }
        excel_data = []
        location_performance = []
        tickets_location_performance = []
        basket_location_performance = []
        all_geos = []
        month_options = []
        total_plan = total_plan_85 = total_actual = plan_achievement = variance = variance_pct = variance_85 = variance_pct_85 = 0
        total_tickets_plan = total_tickets_actual = tickets_achievement = tickets_variance = tickets_variance_pct = 0
        avg_basket_plan = avg_basket_actual = basket_achievement = basket_variance = basket_variance_pct = 0
        file_status = f"✗ Error: {str(e)}"
        print(f"Error in plan_workflow: {e}")
        import traceback
        traceback.print_exc()

        if user_profile.is_admin:
            all_geos = sorted(df_current['geo'].unique().tolist())
        else:
        # Only show locations this user can access
            all_geos = allowed_locations_user
    
    # Add to context before return
  
    
    # ===== CONTEXT FOR TEMPLATE =====
    context = {
        # Labels (same for all)
        'labels': json.dumps(current_data['labels']),
        
        # Revenue - Current Year
        'plan_values': json.dumps(current_data['plan_values']),
        'plan_85_values': json.dumps(current_data['plan_85_values']),
        'actual_values': json.dumps(current_data['actual_values']),
        
        # Revenue - Previous Year
        'plan_values_py': json.dumps(prev_data['plan_values']),
        'actual_values_py': json.dumps(prev_data['actual_values']),
        
        # Tickets - Current Year
        'tickets_plan_values': json.dumps(current_data['tickets_plan_values']),
        'tickets_actual_values': json.dumps(current_data['tickets_actual_values']),
        
        # Tickets - Previous Year
        'tickets_plan_values_py': json.dumps(prev_data['tickets_plan_values']),
        'tickets_actual_values_py': json.dumps(prev_data['tickets_actual_values']),
        
        # Basket - Current Year
        'basket_plan_values': json.dumps(current_data['basket_plan_values']),
        'basket_actual_values': json.dumps(current_data['basket_actual_values']),
        
        # Basket - Previous Year
        'basket_plan_values_py': json.dumps(prev_data['basket_plan_values']),
        'basket_actual_values_py': json.dumps(prev_data['basket_actual_values']),
        
        # Revenue KPIs
        'total_plan': f"${total_plan:,.0f}",
        'total_plan_85': f"${total_plan_85:,.0f}",
        'total_actual': f"${total_actual:,.0f}",
        'plan_achievement': f"{plan_achievement:.1f}",
        'variance': f"${variance:,.0f}",
        'variance_85': f"${variance_85:,.0f}",
        'variance_pct': f"{variance_pct:+.1f}",
        'variance_pct_85': f"{variance_pct_85:+.1f}",
        
        # Tickets KPIs
        'total_tickets_plan': f"{total_tickets_plan:,.0f}",
        'total_tickets_actual': f"{total_tickets_actual:,.0f}",
        'tickets_achievement': f"{tickets_achievement:.1f}",
        'tickets_variance': f"{tickets_variance:+,.0f}",
        'tickets_variance_pct': f"{tickets_variance_pct:+.1f}",
        
        # Basket KPIs
        'avg_basket_plan': f"{avg_basket_plan:.2f}",
        'avg_basket_actual': f"{avg_basket_actual:.2f}",
        'basket_achievement': f"{basket_achievement:.1f}",
        'basket_variance': f"{basket_variance:+.2f}",
        'basket_variance_pct': f"{basket_variance_pct:+.1f}",
        
        # Location Performance
        'location_performance': location_performance,
        'tickets_location_performance': tickets_location_performance,
        'basket_location_performance': basket_location_performance,
        
        # Other
        'excel_df': excel_data,
        'all_geos': all_geos,
        'selected_geo': selected_geo,
        'selected_year': selected_year,
        'selected_start_month': selected_start_month,
        'selected_end_month': selected_end_month,
        'month_options': month_options,
        'aggregation': aggregation,
        'show_prev_year': show_prev_year,
        'file_status': file_status,
    }

    context['user_profile'] = user_profile
    context['is_admin'] = user_profile.is_admin
    
    return render(request, 'another.html', context)

@login_required
def export_location_csv(request):    

    try:
        user_profile = request.user.profile
    except:
        return HttpResponseForbidden("Access denied. Contact administrator.")
    
    allowed_locations_user = user_profile.get_allowed_locations()
    
    comparison_mode = request.GET.get('comparison', '2025-2024')
    if comparison_mode == '2026-2025':
        current_year = 2026
        previous_year = 2025
    elif comparison_mode == '2026-2024':
        current_year = 2026
        previous_year = 2024
    else:
        current_year = 2025
        previous_year = 2024
    
    # Date filters
    start_date_str = request.GET.get('start_date', f'{current_year}-01-01')
    end_date_str = request.GET.get('end_date', f'{current_year}-12-31')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except:
        start_date = date(current_year, 1, 1)
    
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except:
        end_date = date(current_year, 12, 31)
    
    # Location filter - handle multiple selections with SECURITY CHECK
    selected_locations = request.GET.getlist('un_filter')
    
    if not user_profile.is_admin:
        if not selected_locations or 'all' in selected_locations:
            # Non-admin can't export all - restrict to their locations
            selected_locations = allowed_locations_user
        else:
            # Filter out unauthorized locations
            unauthorized = set(selected_locations) - set(allowed_locations_user)
            if unauthorized:
                messages.warning(request, f"Export access denied to: {', '.join(unauthorized)}")
                selected_locations = [loc for loc in selected_locations if loc in allowed_locations_user]
            
            if not selected_locations:
                selected_locations = allowed_locations_user
    
    if not selected_locations and not user_profile.is_admin:
        return HttpResponseForbidden("You don't have access to export any locations.")
    
    # If admin selected 'all', reset to empty list
    if user_profile.is_admin and (not selected_locations or 'all' in request.GET.getlist('un_filter')):
        selected_locations = []
    
    selected_category = request.GET.get('category', 'all')
    selected_product = request.GET.get('prod_filter', 'all')
    selected_campaign = request.GET.get('campaign_filter', 'all')
    
    def get_location_data(year, start_dt, end_dt):
        """Helper function to get data for a specific year"""
        # Create timezone-aware datetimes
        start_datetime = timezone.make_aware(datetime.combine(start_dt, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_dt, datetime.max.time()))
        
        # Build the base query
        query = Sales.objects.filter(
            prodt='selling item',
            cd__year=year,
            cd__gte=start_datetime,
            cd__lte=end_datetime
        ).exclude(un__in=["მთავარი საწყობი 2", "სატესტო"]).exclude(tanxa=0)
        
        # Debug: Print what filters are being applied
        print(f"Year: {year}")
        print(f"Locations filter: {selected_locations}")
        print(f"Category filter: {selected_category}")
        print(f"Product filter: {selected_product}")
        print(f"Campaign filter: {selected_campaign}")
        
        # Apply filters one by one
        if selected_locations and len(selected_locations) > 0:
            print(f"Applying location filter: {selected_locations}")
            query = query.filter(un__in=selected_locations)
        
        if selected_category and selected_category != 'all':
            print(f"Applying category filter: {selected_category}")
            query = query.filter(prodg=selected_category)
        
        if selected_product and selected_product != 'all':
            print(f"Applying product filter: {selected_product}")
            query = query.filter(prod=selected_product)
        
        if selected_campaign and selected_campaign != 'all':
            print(f"Applying campaign filter: {selected_campaign}")
            query = query.filter(actions=selected_campaign)
        
        # Debug: Print query count
        print(f"Query count after filters: {query.count()}")
        
        # Create filtered subquery for cross-selling calculations with same filters
        filtered_tickets = Sales.objects.filter(
            prodt='selling item',
            cd__year=year,
            cd__gte=start_datetime,
            cd__lte=end_datetime
        ).exclude(un__in=["მთავარი საწყობი 2", "სატესტო"]).exclude(tanxa=0).exclude(prodg='POP')
        
        if selected_locations and len(selected_locations) > 0:
            filtered_tickets = filtered_tickets.filter(un__in=selected_locations)
        
        if selected_category and selected_category != 'all':
            filtered_tickets = filtered_tickets.filter(prodg=selected_category)
        
        if selected_product and selected_product != 'all':
            filtered_tickets = filtered_tickets.filter(prod=selected_product)
        
        if selected_campaign and selected_campaign != 'all':
            filtered_tickets = filtered_tickets.filter(actions=selected_campaign)
        
        # Get location aggregations
        location_data = query.values('un').annotate(
            total=Sum('tanxa'),
            tickets=Count('zedd', distinct=True),
            quantity=Count('idreal1'),
            three_plus=Count(
                'zedd',
                distinct=True,
                filter=Q(
                    zedd__in=filtered_tickets
                        .values('zedd')
                        .annotate(c=Count('idreal1'))
                        .filter(c__gte=3)
                        .values('zedd')
                )
            ),
            one_count=Count(
                'zedd',
                distinct=True,
                filter=Q(
                    zedd__in=filtered_tickets
                        .values('zedd')
                        .annotate(c=Count('idreal1'))
                        .filter(c=1)
                        .values('zedd')
                )
            )
        ).annotate(
            avg_basket=ExpressionWrapper(
                F('total') * 1.0 / F('tickets'),
                output_field=FloatField()
            ),
            three_plus_ratio=ExpressionWrapper(
                (F('three_plus') * 100.0) / F('tickets'),
                output_field=FloatField()
            ),
            one_ratio=ExpressionWrapper(
                (F('one_count') * 100.0) / F('tickets'),
                output_field=FloatField()
            )
        ).order_by('-total')
        
        return location_data
    
    # Get data for both years
    previous_start = start_date.replace(year=previous_year)
    previous_end = end_date.replace(year=previous_year)
    
    current_data = list(get_location_data(current_year, start_date, end_date))
    previous_data = list(get_location_data(previous_year, previous_start, previous_end))
    
    # Create Excel workbook
    wb = Workbook()
    
    # Define styles
    header_fill = PatternFill(start_color="667EEA", end_color="667EEA", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    total_fill = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")
    total_font = Font(bold=True, size=11)
    info_font = Font(bold=True, size=10)
    border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC')
    )
    
    def create_sheet(ws, data, year, sheet_name):
        """Create a formatted sheet with location data"""
        ws.title = sheet_name
        
        # Add header information
        ws['A1'] = 'Location Performance Report'
        ws['A1'].font = Font(bold=True, size=14)
        
        ws['A2'] = 'Year:'
        ws['B2'] = year
        ws['A2'].font = info_font
        
        ws['A3'] = 'Period:'
        if year == current_year:
            ws['B3'] = f'{start_date} to {end_date}'
        else:
            ws['B3'] = f'{previous_start} to {previous_end}'
        ws['A3'].font = info_font
        
        ws['A4'] = 'Category:'
        ws['B4'] = selected_category
        ws['A4'].font = info_font
        
        ws['A5'] = 'Product:'
        ws['B5'] = selected_product if selected_product != 'all' else 'All'
        ws['A5'].font = info_font
        
        ws['A6'] = 'Campaign:'
        ws['B6'] = selected_campaign if selected_campaign != 'all' else 'All'
        ws['A6'].font = info_font
        
        # Column headers (row 8)
        headers = [
            'Location', 'Total Amount', 'Tickets', 'Quantity', 
            'Avg Basket', '3+ Items', '1 Item', '3+ Ratio (%)', '1 Item Ratio (%)'
        ]
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=8, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border
        
        # Data rows
        row_num = 9
        total_revenue = 0
        total_tickets = 0
        total_quantity = 0
        total_3plus = 0
        total_1item = 0
        
        for row_data in data:
            ws.cell(row=row_num, column=1, value=row_data['un'])
            ws.cell(row=row_num, column=2, value=round(row_data['total'], 2) if row_data['total'] else 0)
            ws.cell(row=row_num, column=3, value=row_data['tickets'])
            ws.cell(row=row_num, column=4, value=row_data['quantity'])
            ws.cell(row=row_num, column=5, value=round(row_data['avg_basket'], 2) if row_data['avg_basket'] else 0)
            ws.cell(row=row_num, column=6, value=row_data['three_plus'])
            ws.cell(row=row_num, column=7, value=row_data['one_count'])
            ws.cell(row=row_num, column=8, value=round(row_data['three_plus_ratio'], 2) if row_data['three_plus_ratio'] else 0)
            ws.cell(row=row_num, column=9, value=round(row_data['one_ratio'], 2) if row_data['one_ratio'] else 0)
            
            # Apply borders
            for col in range(1, 10):
                ws.cell(row=row_num, column=col).border = border
            
            # Number formatting
            ws.cell(row=row_num, column=2).number_format = '#,##0.00'
            ws.cell(row=row_num, column=5).number_format = '#,##0.00'
            ws.cell(row=row_num, column=8).number_format = '0.00'
            ws.cell(row=row_num, column=9).number_format = '0.00'
            
            # Accumulate totals
            total_revenue += row_data['total'] or 0
            total_tickets += row_data['tickets'] or 0
            total_quantity += row_data['quantity'] or 0
            total_3plus += row_data['three_plus'] or 0
            total_1item += row_data['one_count'] or 0
            
            row_num += 1
        
        # Add totals row
        row_num += 1
        avg_basket_total = total_revenue / total_tickets if total_tickets > 0 else 0
        ratio_3plus = (total_3plus / total_tickets * 100) if total_tickets > 0 else 0
        ratio_1item = (total_1item / total_tickets * 100) if total_tickets > 0 else 0
        
        ws.cell(row=row_num, column=1, value='TOTAL')
        ws.cell(row=row_num, column=2, value=round(total_revenue, 2))
        ws.cell(row=row_num, column=3, value=total_tickets)
        ws.cell(row=row_num, column=4, value=total_quantity)
        ws.cell(row=row_num, column=5, value=round(avg_basket_total, 2))
        ws.cell(row=row_num, column=6, value=total_3plus)
        ws.cell(row=row_num, column=7, value=total_1item)
        ws.cell(row=row_num, column=8, value=round(ratio_3plus, 2))
        ws.cell(row=row_num, column=9, value=round(ratio_1item, 2))
        
        # Style totals row
        for col in range(1, 10):
            cell = ws.cell(row=row_num, column=col)
            cell.fill = total_fill
            cell.font = total_font
            cell.border = border
        
        ws.cell(row=row_num, column=2).number_format = '#,##0.00'
        ws.cell(row=row_num, column=5).number_format = '#,##0.00'
        ws.cell(row=row_num, column=8).number_format = '0.00'
        ws.cell(row=row_num, column=9).number_format = '0.00'
        
        # Adjust column widths
        ws.column_dimensions['A'].width = 25
        for col in range(2, 10):
            ws.column_dimensions[get_column_letter(col)].width = 15
    
    # Create sheets for current and previous year
    ws_current = wb.active
    create_sheet(ws_current, current_data, current_year, f'{current_year}')
    
    ws_previous = wb.create_sheet(title=f'{previous_year}')
    create_sheet(ws_previous, previous_data, previous_year, f'{previous_year}')
    
    # Create comparison sheet
    ws_comparison = wb.create_sheet(title='Comparison')
    ws_comparison['A1'] = f'{previous_year} vs {current_year} Comparison'
    ws_comparison['A1'].font = Font(bold=True, size=14)
    
    # Comparison headers
    comp_headers = [
        'Location', 
        f'{previous_year} Revenue', f'{current_year} Revenue', 'Revenue Change', 'Revenue Change %',
        f'{previous_year} Tickets', f'{current_year} Tickets', 'Tickets Change', 'Tickets Change %'
    ]
    
    for col, header in enumerate(comp_headers, 1):
        cell = ws_comparison.cell(row=3, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Create comparison data
    prev_dict = {row['un']: row for row in previous_data}
    curr_dict = {row['un']: row for row in current_data}
    all_locations = sorted(set(list(prev_dict.keys()) + list(curr_dict.keys())))
    
    row_num = 4
    for location in all_locations:
        prev = prev_dict.get(location, {})
        curr = curr_dict.get(location, {})
        
        prev_revenue = prev.get('total', 0) or 0
        curr_revenue = curr.get('total', 0) or 0
        revenue_change = curr_revenue - prev_revenue
        revenue_change_pct = ((revenue_change / prev_revenue) * 100) if prev_revenue > 0 else 0
        
        prev_tickets = prev.get('tickets', 0) or 0
        curr_tickets = curr.get('tickets', 0) or 0
        tickets_change = curr_tickets - prev_tickets
        tickets_change_pct = ((tickets_change / prev_tickets) * 100) if prev_tickets > 0 else 0
        
        ws_comparison.cell(row=row_num, column=1, value=location)
        ws_comparison.cell(row=row_num, column=2, value=round(prev_revenue, 2))
        ws_comparison.cell(row=row_num, column=3, value=round(curr_revenue, 2))
        ws_comparison.cell(row=row_num, column=4, value=round(revenue_change, 2))
        ws_comparison.cell(row=row_num, column=5, value=round(revenue_change_pct, 2))
        ws_comparison.cell(row=row_num, column=6, value=prev_tickets)
        ws_comparison.cell(row=row_num, column=7, value=curr_tickets)
        ws_comparison.cell(row=row_num, column=8, value=tickets_change)
        ws_comparison.cell(row=row_num, column=9, value=round(tickets_change_pct, 2))
        
        # Apply conditional formatting colors
        for col in [4, 5, 8, 9]:
            cell = ws_comparison.cell(row=row_num, column=col)
            value = cell.value
            if value > 0:
                cell.font = Font(color="10B981")
            elif value < 0:
                cell.font = Font(color="EF4444")
        
        # Apply borders
        for col in range(1, 10):
            ws_comparison.cell(row=row_num, column=col).border = border
        
        row_num += 1
    
    # Adjust comparison sheet column widths
    ws_comparison.column_dimensions['A'].width = 25
    for col in range(2, 10):
        ws_comparison.column_dimensions[get_column_letter(col)].width = 16
    
    # Create filename
    filename_parts = [f'location_report_{current_year}_vs_{previous_year}']
    if selected_locations:
        filename_parts.append(f'{len(selected_locations)}locations')
    if selected_category != 'all':
        filename_parts.append(selected_category.replace(' ', '_'))
    filename_parts.append(f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")}')
    
    filename = '_'.join(filename_parts) + '.xlsx'
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response

@login_required
def query(request):
    try:
        user_profile = request.user.profile
    except:
        return HttpResponseForbidden("Access denied. Contact administrator.")
    
    # ADMIN ONLY for query interface
    if not user_profile.is_admin:
        return HttpResponseForbidden("Only administrators can access the SQL query interface.")
    
    results = None
    columns = None
    query_text = ""
    error_message = None
    
    # Handle Excel export
    if request.method == 'POST' and 'export_excel' in request.POST:
        query_text = request.POST.get('sql_query', '').strip()
        
        if query_text:
            # Basic SQL injection prevention - allow SELECT and WITH (CTE) statements
            query_upper = query_text.upper().strip()
            if not (query_upper.startswith('SELECT') or query_upper.startswith('WITH')):
                error_message = "Only SELECT queries (including CTEs with WITH) are allowed for security reasons."
            # Check for dangerous keywords
            elif any(keyword in query_upper for keyword in ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE']):
                error_message = "Detected prohibited SQL keywords. Only SELECT queries are allowed."
            else:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(query_text)
                        results = cursor.fetchall()
                        columns = [col[0] for col in cursor.description]
                    
                    # Create Excel file
                    return export_to_excel(results, columns)
                    
                except Exception as e:
                    error_message = f"Query Error: {str(e)}"
    
    # Handle regular query execution
    elif request.method == 'POST':
        query_text = request.POST.get('sql_query', '').strip()
        
        if query_text:
            # Security validation
            query_upper = query_text.upper().strip()
            if not (query_upper.startswith('SELECT') or query_upper.startswith('WITH')):
                error_message = "Only SELECT queries (including CTEs with WITH) are allowed for security reasons."
            elif any(keyword in query_upper for keyword in ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE']):
                error_message = "Detected prohibited SQL keywords. Only SELECT queries are allowed."
            else:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(query_text)
                        results = cursor.fetchall()
                        columns = [col[0] for col in cursor.description]
                    
                    if not results:
                        messages.info(request, "Query executed successfully but returned no results.")
                    else:
                        messages.success(request, f"Query executed successfully! {len(results)} rows returned.")
                        
                except Exception as e:
                    error_message = f"Query Error: {str(e)}"
    
    context = {
        'results': results,
        'columns': columns,
        'query_text': query_text,
        'error_message': error_message,
        'user_profile': user_profile,
        'is_admin': user_profile.is_admin,
    }
    
    return render(request, 'query.html', context)

def export_to_excel(results, columns):
    """Export query results to Excel with formatting"""
    
    # Create workbook and worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Query Results"
    
    # Define styles
    header_font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    
    cell_alignment = Alignment(horizontal='left', vertical='center')
    border = Border(
        left=Side(style='thin', color='D0D0D0'),
        right=Side(style='thin', color='D0D0D0'),
        top=Side(style='thin', color='D0D0D0'),
        bottom=Side(style='thin', color='D0D0D0')
    )
    
    # Write headers
    for col_num, column_name in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_num, value=column_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    # Write data
    for row_num, row_data in enumerate(results, 2):
        for col_num, cell_value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=cell_value)
            cell.alignment = cell_alignment
            cell.border = border
            
            # Alternate row colors for better readability
            if row_num % 2 == 0:
                cell.fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
    
    # Auto-adjust column widths
    for col_num in range(1, len(columns) + 1):
        column_letter = get_column_letter(col_num)
        
        # Calculate max length in column
        max_length = len(str(columns[col_num - 1]))
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=col_num, max_col=col_num):
            for cell in row:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
        
        # Set column width (with some padding)
        adjusted_width = min(max_length + 2, 50)  # Max width of 50
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Freeze the header row
    ws.freeze_panes = 'A2'
    
    # Create HTTP response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=query_results.xlsx'
    
    # Save workbook to response
    wb.save(response)
    
    return response

@login_required
def employee_analytics(request):
    try:
        user_profile = request.user.profile
    except:
        return HttpResponseForbidden("Access denied. Contact administrator.")
    
    # Get allowed locations for this user
    allowed_locations = user_profile.get_allowed_locations()
    
    # Get current year and determine comparison
    comparison_mode = request.GET.get('comparison', '2025-2024')
    if comparison_mode == '2026-2025':
        current_year = 2026
        previous_year = 2025
    elif comparison_mode == '2026-2024':
        current_year = 2026
        previous_year = 2024
    else:
        current_year = 2025
        previous_year = 2024
    
    # Get filter parameters
    start_date_str = request.GET.get('start_date', f'{current_year}-01-01')
    end_date_str = request.GET.get('end_date', f'{current_year}-12-31')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except:
        start_date = date(current_year, 1, 1)
    
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except:
        end_date = date(current_year, 12, 31)
    
    # Handle multiple location selections with SECURITY CHECK
    selected_locations = request.GET.getlist('un_filter')
    
    if not user_profile.is_admin:
        if not selected_locations or 'all' in selected_locations:
            selected_locations = allowed_locations
        else:
            unauthorized = set(selected_locations) - set(allowed_locations)
            if unauthorized:
                messages.warning(request, f"Access denied to: {', '.join(unauthorized)}")
                selected_locations = [loc for loc in selected_locations if loc in allowed_locations]
            
            if not selected_locations:
                selected_locations = allowed_locations
    
    if not selected_locations and not user_profile.is_admin:
        return HttpResponseForbidden("You don't have access to any locations.")
    
    # Set selected_un for display
    if user_profile.is_admin and (not selected_locations or 'all' in request.GET.getlist('un_filter')):
        selected_un = 'all'
        selected_locations = []
    else:
        selected_un = selected_locations[0] if len(selected_locations) == 1 else 'multiple'
    
    selected_category = request.GET.get('category', 'all')
    selected_employee = request.GET.get('employee_filter', 'all')
    
    # Adjust dates to match current_year
    start_date = start_date.replace(year=current_year)
    end_date = end_date.replace(year=current_year)
    
    # Define previous year dates
    previous_start = start_date.replace(year=previous_year)
    previous_end = end_date.replace(year=previous_year)
    
    # Create timezone-aware datetimes
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    previous_start_datetime = timezone.make_aware(datetime.combine(previous_start, datetime.min.time()))
    previous_end_datetime = timezone.make_aware(datetime.combine(previous_end, datetime.max.time()))
    
    date_filter_current = {
        'cd__year': current_year,
        'cd__gte': start_datetime,
        'cd__lte': end_datetime
    }
    
    date_filter_previous = {
        'cd__year': previous_year,
        'cd__gte': previous_start_datetime,
        'cd__lte': previous_end_datetime
    }
    
    def apply_filters(q):
        """Helper function to apply filters"""
        if selected_locations:
            q = q.filter(un__in=selected_locations)
        if selected_category != 'all':
            q = q.filter(prodg=selected_category)
        if selected_employee != 'all':
            q = q.filter(tanam=selected_employee)
        return q
    
    def get_cross_selling_metrics(employee_name, date_filter):
        """
        OPTIMIZED: Single query to get all cross-selling metrics at once
        Returns dict with comprehensive cross-selling analytics
        """
        tickets_query = (Sales.objects
            .filter(**date_filter, tanam=employee_name, prodt='selling item')
            .exclude(tanxa=0)
            .exclude(prodg='POP'))
        
        if selected_locations:
            tickets_query = tickets_query.filter(un__in=selected_locations)
        if selected_category != 'all':
            tickets_query = tickets_query.filter(prodg=selected_category)
        
        # Single aggregation to get all ticket-level data
        ticket_items = list(tickets_query.values('zedd').annotate(
            item_count=Count('zedd')
        ))
        
        total_tickets = len(ticket_items)
        if total_tickets == 0:
            return {
                'cross_sell_pct': 0,
                'one_item_pct': 0,
                'two_item_pct': 0,
                'three_plus_pct': 0,
                'avg_items_per_ticket': 0,
                'cross_sell_tickets': 0,
                'one_item_tickets': 0,
                'two_item_tickets': 0,
                'three_plus_tickets': 0
            }
        
        # Calculate distributions
        one_item = sum(1 for t in ticket_items if t['item_count'] == 1)
        two_item = sum(1 for t in ticket_items if t['item_count'] == 2)
        three_plus = sum(1 for t in ticket_items if t['item_count'] >= 3)
        total_items = sum(t['item_count'] for t in ticket_items)
        
        return {
            'cross_sell_pct': (three_plus / total_tickets) * 100,
            'one_item_pct': (one_item / total_tickets) * 100,
            'two_item_pct': (two_item / total_tickets) * 100,
            'three_plus_pct': (three_plus / total_tickets) * 100,
            'avg_items_per_ticket': total_items / total_tickets,
            'cross_sell_tickets': three_plus,
            'one_item_tickets': one_item,
            'two_item_tickets': two_item,
            'three_plus_tickets': three_plus
        }
    
    def get_employee_performance(is_current=True):
        """
        OPTIMIZED: Get employee performance metrics with minimal queries
        """
        if is_current:
            q = Sales.objects.filter(**date_filter_current)
        else:
            q = Sales.objects.filter(**date_filter_previous)
        
        q = apply_filters(q)
        
        # Single optimized query with all aggregations
        employee_data = q.values('tanam', 'un').annotate(
            total_revenue=Sum('tanxa'),
            total_revenue_for_skincare=Sum('tanxa', filter=Q(~Q(prodg__in=['POP']))),
            total_tickets=Count('zedd', distinct=True),
            total_items=Count('zedd', filter=Q(~Q(idprod__in=['M9157', 'M9121', 'M9850']))),
            skincare_turnover=Sum('tanxa', filter=Q(prodg__in=['SKIN CARE'])),
            discount_given=Sum('discount_price'),
            std_price_total=Sum('std_price')
        ).order_by('-total_revenue')
        
        results = []
        for emp in employee_data:
            total_rev_skincare = emp.get('total_revenue_for_skincare') or 0
            skincare_turnover = emp.get('skincare_turnover') or 0
            skincare_percentage = (
                float(skincare_turnover) / float(total_rev_skincare)
                if total_rev_skincare > 0
                else 0
            )   
            avg_basket = float(emp['total_revenue'] or 0) / emp['total_tickets'] if emp['total_tickets'] > 0 else 0
            items_per_ticket = emp['total_items'] / emp['total_tickets'] if emp['total_tickets'] > 0 else 0
            discount_rate = (1 - (emp['discount_given'] / emp['std_price_total'])) * 100 if emp['std_price_total'] and emp['std_price_total'] > 0 else 0
            
            # Get cross-selling metrics only for current period
            if is_current:
                cross_metrics = get_cross_selling_metrics(emp['tanam'], date_filter_current)
            else:
                cross_metrics = {
                    'cross_sell_pct': 0,
                    'one_item_pct': 0,
                    'two_item_pct': 0,
                    'three_plus_pct': 0,
                    'avg_items_per_ticket': 0,
                    'cross_sell_tickets': 0,
                    'one_item_tickets': 0,
                    'two_item_tickets': 0,
                    'three_plus_tickets': 0
                }
            
            results.append({
                'name': emp['tanam'] or 'Unknown',
                'location': emp['un'] or 'Unknown',
                'revenue': float(emp['total_revenue'] or 0),
                'skincare_percentage': skincare_percentage * 100,
                'tickets': emp['total_tickets'],
                'items': emp['total_items'],
                'avg_basket': avg_basket,
                'items_per_ticket': items_per_ticket,
                'discount_rate': discount_rate,
                **cross_metrics  # Unpack all cross-selling metrics
            })
        
        return results
    
    def get_category_top_performers(category, is_current=True):
        """Get top 10 performers for a specific category"""
        if is_current:
            q = Sales.objects.filter(**date_filter_current, prodg=category)
        else:
            q = Sales.objects.filter(**date_filter_previous, prodg=category)
        
        # Apply location filter only
        if selected_locations:
            q = q.filter(un__in=selected_locations)
        
        employee_data = q.values('tanam').annotate(
            total_revenue=Sum('tanxa'),
            total_tickets=Count('zedd', distinct=True),
            total_items=Count('zedd')
        ).order_by('-total_revenue')[:10]
        
        results = []
        for emp in employee_data:
            # Get cross-selling metrics for category leaders
            cross_metrics = get_cross_selling_metrics(emp['tanam'], 
                {'cd__year': current_year if is_current else previous_year,
                 'cd__gte': start_datetime if is_current else previous_start_datetime,
                 'cd__lte': end_datetime if is_current else previous_end_datetime,
                 'prodg': category})
            
            results.append({
                'name': emp['tanam'] or 'Unknown',
                'revenue': float(emp['total_revenue'] or 0),
                'tickets': emp['total_tickets'],
                'items': emp['total_items'],
                'cross_sell_pct': cross_metrics['cross_sell_pct']
            })
        
        return results
    
    # Get overall employee performance
    employees_current = get_employee_performance(is_current=True)
    employees_previous = get_employee_performance(is_current=False)
    
    # Create comparison dictionary
    employees_previous_dict = {emp['name']: emp for emp in employees_previous}
    
    # Add YoY comparison
    for emp in employees_current:
        prev_data = employees_previous_dict.get(emp['name'], {})
        emp['revenue_previous'] = prev_data.get('revenue', 0)
        emp['tickets_previous'] = prev_data.get('tickets', 0)
        emp['revenue_change'] = ((emp['revenue'] - emp['revenue_previous']) / emp['revenue_previous'] * 100) if emp['revenue_previous'] > 0 else 0
        emp['tickets_change'] = ((emp['tickets'] - emp['tickets_previous']) / emp['tickets_previous'] * 100) if emp['tickets_previous'] > 0 else 0
    
    # Get top categories
    top_categories_query = Sales.objects.filter(**date_filter_current)
    if selected_locations:
        top_categories_query = top_categories_query.filter(un__in=selected_locations)
    
    top_categories = list(top_categories_query.values('prodg').annotate(
        total=Sum('tanxa')
    ).order_by('-total')[:10].values_list('prodg', flat=True))
    
    # Get top performers by category
    category_leaders = []
    for category in top_categories:
        category_leaders.append({
            'category': category,
            'performers_current': get_category_top_performers(category, is_current=True),
            'performers_previous': get_category_top_performers(category, is_current=False)
        })
    
    # Get all unique values for filters - OPTIMIZED with distinct()
    if user_profile.is_admin:
        all_locations = list(Sales.objects.filter(cd__year=current_year).values_list('un', flat=True).distinct().order_by('un'))
    else:
        all_locations = allowed_locations
        
    all_categories = list(Sales.objects.filter(cd__year=current_year).values_list('prodg', flat=True).distinct().order_by('prodg'))
    all_employees = list(Sales.objects.filter(cd__year=current_year).values_list('tanam', flat=True).distinct().order_by('tanam'))
    
    date_range_text = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}, {current_year}"

    context = {
        'comparison_mode': comparison_mode,
        'current_year': current_year,
        'previous_year': previous_year,
        'date_range_text': date_range_text,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        
        'employees_current': employees_current,
        'category_leaders': category_leaders,
        'top_categories': top_categories,
        
        'all_locations': all_locations,
        'all_categories': all_categories,
        'all_employees': all_employees,
        'selected_un': selected_un,
        'selected_locations': selected_locations,
        'selected_category': selected_category,
        'selected_employee': selected_employee,

        'user_profile': user_profile,
        'is_admin': user_profile.is_admin,
        'user_locations_count': len(allowed_locations) if not user_profile.is_admin else 0,
    }
    
    return render(request, 'employee_analytics.html', context)

@login_required
def insights(request):
    """
    Generate AI-powered insights by comparing current selection with up to 2 previous years
    """
    
    # Get filter parameters - same as dashboard
    try:
        user_profile = request.user.profile
    except:
        return HttpResponseForbidden("Access denied. Contact administrator.")
    
    # Get allowed locations for this user
    allowed_locations = user_profile.get_allowed_locations()
    
    # Get filter parameters - same as dashboard
    comparison_mode = request.GET.get('comparison', '2025-2024')
    if comparison_mode == '2026-2025':
        current_year = 2026
        previous_year = 2025
        two_years_ago = 2024
    elif comparison_mode == '2026-2024':
        current_year = 2026
        previous_year = 2024
        two_years_ago = None  # Not enough data
    else:
        current_year = 2025
        previous_year = 2024
        two_years_ago = 2023

    # Get date range
    start_date_str = request.GET.get('start_date', f'{current_year}-01-01')
    end_date_str = request.GET.get('end_date', f'{current_year}-12-31')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except:
        start_date = date(current_year, 1, 1)
    
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except:
        end_date = date(current_year, 12, 31)
    
    # Handle location filtering with SECURITY CHECK
    selected_locations = request.GET.getlist('un_filter')
    
    if not user_profile.is_admin:
        if not selected_locations or 'all' in selected_locations:
            selected_locations = allowed_locations
        else:
            unauthorized = set(selected_locations) - set(allowed_locations)
            if unauthorized:
                messages.warning(request, f"Access denied to: {', '.join(unauthorized)}")
                selected_locations = [loc for loc in selected_locations if loc in allowed_locations]
            
            if not selected_locations:
                selected_locations = allowed_locations
    
    if not selected_locations and not user_profile.is_admin:
        return HttpResponseForbidden("You don't have access to any locations.")
    
    # If admin selected 'all', reset to empty list
    if user_profile.is_admin and (not selected_locations or 'all' in request.GET.getlist('un_filter')):
        selected_locations = []
    
    selected_category = request.GET.get('category', 'all')
    selected_product = request.GET.get('prod_filter', 'all')
    selected_campaign = request.GET.get('campaign_filter', 'all')
    
    # Adjust dates to current year
    start_date = start_date.replace(year=current_year)
    end_date = end_date.replace(year=current_year)
    
    # Create timezone-aware datetimes
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    
    def apply_filters(queryset):
        """Apply consistent filters across all queries"""
        if selected_locations:
            queryset = queryset.filter(un__in=selected_locations)
        if selected_category != 'all':
            queryset = queryset.filter(prodg=selected_category)
        if selected_product != 'all':
            queryset = queryset.filter(prod=selected_product)
        if selected_campaign != 'all':
            queryset = queryset.filter(actions=selected_campaign)
        return queryset.exclude(un__in=["მთავარი საწყობი 2", "სატესტო"])
    
    def get_year_stats(year):
        """Get comprehensive stats for a given year"""
        year_start = start_date.replace(year=year)
        year_end = end_date.replace(year=year)
        year_start_dt = timezone.make_aware(datetime.combine(year_start, datetime.min.time()))
        year_end_dt = timezone.make_aware(datetime.combine(year_end, datetime.max.time()))
        
        q = Sales.objects.filter(
            cd__year=year,
            cd__gte=year_start_dt,
            cd__lte=year_end_dt
        )
        q = apply_filters(q)
        
        # Basic stats
        basic_stats = q.aggregate(
            total_revenue=Sum('tanxa'),
            total_tickets=Count('zedd', distinct=True),
            total_items=Count('zedd'),
            discount_total=Sum('discount_price'),
            std_price_total=Sum('std_price')
        )
        
        # Calculate derived metrics
        total_tickets = basic_stats['total_tickets'] or 0
        total_revenue = float(basic_stats['total_revenue'] or 0)
        total_items = basic_stats['total_items'] or 0
        
        avg_basket = total_revenue / total_tickets if total_tickets > 0 else 0
        items_per_ticket = total_items / total_tickets if total_tickets > 0 else 0
        discount_share = (1 - (basic_stats['discount_total'] / basic_stats['std_price_total'])) * 100 if basic_stats['std_price_total'] and basic_stats['std_price_total'] > 0 else 0
        
        # Cross-selling stats
        ticket_items = q.filter(prodt='selling item').exclude(tanxa=0).exclude(prodg='POP').values('zedd').annotate(
            item_count=Count('idreal1')
        )
        
        total_analyzed_tickets = ticket_items.count()
        cross_sell_tickets = sum(1 for t in ticket_items if t['item_count'] >= 3)
        single_item_tickets = sum(1 for t in ticket_items if t['item_count'] == 1)
        
        cross_sell_rate = (cross_sell_tickets / total_analyzed_tickets * 100) if total_analyzed_tickets > 0 else 0
        single_item_rate = (single_item_tickets / total_analyzed_tickets * 100) if total_analyzed_tickets > 0 else 0
        
        # Category performance
        category_data = q.values('prodg').annotate(
            revenue=Sum('tanxa')
        ).order_by('-revenue')[:5]
        
        # Top products
        product_data = q.values('prod').annotate(
            revenue=Sum('tanxa'),
            quantity=Count('idreal1')
        ).order_by('-revenue')[:5]
        
        # Location performance
        location_data = q.values('un').annotate(
            revenue=Sum('tanxa'),
            tickets=Count('zedd', distinct=True)
        ).order_by('-revenue')[:5]
        
        return {
            'year': year,
            'total_revenue': total_revenue,
            'total_tickets': total_tickets,
            'total_items': total_items,
            'avg_basket': avg_basket,
            'items_per_ticket': items_per_ticket,
            'discount_share': discount_share,
            'cross_sell_rate': cross_sell_rate,
            'single_item_rate': single_item_rate,
            'top_categories': list(category_data),
            'top_products': list(product_data),
            'top_locations': list(location_data)
        }
    
    # Get stats for all available years
    stats_current = get_year_stats(current_year)
    stats_previous = get_year_stats(previous_year)
    stats_two_years = get_year_stats(two_years_ago) if two_years_ago else None
    
    # Helper functions
    def calc_change(current, previous):
        if previous and previous > 0:
            return ((current - previous) / previous) * 100
        return 0
    
    def format_currency(value):
        if value >= 1000000:
            return f"${value/1000000:.1f}M"
        elif value >= 1000:
            return f"${value/1000:.1f}K"
        return f"${value:.2f}"
    
    def format_number(value):
        if value >= 1000000:
            return f"{value/1000000:.1f}M"
        elif value >= 1000:
            return f"{value/1000:.1f}K"
        return f"{int(value)}"
    
    def get_trend_class(change_pct):
        if change_pct > 0:
            return 'positive'
        elif change_pct < 0:
            return 'negative'
        return 'neutral'
    
    def get_trend_icon(change_pct):
        if change_pct > 0:
            return 'up'
        elif change_pct < 0:
            return 'down'
        return 'right'
    
    # Generate insights
    insights_list = []
    recommendations = []
    
    # Calculate changes
    revenue_change = calc_change(stats_current['total_revenue'], stats_previous['total_revenue'])
    tickets_change = calc_change(stats_current['total_tickets'], stats_previous['total_tickets'])
    basket_change = calc_change(stats_current['avg_basket'], stats_previous['avg_basket'])
    cross_sell_change = calc_change(stats_current['cross_sell_rate'], stats_previous['cross_sell_rate'])
    single_item_change = calc_change(stats_current['single_item_rate'], stats_previous['single_item_rate'])
    
    # INSIGHT 1: Overall Revenue Performance
    if abs(revenue_change) > 1:  # Only show if meaningful change
        revenue_insight = {
            'category': 'Revenue Analysis',
            'title': f"Revenue {'Growth' if revenue_change > 0 else 'Decline'} of {abs(revenue_change):.1f}%",
            'icon': 'fa-chart-line',
            'icon_class': 'icon-positive' if revenue_change > 0 else 'icon-negative',
            'description': '',
            'metrics': [
                {
                    'label': f'{current_year} Revenue',
                    'value': format_currency(stats_current['total_revenue']),
                    'change': f"{revenue_change:+.1f}%",
                    'change_class': get_trend_class(revenue_change),
                    'change_icon': get_trend_icon(revenue_change)
                },
                {
                    'label': f'{previous_year} Revenue',
                    'value': format_currency(stats_previous['total_revenue']),
                    'change': None
                }
            ],
            'year_comparison': None
        }
        
        # Generate description based on revenue components
        if revenue_change > 0:
            if tickets_change > basket_change:
                revenue_insight['description'] = f"<p>Your revenue increased by <span class='highlight-positive'>{revenue_change:.1f}%</span> compared to {previous_year}, primarily driven by a <strong>{tickets_change:.1f}% increase in transaction volume</strong>. This indicates strong customer acquisition or increased purchase frequency.</p>"
            else:
                revenue_insight['description'] = f"<p>Your revenue grew by <span class='highlight-positive'>{revenue_change:.1f}%</span> year-over-year, with the average basket size increasing by <strong>{basket_change:.1f}%</strong>. Customers are spending more per transaction, suggesting effective upselling or premium product adoption.</p>"
        else:
            revenue_insight['description'] = f"<p>Revenue declined by <span class='highlight-negative'>{abs(revenue_change):.1f}%</span> compared to {previous_year}. "
            if tickets_change < 0 and basket_change < 0:
                revenue_insight['description'] += f"Both transaction volume (down {abs(tickets_change):.1f}%) and average basket size (down {abs(basket_change):.1f}%) decreased, indicating challenges in both customer retention and purchase value.</p>"
            elif tickets_change < 0:
                revenue_insight['description'] += f"This is primarily due to a <strong>{abs(tickets_change):.1f}% decrease in transaction volume</strong>, despite average basket size remaining stable.</p>"
            else:
                revenue_insight['description'] += f"While transaction volume increased by {tickets_change:.1f}%, the average basket size decreased by {abs(basket_change):.1f}%, suggesting customers are purchasing less per visit.</p>"
        
        insights_list.append(revenue_insight)
        
        # Add recommendations based on revenue performance
        if revenue_change < 0:
            if tickets_change < -5:
                recommendations.append("Focus on customer retention and acquisition strategies to reverse the declining transaction volume. Consider loyalty programs or targeted marketing campaigns.")
            if basket_change < -5:
                recommendations.append("Implement bundle offers or cross-selling strategies to increase average basket size and maximize value per customer visit.")
    
    # INSIGHT 2: Cross-Selling Performance
    if stats_current['cross_sell_rate'] > 0:
        cross_sell_insight = {
            'category': 'Customer Behavior',
            'title': f"Cross-Selling Rate: {stats_current['cross_sell_rate']:.1f}%",
            'icon': 'fa-layer-group',
            'icon_class': 'icon-positive' if cross_sell_change > 0 else 'icon-warning',
            'description': '',
            'metrics': [
                {
                    'label': 'Cross-Sell Rate',
                    'value': f"{stats_current['cross_sell_rate']:.1f}%",
                    'change': f"{cross_sell_change:+.1f}%" if cross_sell_change != 0 else "No change",
                    'change_class': get_trend_class(cross_sell_change),
                    'change_icon': get_trend_icon(cross_sell_change)
                },
                {
                    'label': 'Single Item Rate',
                    'value': f"{stats_current['single_item_rate']:.1f}%",
                    'change': f"{single_item_change:+.1f}%" if single_item_change != 0 else "No change",
                    'change_class': 'negative' if single_item_change > 0 else 'positive',
                    'change_icon': get_trend_icon(single_item_change)
                }
            ],
            'year_comparison': None
        }
        
        if cross_sell_change > 5:
            cross_sell_insight['description'] = f"<p><strong>Excellent progress!</strong> Your cross-selling rate improved by <span class='highlight-positive'>{cross_sell_change:.1f}%</span>, with <strong>{stats_current['cross_sell_rate']:.1f}% of transactions</strong> containing 3+ items. This indicates effective merchandising and sales techniques.</p>"
            recommendations.append(f"Continue strengthening cross-selling initiatives. Consider training staff on successful bundling techniques and optimizing product placement.")
        elif cross_sell_change < -5:
            cross_sell_insight['description'] = f"<p>Cross-selling performance declined by <span class='highlight-negative'>{abs(cross_sell_change):.1f}%</span>. Only <strong>{stats_current['cross_sell_rate']:.1f}% of customers</strong> are purchasing 3+ items per transaction, down from {stats_previous['cross_sell_rate']:.1f}% last year.</p>"
            recommendations.append("Develop strategic product bundles and train staff on cross-selling techniques. Consider implementing 'frequently bought together' displays.")
        else:
            cross_sell_insight['description'] = f"<p>Your cross-selling rate is stable at <strong>{stats_current['cross_sell_rate']:.1f}%</strong>, with {format_number(stats_current['total_tickets'] * stats_current['cross_sell_rate'] / 100)} multi-item transactions. There's opportunity to further improve customer basket composition.</p>"
            
            if stats_current['single_item_rate'] > 30:
                cross_sell_insight['description'] += f"<p>However, <span class='highlight-warning'>{stats_current['single_item_rate']:.1f}% of transactions</span> are single-item purchases, representing a significant opportunity for improvement.</p>"
                recommendations.append(f"With {stats_current['single_item_rate']:.1f}% single-item purchases, focus on bundling strategies and point-of-sale suggestions to increase items per basket.")
        
        insights_list.append(cross_sell_insight)
    
    # INSIGHT 3: Basket Size Trends
    if abs(basket_change) > 3:
        basket_insight = {
            'category': 'Transaction Value',
            'title': f"Average Basket {'Increased' if basket_change > 0 else 'Decreased'} to ${stats_current['avg_basket']:.2f}",
            'icon': 'fa-shopping-basket',
            'icon_class': 'icon-positive' if basket_change > 0 else 'icon-negative',
            'description': '',
            'metrics': [
                {
                    'label': f'{current_year} Avg Basket',
                    'value': f"${stats_current['avg_basket']:.2f}",
                    'change': f"{basket_change:+.1f}%",
                    'change_class': get_trend_class(basket_change),
                    'change_icon': get_trend_icon(basket_change)
                },
                {
                    'label': 'Items per Ticket',
                    'value': f"{stats_current['items_per_ticket']:.1f}",
                    'change': None
                }
            ],
            'year_comparison': None
        }
        
        items_change = calc_change(stats_current['items_per_ticket'], stats_previous['items_per_ticket'])
        
        if basket_change > 0:
            if items_change > basket_change:
                basket_insight['description'] = f"<p>The average basket value increased by <span class='highlight-positive'>{basket_change:.1f}%</span> to <strong>${stats_current['avg_basket']:.2f}</strong>, primarily driven by customers purchasing more items per transaction (up {items_change:.1f}%).</p>"
            else:
                basket_insight['description'] = f"<p>Average basket size grew by <span class='highlight-positive'>{basket_change:.1f}%</span> to <strong>${stats_current['avg_basket']:.2f}</strong>, indicating customers are trading up to higher-value products or responding well to premium offerings.</p>"
                recommendations.append("Capitalize on the premium trend by highlighting high-margin products and creating exclusive bundles.")
        else:
            basket_insight['description'] = f"<p>The average basket decreased by <span class='highlight-negative'>{abs(basket_change):.1f}%</span> to <strong>${stats_current['avg_basket']:.2f}</strong>. "
            if items_change < 0:
                basket_insight['description'] += "Customers are purchasing fewer items per visit, suggesting potential issues with product availability, pricing, or shopping experience.</p>"
                recommendations.append("Investigate causes of smaller baskets - consider customer feedback surveys and analyze product availability during peak periods.")
            else:
                basket_insight['description'] += "While customers are buying similar quantities, they're choosing lower-priced options, possibly due to economic factors or competitive pricing pressure.</p>"
        
        insights_list.append(basket_insight)
    
    # INSIGHT 4: Category Performance (if available)
    if stats_current['top_categories']:
        top_cat = stats_current['top_categories'][0]
        top_cat_revenue = float(top_cat['revenue'] or 0)
        top_cat_share = (top_cat_revenue / stats_current['total_revenue'] * 100) if stats_current['total_revenue'] > 0 else 0
        
        # Find previous year data for same category
        prev_cat_data = next((c for c in stats_previous['top_categories'] if c['prodg'] == top_cat['prodg']), None)
        
        if prev_cat_data:
            prev_cat_revenue = float(prev_cat_data['revenue'] or 0)
            cat_change = calc_change(top_cat_revenue, prev_cat_revenue)
            
            category_insight = {
                'category': 'Category Performance',
                'title': f"{top_cat['prodg']} Leads with {top_cat_share:.1f}% Share",
                'icon': 'fa-tags',
                'icon_class': 'icon-positive' if cat_change > 0 else 'icon-warning',
                'description': f"<p><strong>{top_cat['prodg']}</strong> is your top-performing category, generating <span class='highlight'>{format_currency(top_cat_revenue)}</span> ({top_cat_share:.1f}% of total revenue). ",
                'metrics': [
                    {
                        'label': 'Category Revenue',
                        'value': format_currency(top_cat_revenue),
                        'change': f"{cat_change:+.1f}%",
                        'change_class': get_trend_class(cat_change),
                        'change_icon': get_trend_icon(cat_change)
                    },
                    {
                        'label': 'Revenue Share',
                        'value': f"{top_cat_share:.1f}%",
                        'change': None
                    }
                ],
                'year_comparison': None
            }
            
            if cat_change > 10:
                category_insight['description'] += f"This category grew by <span class='highlight-positive'>{cat_change:.1f}%</span> year-over-year, significantly outpacing overall business growth.</p>"
                recommendations.append(f"Invest in expanding the {top_cat['prodg']} category - increase inventory depth, add complementary products, and feature prominently in marketing.")
            elif cat_change < -10:
                category_insight['description'] += f"However, this category declined by <span class='highlight-negative'>{abs(cat_change):.1f}%</span> compared to last year, which is concerning given its importance to your business.</p>"
                recommendations.append(f"Investigate the decline in {top_cat['prodg']} - analyze pricing, competition, and product freshness. Consider category refresh or promotional support.")
            else:
                category_insight['description'] += f"Performance changed by {cat_change:+.1f}% versus last year.</p>"
            
            insights_list.append(category_insight)
    
    # INSIGHT 5: Location Performance (if filtered or if there's variance)
    if stats_current['top_locations'] and len(stats_current['top_locations']) > 1:
        top_loc = stats_current['top_locations'][0]
        bottom_loc = stats_current['top_locations'][-1]
        
        top_loc_revenue = float(top_loc['revenue'] or 0)
        bottom_loc_revenue = float(bottom_loc['revenue'] or 0)
        
        if top_loc_revenue > 0 and bottom_loc_revenue > 0:
            variance_ratio = top_loc_revenue / bottom_loc_revenue
            
            if variance_ratio > 2:  # Significant variance
                location_insight = {
                    'category': 'Location Analysis',
                    'title': 'Significant Performance Variance Across Locations',
                    'icon': 'fa-map-marker-alt',
                    'icon_class': 'icon-warning',
                    'description': f"<p>There's significant performance variance across locations. <strong>{top_loc['un']}</strong> generates {format_currency(top_loc_revenue)}, while <strong>{bottom_loc['un']}</strong> generates {format_currency(bottom_loc_revenue)} - a {variance_ratio:.1f}x difference.</p>",
                    'metrics': [
                        {
                            'label': 'Top Location',
                            'value': format_currency(top_loc_revenue),
                            'change': None
                        },
                        {
                            'label': 'Performance Spread',
                            'value': f"{variance_ratio:.1f}x",
                            'change': None
                        }
                    ],
                    'year_comparison': None
                }
                
                recommendations.append(f"Analyze best practices from {top_loc['un']} and apply learnings to underperforming locations. Consider staffing, inventory, and local marketing differences.")
                insights_list.append(location_insight)
    
    # INSIGHT 6: Multi-year trend (if we have 3 years of data)
    if stats_two_years:
        revenue_3yr_growth = calc_change(stats_current['total_revenue'], stats_two_years['total_revenue'])
        cagr = (((stats_current['total_revenue'] / stats_two_years['total_revenue']) ** (1/2)) - 1) * 100 if stats_two_years['total_revenue'] > 0 else 0
        
        if abs(revenue_3yr_growth) > 10:
            trend_insight = {
                'category': 'Long-term Trends',
                'title': f"{current_year - two_years_ago}-Year Performance Trajectory",
                'icon': 'fa-chart-area',
                'icon_class': 'icon-positive' if revenue_3yr_growth > 0 else 'icon-negative',
                'description': f"<p>Over the past {current_year - two_years_ago} years, revenue {'grew' if revenue_3yr_growth > 0 else 'declined'} by <span class='{'highlight-positive' if revenue_3yr_growth > 0 else 'highlight-negative'}'>{abs(revenue_3yr_growth):.1f}%</span> (CAGR: {cagr:+.1f}%). ",
                'metrics': [],
                'year_comparison': [
                    {
                        'year': str(current_year),
                        'stats': [
                            {'label': 'Revenue', 'value': format_currency(stats_current['total_revenue'])},
                            {'label': 'Tickets', 'value': format_number(stats_current['total_tickets'])},
                            {'label': 'Avg Basket', 'value': f"${stats_current['avg_basket']:.2f}"}
                        ]
                    },
                    {
                        'year': str(previous_year),
                        'stats': [
                            {'label': 'Revenue', 'value': format_currency(stats_previous['total_revenue'])},
                            {'label': 'Tickets', 'value': format_number(stats_previous['total_tickets'])},
                            {'label': 'Avg Basket', 'value': f"${stats_previous['avg_basket']:.2f}"}
                        ]
                    },
                    {
                        'year': str(two_years_ago),
                        'stats': [
                            {'label': 'Revenue', 'value': format_currency(stats_two_years['total_revenue'])},
                            {'label': 'Tickets', 'value': format_number(stats_two_years['total_tickets'])},
                            {'label': 'Avg Basket', 'value': f"${stats_two_years['avg_basket']:.2f}"}
                        ]
                    }
                ]
            }
            
            # Analyze the trend trajectory
            recent_growth = calc_change(stats_current['total_revenue'], stats_previous['total_revenue'])
            older_growth = calc_change(stats_previous['total_revenue'], stats_two_years['total_revenue'])
            
            if recent_growth > older_growth:
                trend_insight['description'] += f"Growth is <strong>accelerating</strong> - {current_year} saw {recent_growth:.1f}% growth compared to {older_growth:.1f}% in the prior year.</p>"
            elif recent_growth < older_growth:
                trend_insight['description'] += f"Growth is <strong>decelerating</strong> - {current_year} saw {recent_growth:.1f}% growth compared to {older_growth:.1f}% in the prior year.</p>"
            else:
                trend_insight['description'] += f"Growth is <strong>consistent</strong> at approximately {recent_growth:.1f}% year-over-year.</p>"
            
            insights_list.append(trend_insight)
    
    # Prepare summary for the overview section
    summary = {
        'total_revenue': format_currency(stats_current['total_revenue']),
        'revenue_change': f"{abs(revenue_change):.1f}%",
        'revenue_trend': get_trend_class(revenue_change),
        'revenue_trend_icon': get_trend_icon(revenue_change),
        
        'total_tickets': format_number(stats_current['total_tickets']),
        'tickets_change': f"{abs(tickets_change):.1f}%",
        'tickets_trend': get_trend_class(tickets_change),
        'tickets_trend_icon': get_trend_icon(tickets_change),
        
        'avg_basket': f"${stats_current['avg_basket']:.2f}",
        'basket_change': f"{abs(basket_change):.1f}%",
        'basket_trend': get_trend_class(basket_change),
        'basket_trend_icon': get_trend_icon(basket_change),
        
        'cross_sell_rate': f"{stats_current['cross_sell_rate']:.1f}",
        'cross_sell_change': f"{abs(cross_sell_change):.1f}%",
        'cross_sell_trend': get_trend_class(cross_sell_change),
        'cross_sell_trend_icon': get_trend_icon(cross_sell_change)
    }
    
    # Date range text
    date_range_text = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}, {current_year}"
    if selected_locations:
        location_text = ', '.join(selected_locations[:3])
        if len(selected_locations) > 3:
            location_text += f" +{len(selected_locations) - 3} more"
        date_range_text += f" • {location_text}"
    
    context = {
        'insights': insights_list,
        'recommendations': recommendations,
        'summary': summary,
        'date_range_text': date_range_text,
        'current_year': current_year,
        'previous_year': previous_year,
        'two_years_ago': two_years_ago,

        'user_profile': user_profile,
        'is_admin': user_profile.is_admin
    }
    
    return render(request, 'insights.html', context)

def user_login(request):
    # If already logged in, go to dashboard
    if request.user.is_authenticated:
        return redirect('sales_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if user has profile
            try:
                profile = user.profile
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                
                # Try to redirect to 'next' parameter, otherwise dashboard
                next_url = request.GET.get('next', 'sales_dashboard')
                return redirect(next_url)
                
            except Exception as e:
                print(f"Profile error: {e}")  # Debug
                messages.error(request, "Your account is not configured. Contact administrator.")
                return redirect('login')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')

def user_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')
# sales_app/decorators.py
# Caching decorators for dashboard views

import hashlib
import json
from functools import wraps
from django.core.cache import cache


def cache_dashboard_view(timeout=900):
    """
    Decorator to cache entire dashboard view based on filters.
    
    Usage:
        @cache_dashboard_view(timeout=900)  # 15 minutes
        @login_required
        def dashboard(request):
            # ... your view code
    
    Args:
        timeout: Cache timeout in seconds (default 900 = 15 minutes)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Only cache GET requests
            if request.method != 'GET':
                return view_func(request, *args, **kwargs)
            
            # Build cache key from all filter parameters
            cache_key_data = {
                'view': view_func.__name__,
                'user_id': request.user.id,
                'comparison': request.GET.get('comparison', '2025-2024'),
                'start_date': request.GET.get('start_date', ''),
                'end_date': request.GET.get('end_date', ''),
                'locations': sorted(request.GET.getlist('un_filter')),
                'category': request.GET.get('category', 'all'),
                'product': request.GET.get('prod_filter', 'all'),
                'campaign': request.GET.get('campaign_filter', 'all'),
            }
            
            # Create hash of parameters for cache key
            cache_key = 'view_' + hashlib.md5(
                json.dumps(cache_key_data, sort_keys=True).encode()
            ).hexdigest()
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                print(f"✓ CACHE HIT: {view_func.__name__} ({cache_key[:16]}...)")
                return cached_response
            
            print(f"✗ CACHE MISS: {view_func.__name__} - Executing view...")
            
            # Execute view and cache the response
            response = view_func(request, *args, **kwargs)
            
            # Only cache successful responses
            if response.status_code == 200:
                cache.set(cache_key, response, timeout)
                print(f"✓ CACHED: {view_func.__name__} for {timeout}s")
            
            return response
        
        return wrapper
    return decorator
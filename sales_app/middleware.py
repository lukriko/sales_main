from django.shortcuts import redirect
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from sales_app.models import UserProfile
import time
import logging

logger = logging.getLogger(__name__)

class LocationAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip middleware for login/logout and ALL admin routes
        if request.path in ["/login/", "/logout/"] or request.path.startswith("/admin/"):
            return self.get_response(request)
        
        if request.user.is_authenticated:
            try:
                _ = request.user.profile
            except UserProfile.DoesNotExist:
                messages.error(request, "Your account is not properly configured. Contact admin.")
                return redirect("login")
        
        return self.get_response(request)


class QueryTimingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            # Get username
            username = request.user.username if request.user.is_authenticated else 'Anonymous'
            
            # Log with user info
            if duration > 1:
                logger.warning(
                    f"👤 {username} | ⚠️ Slow request: {request.path} took {duration:.2f}s"
                )
            else:
                logger.info(
                    f"👤 {username} | {request.method} {request.path} - {duration:.2f}s"
                )
        
        return response
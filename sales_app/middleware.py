from django.shortcuts import redirect
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from sales_app.models import UserProfile


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
    # paste your full class here
    pass

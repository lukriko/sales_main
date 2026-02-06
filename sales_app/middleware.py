# middleware.py
from django.shortcuts import redirect
from django.contrib import messages

class LocationAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip middleware for login/logout pages
        if request.path in ['/login/', '/logout/', '/admin/']:
            return self.get_response(request)
        
        # Check if user is authenticated
        if request.user.is_authenticated:
            # Ensure user has a profile
            if not hasattr(request.user, 'profile'):
                messages.error(request, "Your account is not properly configured. Contact admin.")
                return redirect('login')
        
        response = self.get_response(request)
        return response
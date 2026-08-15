from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'admin':
            messages.error(request, 'Admin access required.')
            if profile and profile.role in ('viewer', 'staff'):
                return redirect('dashboard')
            return redirect('account_logout')
        return view_func(request, *args, **kwargs)
    return wrapper


def viewer_or_admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_active_user:
            messages.error(request, 'Account is inactive or profile missing.')
            return redirect('account_logout')
        return view_func(request, *args, **kwargs)
    return wrapper


def staff_or_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_active_user:
            messages.error(request, 'Account is inactive or profile missing.')
            return redirect('account_logout')
        if profile.role == 'viewer':
            messages.error(request, 'Staff or Admin access required.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def staff_permission_required(permission_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('account_login')
            profile = getattr(request.user, 'profile', None)
            if not profile or not profile.is_active_user:
                messages.error(request, 'Account is inactive or profile missing.')
                return redirect('account_logout')
            if profile.role == 'admin':
                return view_func(request, *args, **kwargs)
            if profile.role == 'staff' and getattr(profile, permission_name, False):
                return view_func(request, *args, **kwargs)
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('dashboard')
        return wrapper
    return decorator


def is_admin(user):
    if not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'admin'


def is_viewer_or_admin(user):
    if not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.is_active_user


def is_staff_or_admin(user):
    if not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.is_active_user and profile.role in ('admin', 'staff')


def user_has_permission(user, permission_name):
    if not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    if not profile or not profile.is_active_user:
        return False
    return profile.role == 'admin' or (profile.role == 'staff' and getattr(profile, permission_name, False))

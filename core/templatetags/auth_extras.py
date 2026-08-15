import os
from django import template
from allauth.socialaccount.templatetags.socialaccount import provider_login_url
from allauth.socialaccount.models import SocialApp
from django.contrib.auth.models import AnonymousUser

register = template.Library()


@register.simple_tag
def google_enabled():
    has_env = bool(
        os.environ.get('GOOGLE_CLIENT_ID') and
        os.environ.get('GOOGLE_CLIENT_SECRET')
    )
    if has_env:
        return True
    try:
        return SocialApp.objects.filter(provider='google').exists()
    except Exception:
        return False


@register.simple_tag(takes_context=True)
def safe_provider_login_url(context, provider):
    try:
        return provider_login_url(context, provider)
    except SocialApp.DoesNotExist:
        return '#'


@register.simple_tag(takes_context=True)
def user_can(context, permission_name):
    user = context.get('user')
    if not user or not user.is_authenticated or isinstance(user, AnonymousUser):
        return False
    profile = getattr(user, 'profile', None)
    if not profile or not profile.is_active_user:
        return False
    if profile.role == 'admin':
        return True
    if profile.role == 'staff':
        return bool(getattr(profile, permission_name, False))
    return False

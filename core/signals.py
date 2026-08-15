from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.account.signals import user_signed_up, user_logged_in
from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(user_signed_up)
def track_first_login(sender, request, user, **kwargs):
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created or not profile.first_login:
        profile.first_login = user.last_login
        profile.login_count = 1
        profile.save()


@receiver(user_logged_in)
def track_login_activity(sender, request, user, **kwargs):
    profile, created = UserProfile.objects.get_or_create(user=user)
    if not profile.first_login:
        profile.first_login = user.last_login
    profile.last_login = user.last_login
    profile.login_count += 1
    profile.save()

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.account.signals import user_signed_up, user_logged_in
from .models import (
    UserProfile, Payment, StudentPeriodAccount, PeriodDefaultFee,
)


def apply_payment_mode_to_account(payment, account=None):
    """Apply the Payment.payment_mode to its StudentPeriodAccount.

    - default_fee: seed total_to_collect from the period's configured
      PeriodDefaultFee, but only when total_to_collect is still unset (0).
    - custom_full: seed total_to_collect with the payment amount, but only
      when total_to_collect is still unset (0).

    Never overwrites an already non-zero (manually configured) total_to_collect.
    """
    if not payment.period_id:
        return
    if account is None:
        account, _ = StudentPeriodAccount.objects.get_or_create(
            student=payment.student,
            period=payment.period,
        )

    if account.total_to_collect:
        return

    if payment.payment_mode == 'default_fee':
        default_fee = PeriodDefaultFee.objects.filter(
            period=payment.period
        ).first()
        if default_fee and default_fee.default_fee_per_student:
            account.total_to_collect = default_fee.default_fee_per_student
            account.save(update_fields=['total_to_collect', 'updated_at'])
    elif payment.payment_mode == 'custom_full':
        if payment.amount:
            account.total_to_collect = payment.amount
            account.save(update_fields=['total_to_collect', 'updated_at'])


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


@receiver(post_save, sender=Payment)
def ensure_student_period_account(sender, instance, created, **kwargs):
    if not instance.period_id:
        return
    account, _ = StudentPeriodAccount.objects.get_or_create(
        student=instance.student,
        period=instance.period,
    )
    apply_payment_mode_to_account(instance, account)

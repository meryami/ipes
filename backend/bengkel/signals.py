from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


def link_jemputan_to_user(user):
    """Link all Jemputan with matching email to this user account."""
    from .models import Jemputan
    Jemputan.objects.filter(email__iexact=user.email, user__isnull=True).update(user=user)


def ensure_profile(user):
    """Make sure UserProfile exists for this user."""
    from .models import UserProfile
    UserProfile.objects.get_or_create(user=user)


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    link_jemputan_to_user(user)
    ensure_profile(user)


@receiver(post_save, sender=User)
def on_user_created(sender, instance, created, **kwargs):
    if created:
        link_jemputan_to_user(instance)
        ensure_profile(instance)

# core/signals.py
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Advisor, Profile, Staff


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=Staff)
def auto_create_advisor_profile(sender, instance, created, **kwargs):
    """When a Staff record is created for a user with ADVISOR role,
    automatically create the corresponding Advisor profile."""
    if created and instance.user.role and instance.user.role.role_name == "ADVISOR":
        Advisor.objects.get_or_create(
            user=instance.user,
            defaults={"department": instance.department},
        )

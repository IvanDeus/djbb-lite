from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import avatars
from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, avatar=avatars.preset_for_id(instance.pk))


@receiver(post_delete, sender=Profile)
def remove_uploaded_avatar(sender, instance, **kwargs):
    """Cascade deletes take the row, not the picture; forget() ignores everything but an upload."""
    avatars.forget(instance.avatar)

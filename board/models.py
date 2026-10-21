from django.conf import settings
from django.db import models

from . import avatars


class Post(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class Comment(models.Model):
    post = models.ForeignKey(Post, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Profile(models.Model):
    """One row per user, holding the avatar the board renders. The post_save receiver creates it
    with the same rotation the migration backfilled, so an account never appears without a picture."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    avatar = models.CharField(max_length=255)

    def __str__(self):
        return self.user.username

    @property
    def avatar_url(self):
        return avatars.avatar_url(self.avatar)

    @property
    def picked_preset(self):
        """The preset to preselect, or an empty string when an upload holds the picture."""
        return self.avatar if self.avatar in avatars.AVATAR_PRESETS else ''

    @property
    def has_uploaded_avatar(self):
        return bool(avatars.AVATAR_UPLOAD.match(self.avatar))

    def set_avatar(self, preset, image):
        """Point this user at their picked preset, or at the resized copy of their upload when one
        came in - an upload always wins over the radio button it was submitted with.

        The picture reached here already encoded, so nothing can leave this row pointing at an
        avatar that was never written.
        """
        avatar = avatars.upload_name(self.user_id, image) if image else preset
        previous = self.avatar

        if avatar != previous:
            self.avatar = avatar
            self.save(update_fields=['avatar'])

        if image:
            avatars.write(avatar, image)

        if avatar != previous:
            avatars.forget(previous)

from django import template

from board import avatars

register = template.Library()


@register.filter
def avatar_url(avatar):
    """A stored value - a preset basename or an uploads/... path - as a URL."""
    return avatars.avatar_url(avatar)

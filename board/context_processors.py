from django.contrib.auth.models import User

from .models import Comment, Post


def board_stats(request):
    """Three counts for the footer, on every page.

    A topic is a post — this board has no separate thread/category model — so the trio is members,
    replies, topics. Counted per request rather than cached: three indexed COUNTs on tables this
    small cost less than anything that could go stale.
    """
    return {
        'stats': {
            'users': User.objects.count(),
            'comments': Comment.objects.count(),
            'topics': Post.objects.count(),
        }
    }

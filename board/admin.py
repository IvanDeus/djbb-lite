from django.contrib import admin
from django.utils.html import format_html

from .models import Comment, Post


def author_with_avatar(obj):
    return format_html(
        '<img src="{}" alt="" width="24" height="24" style="border-radius:50%;vertical-align:-6px;margin-right:.3rem"> {}',
        obj.author.profile.avatar_url,
        obj.author.username,
    )


author_with_avatar.short_description = 'author'


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', author_with_avatar, 'created_at')
    list_select_related = ('author__profile',)
    inlines = [CommentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('post', author_with_avatar, 'created_at')
    list_select_related = ('author__profile',)

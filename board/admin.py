from django.contrib import admin
from django.utils.html import format_html

from .models import Comment, Post, Profile


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


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """The board's people, for looking at and not for touching.

    View is the only permission this grants: add, change and delete are refused outright, so the
    detail page arrives in Django's read-only mode and every field has to be declared read-only to
    have anywhere to render at all. Editing accounts stays where it belongs — `/admin/auth/user/`.
    """

    list_display = ('avatar_tag', 'name', 'email')
    ordering = ('user__username',)
    search_fields = ('user__username', 'user__email')
    fields = ('name', 'email', 'avatar_tag')
    readonly_fields = ('name', 'email', 'avatar_tag')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    @admin.display(description='name', ordering='user__username')
    def name(self, obj):
        return obj.user.username

    @admin.display(description='e-mail', ordering='user__email')
    def email(self, obj):
        return obj.user.email

    @admin.display(description='avatar')
    def avatar_tag(self, obj):
        return format_html(
            '<img src="{}" alt="" width="48" height="48" style="border-radius:50%">', obj.avatar_url
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

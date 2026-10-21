from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import DateTimeField, F, Max
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import avatars
from .forms import CommentForm, PasswordChangeForm, PostForm, ProfileForm, RegistrationForm
from .models import Post


def _can_manage(user, post):
    return user.is_staff or post.author_id == user.pk


def post_list(request):
    posts = Post.objects.select_related('author__profile').order_by('-created_at')
    return render(request, 'board/post_list.html', {'posts': posts})


def post_detail(request, pk):
    post = Post.objects.select_related('author__profile').filter(pk=pk).first()
    if post is None:
        # Answering it here rather than raising: with DEBUG on, Django replaces any handler404 with
        # its own technical page, so a raised 404 would show a stack trace instead of this.
        return render(request, 'board/post_missing.html', status=404)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            return redirect('post_detail', pk=post.pk)
    else:
        form = CommentForm()
    return render(
        request,
        'board/post_detail.html',
        {
            'post': post,
            'comments': post.comments.select_related('author__profile'),
            'comment_form': form,
            'can_manage': _can_manage(request.user, post),
        },
    )


def user_detail(request, username):
    """One board member, at the size their picture was made for. Public, because the board shows
    these faces everywhere; the e-mail address is the one thing held back for staff."""
    person = get_object_or_404(User.objects.select_related('profile'), username=username)
    return render(
        request,
        'board/user_detail.html',
        {'person': person, 'show_email': request.user.is_staff},
    )


@login_required
def member_list(request):
    """The board's people, the one who wrote most recently first.

    Staff only, and the refusal is split the way the board's admin splits it: `login_required`
    sends a guest to the login page, and a writer who is not staff gets a 403 for having already
    logged in. Someone who never wrote is placed by the day they joined, so the ordering has no
    hole in it.
    """
    if not request.user.is_staff:
        raise PermissionDenied

    people = (
        User.objects.select_related('profile')
        .annotate(
            last_activity=Coalesce(
                Greatest(Max('post__created_at'), Max('comment__created_at')),
                F('date_joined'),
                output_field=DateTimeField(),
            )
        )
        .order_by('-last_activity')
    )

    return render(request, 'board/member_list.html', {'people': people})


@login_required
def post_create(request):
    form = PostForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('post_detail', pk=post.pk)
    return render(request, 'board/post_form.html', {'form': form, 'editing': False})


@login_required
def post_update(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not _can_manage(request.user, post):
        return redirect('post_detail', pk=pk)
    form = PostForm(request.POST or None, instance=post)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('post_detail', pk=pk)
    return render(request, 'board/post_form.html', {'form': form, 'editing': True})


@login_required
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not _can_manage(request.user, post):
        return redirect('post_detail', pk=pk)
    if request.method == 'POST':
        post.delete()
        return redirect(reverse('post_list'))
    return render(request, 'board/post_confirm_delete.html', {'post': post})


def signup(request):
    form = RegistrationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']

        # The receiver in signals.py gives the new row the id % 4 preset, which the picked one
        # replaces here - so the NOT NULL column is never left waiting on an upload.
        user = User.objects.create_user(username=username, email=form.cleaned_data['email'], password=password)
        user.profile.set_avatar(form.cleaned_data['avatar'], form.cleaned_data['avatar_file'])

        login(request, authenticate(username=username, password=password))
        return redirect('post_list')
    return render(request, 'registration/signup.html', {'form': form, 'presets': avatars.AVATAR_PRESETS})


@login_required
def profile(request):
    user_profile = request.user.profile
    posting = request.method == 'POST'
    # One page, two forms: the button that came back decides which one is bound, so a rejected
    # password never paints errors over the avatar picker beside it.
    changing_password = posting and 'change_password' in request.POST
    saving_avatar = posting and not changing_password

    avatar_form = ProfileForm(
        request.POST if saving_avatar else None,
        request.FILES if saving_avatar else None,
        initial={'avatar': user_profile.picked_preset},
    )
    password_form = PasswordChangeForm(request.user, request.POST if changing_password else None)

    if changing_password and password_form.is_valid():
        password_form.save()
        # The session is keyed to the password hash, so without this the visitor is logged out by
        # their own successful change.
        update_session_auth_hash(request, password_form.user)
        messages.success(request, 'Password changed.')
        return redirect('profile')

    if saving_avatar and avatar_form.is_valid():
        user_profile.set_avatar(avatar_form.cleaned_data['avatar'] or user_profile.avatar, avatar_form.cleaned_data['avatar_file'])
        return redirect('profile')

    return render(
        request,
        'board/profile.html',
        {
            'profile': user_profile,
            'form': avatar_form,
            'password_form': password_form,
            'presets': avatars.AVATAR_PRESETS,
        },
    )

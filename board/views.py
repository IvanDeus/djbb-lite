from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import avatars
from .forms import CommentForm, PostForm, ProfileForm, RegistrationForm
from .models import Post


def _can_manage(user, post):
    return user.is_staff or post.author_id == user.pk


def post_list(request):
    posts = Post.objects.select_related('author__profile').order_by('-created_at')
    return render(request, 'board/post_list.html', {'posts': posts})


def post_detail(request, pk):
    post = get_object_or_404(Post.objects.select_related('author__profile'), pk=pk)
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
    form = ProfileForm(request.POST or None, request.FILES or None, initial={'avatar': user_profile.picked_preset})
    if request.method == 'POST' and form.is_valid():
        user_profile.set_avatar(form.cleaned_data['avatar'] or user_profile.avatar, form.cleaned_data['avatar_file'])
        return redirect('profile')
    return render(
        request,
        'board/profile.html',
        {'profile': user_profile, 'form': form, 'presets': avatars.AVATAR_PRESETS},
    )

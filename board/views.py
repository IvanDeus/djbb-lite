from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import CommentForm, PostForm
from .models import Post


def _can_manage(user, post):
    return user.is_staff or post.author_id == user.pk


def post_list(request):
    posts = Post.objects.select_related('author').order_by('-created_at')
    return render(request, 'board/post_list.html', {'posts': posts})


def post_detail(request, pk):
    post = get_object_or_404(Post.objects.select_related('author'), pk=pk)
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
        {'post': post, 'comment_form': form, 'can_manage': _can_manage(request.user, post)},
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

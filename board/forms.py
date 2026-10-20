from django import forms

from .models import Comment, Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'body']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'field', 'placeholder': 'Title'}),
            'body': forms.Textarea(attrs={'class': 'field', 'rows': 8, 'placeholder': 'What is on the board?'}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={'class': 'field', 'rows': 3, 'placeholder': 'Reply...'}),
        }

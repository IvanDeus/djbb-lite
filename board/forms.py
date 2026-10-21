from django import forms
from django.contrib.auth.forms import PasswordChangeForm as AuthPasswordChangeForm
from django.contrib.auth.models import User

from . import avatars
from .models import Comment, Post


def avatar_preset_field(required):
    """Only the four committed basenames are accepted, so no path shape can be stored at all."""
    return forms.ChoiceField(
        label='Avatar',
        required=required,
        choices=[(preset, preset) for preset in avatars.AVATAR_PRESETS],
    )


class AvatarFileField(forms.FileField):
    """Sniffed, cropped and re-encoded during validation, so the store only ever writes bytes that
    decoded and a corrupt file cannot leave a row pointing at an avatar that does not exist.

    The preset and the file are separate keys on purpose: `avatar` is the only thing that reaches
    the database.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.FileInput(attrs={
            'class': 'field',
            'accept': 'image/jpeg,image/png,image/webp',
        }))
        super().__init__(**kwargs)

    def clean(self, data, initial=None):
        upload = super().clean(data, initial)
        if upload is None:
            return None
        if upload.size > avatars.MAX_UPLOAD_BYTES:
            raise forms.ValidationError('This picture is larger than 2 MB.')
        try:
            return avatars.normalize(upload)
        except avatars.AvatarError as error:
            raise forms.ValidationError(str(error)) from error


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


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'field', 'placeholder': 'Password (min 6 chars)'}))
    avatar = avatar_preset_field(required=True)
    avatar_file = AvatarFileField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'field', 'placeholder': 'Username'}),
            'email': forms.EmailInput(attrs={'class': 'field', 'placeholder': 'E-mail'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].required = True
        self.fields['email'].required = True
        self.fields['password'].min_length = 6

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username


class ProfileForm(forms.Form):
    """Leaving both fields empty keeps the avatar already on the row, which is the only way to hold
    on to an uploaded one: the whitelist accepts preset names alone."""

    avatar = avatar_preset_field(required=False)
    avatar_file = AvatarFileField()


class PasswordChangeForm(AuthPasswordChangeForm):
    """Django's form, which already runs the validators in AUTH_PASSWORD_VALIDATORS over the new
    password and compares it against the stored hash for `old_password`."""

    LABELS = {
        'old_password': 'Current password',
        'new_password1': 'New password',
        'new_password2': 'Type the new password again',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, label in self.LABELS.items():
            self.fields[name].label = label
            self.fields[name].widget.attrs.update({'class': 'field', 'placeholder': label})

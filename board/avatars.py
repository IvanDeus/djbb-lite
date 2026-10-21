"""What an avatar is: the four committed presets, the shape of an upload, and how a picture is
cropped and stored. Nothing here imports the models, so a Profile row is just an addressable name."""

import io
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from PIL import Image

# A stored avatar is either one of these basenames or an `uploads/{id}.{jpeg,png,webp}` path,
# always relative to AVATARS_ROOT.
AVATAR_PRESETS = ('fem-a1.png', 'fem-a2.png', 'male-b1.png', 'male-b2.png')

# Guards every unlink: nothing but this user's own upload can ever be addressed.
AVATAR_UPLOAD = re.compile(r'^uploads/\d{1,19}\.(?:jpeg|png|webp)$')

SIDE = 100
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
AVATAR_REJECTED = 'Please upload a readable JPG, PNG or WebP image.'

# Pillow format name => stored extension and the save() arguments that keep that container.
# PNG takes a compression level, the other two a quality, so the numbers are not the same kind.
FORMATS = {
    'JPEG': ('jpeg', {'quality': 90}),
    'PNG': ('png', {'compress_level': 6}),
    'WEBP': ('webp', {'quality': 90}),
}


class AvatarError(Exception):
    pass


@dataclass(frozen=True)
class AvatarImage:
    """A picture that has already been cropped, resampled and re-encoded, ready to be written."""

    bytes: bytes
    extension: str


def preset_for_id(user_id):
    """`id % 4` over the four presets, so a row keeps one preset for as long as it keeps its
    primary key. The migration backfill calls this same function."""
    return AVATAR_PRESETS[user_id % len(AVATAR_PRESETS)]


def upload_name(user_id, image):
    return f'uploads/{user_id}.{image.extension}'


def avatar_url(avatar):
    return f'{settings.STATIC_URL}avatars/{avatar}'


def root():
    return Path(settings.AVATARS_ROOT)


def normalize(upload):
    """Centre-crop to a square, resample to exactly 100x100, keep the source format so a transparent
    PNG is not flattened into a lossy container.

    GIF and AVIF both decode here, so the allowlist above is the only thing keeping them out.
    """
    upload.seek(0)
    try:
        image = Image.open(upload)
        image.load()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise AvatarError(AVATAR_REJECTED) from exc

    format_entry = FORMATS.get(image.format)
    if format_entry is None or min(image.size) < 1:
        raise AvatarError(AVATAR_REJECTED)
    extension, save_options = format_entry

    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        source = image.convert('RGBA')
    elif image.mode not in ('RGB', 'L'):
        source = image.convert('RGB')
    else:
        source = image

    side = min(source.size)
    left = (source.width - side) // 2
    top = (source.height - side) // 2
    square = source.crop((left, top, left + side, top + side)).resize((SIDE, SIDE), Image.Resampling.LANCZOS)

    if extension == 'jpeg' and square.mode != 'RGB':
        square = square.convert('RGB')

    buffer = io.BytesIO()
    try:
        square.save(buffer, format=image.format, **save_options)
    except OSError as exc:
        raise AvatarError(AVATAR_REJECTED) from exc
    data = buffer.getvalue()
    if not data:
        raise AvatarError(AVATAR_REJECTED)

    return AvatarImage(bytes=data, extension=extension)


def write(avatar, image):
    path = root() / avatar
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image.bytes)


def forget(avatar):
    """The pattern is what makes this safe: a stored value that is not an upload - a preset, or
    anything a hand-edited row might name - is never addressed to the filesystem."""
    if AVATAR_UPLOAD.match(avatar):
        (root() / avatar).unlink(missing_ok=True)

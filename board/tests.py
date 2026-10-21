import io
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import avatars

REJECTED = avatars.AVATAR_REJECTED


class AvatarTestCase(TestCase):
    """AVATARS_ROOT is the app's static tree, so a test that forgot to redirect it would write real
    files into a committed folder. Every avatar test runs against a scratch copy instead."""

    def setUp(self):
        super().setUp()
        root = Path(tempfile.mkdtemp(prefix='djbb-avatars-'))
        configuration = override_settings(AVATARS_ROOT=root)
        configuration.enable()
        self.addCleanup(configuration.disable)
        self.addCleanup(shutil.rmtree, root, True)
        self.root = root

    def upload(self, fmt='PNG', mode='RGBA', size=(180, 90), color=(255, 0, 0, 0), name='pic'):
        extension = fmt.lower()
        buffer = io.BytesIO()
        Image.new(mode, size, color).save(buffer, format=fmt)
        return SimpleUploadedFile(f'{name}.{extension}', buffer.getvalue(), content_type=f'image/{extension}')

    def image(self, **kwargs):
        """The form field hands the model an already-encoded picture; tests post the upload itself."""
        return avatars.normalize(self.upload(**kwargs))

    def stored_image(self, user):
        path = self.root / user.profile.avatar
        self.assertTrue(path.exists(), f'{path} was never written')
        return Image.open(path)


class ProfileRowTests(AvatarTestCase):
    def test_every_new_user_gets_the_rotated_preset(self):
        for number in range(4):
            User.objects.create_user(username=f'poet{number}', password='zxc123')

        for user in User.objects.order_by('pk'):
            self.assertEqual(user.profile.avatar, avatars.preset_for_id(user.pk))
            self.assertIn(user.profile.avatar, avatars.AVATAR_PRESETS)

    def test_preset_rotation_is_a_function_of_the_primary_key(self):
        self.assertEqual(list(map(avatars.preset_for_id, range(4, 8))), list(avatars.AVATAR_PRESETS))

    def test_deleting_an_account_takes_its_upload_with_it(self):
        user = User.objects.create_user(username='gone', password='zxc123')
        user.profile.set_avatar('fem-a1.png', self.image())
        path = self.root / user.profile.avatar
        self.assertTrue(path.exists())

        user.delete()

        self.assertFalse(path.exists())


class SignupAvatarTests(AvatarTestCase):
    def signup(self, payload):
        data = {'username': 'poet', 'email': 'poet@example.com', 'password': 'zxc123', 'avatar': 'fem-a1.png'}
        return self.client.post(reverse('signup'), {**data, **payload})

    def test_an_avatar_pick_is_required(self):
        response = self.signup({'avatar': ''})

        self.assertFormError(response.context['form'], 'avatar', 'This field is required.')
        self.assertFalse(User.objects.exists())

    def test_only_the_four_presets_can_ever_be_stored(self):
        response = self.signup({'avatar': '../../etc/passwd'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('Select a valid choice', response.context['form'].errors['avatar'][0])
        self.assertFalse(User.objects.exists())

    def test_the_picked_preset_is_stored_and_an_upload_beats_it(self):
        response = self.signup({'avatar_file': self.upload(fmt='WEBP', mode='RGB', color='navy')})

        self.assertRedirects(response, reverse('post_list'))
        user = User.objects.get(username='poet')
        self.assertEqual(user.profile.avatar, f'uploads/{user.pk}.webp')
        image = self.stored_image(user)
        self.assertEqual(image.size, (avatars.SIDE, avatars.SIDE))
        self.assertEqual(image.format, 'WEBP')

    def test_a_preset_pick_writes_no_file(self):
        self.signup({'avatar': 'male-b1.png'})

        self.assertEqual(User.objects.get(username='poet').profile.avatar, 'male-b1.png')
        self.assertEqual(list(self.root.glob('uploads/*')), [])

    def test_an_upload_is_cropped_to_the_short_side_and_keeps_its_transparency(self):
        self.signup({'avatar_file': self.upload()})

        image = self.stored_image(User.objects.get(username='poet'))
        self.assertEqual(image.size, (avatars.SIDE, avatars.SIDE))
        self.assertEqual(image.mode, 'RGBA')
        self.assertEqual(image.getpixel((50, 50))[3], 0)

    def test_the_upload_keeps_its_own_container(self):
        for fmt, mode, color in (('JPEG', 'RGB', 'white'), ('PNG', 'RGBA', (0, 0, 255, 255))):
            with self.subTest(fmt=fmt):
                User.objects.all().delete()
                self.signup({'avatar_file': self.upload(fmt=fmt, mode=mode, color=color)})

                user = User.objects.get(username='poet')
                self.assertEqual(user.profile.avatar, f'uploads/{user.pk}.{fmt.lower()}')
                self.assertEqual(self.stored_image(user).format, fmt)

    def test_a_file_that_is_not_a_readable_jpg_png_or_webp_is_rejected(self):
        cases = (
            ('text', SimpleUploadedFile('notes.txt', b'No image here.', content_type='text/plain')),
            ('gif', self.upload(fmt='GIF', mode='P', color='red')),
            ('truncated', SimpleUploadedFile('broken.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')),
        )
        for name, upload in cases:
            with self.subTest(name=name):
                response = self.signup({'avatar_file': upload})

                self.assertFormError(response.context['form'], 'avatar_file', REJECTED)
                self.assertFalse(User.objects.exists())
                self.assertEqual(list(self.root.glob('uploads/*')), [])

    def test_a_picture_over_two_megabytes_is_rejected(self):
        huge = SimpleUploadedFile(
            'huge.png', b'\x89PNG\r\n\x1a\n' + b'0' * (avatars.MAX_UPLOAD_BYTES + 1), content_type='image/png'
        )

        response = self.signup({'avatar_file': huge})

        self.assertFormError(response.context['form'], 'avatar_file', 'This picture is larger than 2 MB.')
        self.assertFalse(User.objects.exists())


class ProfilePageTests(AvatarTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='user', password='zxc123')
        self.client.force_login(self.user)

    def submit(self, payload=None, files=None):
        return self.client.post(reverse('profile'), {'avatar': '', **(payload or {}), **(files or {})})

    def test_an_empty_submission_keeps_an_uploaded_avatar(self):
        self.user.profile.set_avatar('fem-a1.png', self.image(fmt='JPEG', mode='RGB', color='white'))
        path = self.root / self.user.profile.avatar

        response = self.submit()

        self.assertRedirects(response, reverse('profile'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar, f'uploads/{self.user.pk}.jpeg')
        self.assertTrue(path.exists())

    def test_picking_a_preset_replaces_the_upload_and_removes_the_file(self):
        self.user.profile.set_avatar('fem-a1.png', self.image())
        path = self.root / self.user.profile.avatar

        self.submit({'avatar': 'male-b2.png'})

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar, 'male-b2.png')
        self.assertFalse(path.exists())

    def test_an_upload_replaces_the_preset_and_is_named_after_the_user(self):
        self.submit(files={'avatar_file': self.upload()})

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar, f'uploads/{self.user.pk}.png')

    def test_the_page_preselects_a_stored_preset(self):
        response = self.client.get(reverse('profile'))

        self.assertContains(response, f'value="{self.user.profile.avatar}" checked')

    def test_the_page_leaves_the_choice_open_and_admits_an_upload_holds_it_back(self):
        self.user.profile.set_avatar('fem-a1.png', self.image())

        response = self.client.get(reverse('profile'))

        self.assertNotContains(response, 'value="fem-a1.png" checked')
        self.assertContains(response, 'Your uploaded picture is kept unless you pick one of the four above.')

    def test_the_page_requires_a_login(self):
        self.client.logout()

        response = self.client.get(reverse('profile'))

        self.assertRedirects(response, f'{reverse("login")}?next={reverse("profile")}')


class StorageShapeTests(AvatarTestCase):
    def test_only_an_upload_can_ever_be_addressed_on_disk(self):
        preset = self.root / 'fem-a1.png'
        preset.write_bytes(b'preset')
        outside = self.root.parent / 'victim.png'
        outside.write_bytes(b'keep me')
        self.addCleanup(outside.unlink, True)

        for stored in ('fem-a1.png', '../victim.png', 'uploads/../victim.png', 'uploads/1.gif', ''):
            with self.subTest(stored=stored):
                avatars.forget(stored)

        self.assertTrue(preset.exists())
        self.assertTrue(outside.exists())

    def test_a_stored_value_becomes_one_of_two_url_shapes(self):
        self.assertEqual(avatars.avatar_url('fem-a1.png'), '/static/avatars/fem-a1.png')
        self.assertEqual(avatars.avatar_url('uploads/7.webp'), '/static/avatars/uploads/7.webp')

    def test_only_a_preset_or_an_own_upload_describes_the_row(self):
        user = User.objects.create_user(username='user', password='zxc123')

        user.profile.avatar = 'uploads/1.png'
        self.assertTrue(user.profile.has_uploaded_avatar)
        self.assertEqual(user.profile.picked_preset, '')

        user.profile.avatar = 'male-b1.png'
        self.assertFalse(user.profile.has_uploaded_avatar)
        self.assertEqual(user.profile.picked_preset, 'male-b1.png')


class RenderedAvatarTests(TestCase):
    def test_the_board_renders_an_avatar_next_to_every_author(self):
        user = User.objects.create_user(username='donne', password='zxc123')
        post = user.post_set.create(title='Holy Sonnets', body='Death, be not proud.')
        post.comments.create(author=user, body='And yet.')
        expected = f'src="/static/avatars/{user.profile.avatar}"'

        self.client.force_login(user)
        for url in (reverse('post_list'), reverse('post_detail', args=[post.pk]), reverse('profile')):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), expected)

    def test_the_signup_page_offers_the_four_presets(self):
        response = self.client.get(reverse('signup'))

        self.assertNotContains(response, 'checked')
        for preset in avatars.AVATAR_PRESETS:
            self.assertContains(response, f'src="/static/avatars/{preset}"')

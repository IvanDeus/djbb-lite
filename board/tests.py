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
from .models import Profile

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


NEW_PASSWORD = 'gathering-rosebuds'


class PasswordChangeTests(AvatarTestCase):
    OLD_PASSWORD = 'zxc123'

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='user', password=self.OLD_PASSWORD)
        self.client.force_login(self.user)

    def change(self, follow=False, **overrides):
        payload = {
            'change_password': '1',
            'old_password': self.OLD_PASSWORD,
            'new_password1': NEW_PASSWORD,
            'new_password2': NEW_PASSWORD,
        }
        return self.client.post(reverse('profile'), {**payload, **overrides}, follow=follow)

    def stored_password_still_works(self):
        self.user.refresh_from_db()
        return self.user.check_password(self.OLD_PASSWORD)

    def test_the_page_offers_both_forms_unbound(self):
        response = self.client.get(reverse('profile'))
        page = response.content.decode()

        self.assertContains(response, 'name="change_password"')
        for name in ('old_password', 'new_password1', 'new_password2'):
            self.assertIn(f'name="{name}"', page)
        self.assertEqual(response.context['password_form'].errors, {})
        self.assertEqual(response.context['form'].errors, {})

    def test_the_current_password_has_to_be_right(self):
        response = self.change(old_password='not-it')

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['password_form'],
            'old_password',
            'Your old password was entered incorrectly. Please enter it again.',
        )
        self.assertTrue(self.stored_password_still_works())
        # The avatar form stayed unbound, so the picker still shows what is stored rather than blank.
        self.assertContains(response, f'value="{self.user.profile.avatar}" checked')

    def test_the_two_new_passwords_have_to_match(self):
        response = self.change(new_password2='gathering-rosebuds?')

        self.assertFormError(
            response.context['password_form'], 'new_password2', 'The two password fields didn’t match.'
        )
        self.assertTrue(self.stored_password_still_works())

    def test_a_password_the_validators_refuse_is_refused(self):
        response = self.change(new_password1='12345678', new_password2='12345678')

        self.assertTrue(response.context['password_form'].errors)
        self.assertTrue(self.stored_password_still_works())

    def test_a_change_is_stored_and_the_session_survives_it(self):
        response = self.change()

        # Following the redirect only reaches /profile/ at all because update_session_auth_hash
        # moved the session to the new hash; otherwise this lands on the login page.
        self.assertRedirects(response, reverse('profile'), target_status_code=200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_the_board_says_the_change_worked(self):
        self.assertContains(self.change(follow=True), 'Password changed.')

    def test_the_avatar_is_left_out_of_a_password_change(self):
        self.user.profile.set_avatar('fem-a1.png', self.image())
        stored = self.user.profile.avatar

        self.change()

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar, stored)
        self.assertTrue((self.root / stored).exists())

    def test_saving_the_avatar_leaves_the_password_alone(self):
        self.client.post(reverse('profile'), {'avatar': 'male-b2.png'})

        self.assertTrue(self.stored_password_still_works())
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar, 'male-b2.png')


class ProfileAdminTests(TestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_superuser(username='overseer', email='overseer@example.com', password='thorn-apples-9')
        self.writer = User.objects.create_user(username='donne', email='donne@example.com', password='zxc123')
        self.profile = self.writer.profile
        self.client.force_login(self.owner)

    def test_the_list_shows_name_avatar_and_email_for_every_writer(self):
        response = self.client.get(reverse('admin:board_profile_changelist'))

        self.assertContains(response, 'donne')
        self.assertContains(response, 'donne@example.com')
        self.assertContains(response, f'src="/static/avatars/{self.profile.avatar}"')

    def test_the_detail_page_shows_a_profile_without_offering_to_edit_it(self):
        response = self.client.get(reverse('admin:board_profile_change', args=[self.profile.pk]))

        self.assertContains(response, 'donne@example.com')
        self.assertContains(response, f'src="/static/avatars/{self.profile.avatar}"')
        self.assertContains(response, 'class="readonly"')
        self.assertNotContains(response, 'name="_save"')

    def test_no_route_through_this_admin_writes_anything(self):
        for name, args, payload in (
            ('board_profile_add', [], None),
            ('board_profile_delete', [self.profile.pk], None),
        ):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(f'admin:{name}', args=args)).status_code, 403)

        forged = self.client.post(
            reverse('admin:board_profile_change', args=[self.profile.pk]), {'email': 'forged@example.com'}
        )
        bulk = self.client.post(
            reverse('admin:board_profile_changelist'),
            {'action': 'delete_selected', 'select_across': '1', '_selected_action': [self.profile.pk]},
        )

        self.assertEqual(forged.status_code, 403)
        self.assertTrue(Profile.objects.filter(pk=self.profile.pk).exists())
        self.writer.refresh_from_db()
        self.assertEqual(self.writer.email, 'donne@example.com')

    def test_a_staff_user_without_the_view_permission_is_turned_away(self):
        User.objects.create_user(username='intern', password='thorn-apples-9', is_staff=True)
        self.client.force_login(User.objects.get(username='intern'))

        self.assertEqual(self.client.get(reverse('admin:board_profile_changelist')).status_code, 403)
        self.assertNotContains(self.client.get(reverse('admin:index')), '/admin/board/profile/')

    def test_anonymous_never_reaches_it(self):
        self.client.logout()

        response = self.client.get(reverse('admin:board_profile_changelist'))

        self.assertRedirects(response, f'/admin/login/?next={reverse("admin:board_profile_changelist")}')


class MissingPostTests(TestCase):
    def test_a_missing_id_answers_in_the_boards_own_voice(self):
        response = self.client.get('/post/1/')

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'No such post', status_code=404)
        self.assertContains(response, 'That topic does not exist, or it has been deleted.', status_code=404)

    def test_the_page_hands_the_visitor_back_to_the_board_after_two_seconds(self):
        response = self.client.get('/post/1/')

        self.assertContains(response, '<meta http-equiv="refresh" content="2;url=/">', html=True, status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)

    def test_a_post_deleted_since_the_link_was_made_takes_the_same_route(self):
        author = User.objects.create_user(username='marvell', password='zxc123')
        post = author.post_set.create(title='To His Coy Mistress', body='Had we but world enough.')
        url = reverse('post_detail', args=[post.pk])

        post.delete()

        self.assertContains(self.client.get(url), 'No such post', status_code=404)

    def test_an_id_too_large_for_the_column_counts_as_missing(self):
        self.assertContains(self.client.get('/post/99999999999999999999/'), 'No such post', status_code=404)

    def test_a_post_that_does_exist_still_renders(self):
        author = User.objects.create_user(username='donne', password='zxc123')
        post = author.post_set.create(title='The Annunciation', body='As wise at love thou wentest.')

        response = self.client.get(reverse('post_detail', args=[post.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The Annunciation')


class MemberPageTests(TestCase):
    def setUp(self):
        super().setUp()
        self.writer = User.objects.create_user(username='donne', email='donne@example.com', password='zxc123')
        self.url = reverse('user_detail', args=['donne'])
        self.avatar = f'src="/static/avatars/{self.writer.profile.avatar}"'

    def test_anyone_can_see_the_face_and_the_name(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h2>donne</h2>')
        self.assertContains(response, self.avatar)
        self.assertContains(response, 'width="100" height="100"')

    def test_the_address_is_not_for_public_eyes(self):
        self.assertNotContains(self.client.get(self.url), 'donne@example.com')

        self.client.force_login(User.objects.create_user(username='marvell', password='zxc123'))
        self.assertNotContains(self.client.get(self.url), 'donne@example.com')

    def test_staff_sees_the_address_too(self):
        self.client.force_login(User.objects.create_user(username='overseer', password='zxc123', is_staff=True))

        self.assertContains(self.client.get(self.url), 'donne@example.com')

    def test_every_avatar_on_the_board_links_here(self):
        post = self.writer.post_set.create(title='The Canonization', body='For whom have we loved?')
        post.comments.create(author=self.writer, body='Let it be.')
        link = f'href="{self.url}"'

        for url in (reverse('post_list'), reverse('post_detail', args=[post.pk])):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), link)

    def test_a_name_that_is_not_on_the_board_is_not_found(self):
        self.assertEqual(self.client.get('/user/herbert-never-wrote/').status_code, 404)


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

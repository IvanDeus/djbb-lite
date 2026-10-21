"""Seed the board with the documented accounts and a thread of 17th-century poetry to look at."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from board.models import Comment, Post

METAPHYSICAL = 'Metaphysical conceit'
CAVALIER = 'Cavalier and Royalist'
SACRED = 'Epic and sacred verse'

ACCOUNTS = (
    ('admin', 'pass123', 'male-b1.png', True),
    ('user', 'zxc123', 'fem-a2.png', False),
    ('cleric', 'zxc123', 'fem-a1.png', False),
    ('cavalier', 'zxc123', 'male-b2.png', False),
)

# Twenty notes on seventeenth-century verse, each carrying its theme, listed so the themes alternate
# down the page and handed to the writers in turn: five posts each, and because 3 and 4 share no
# factor, every writer ends up with a spread of themes.
POEMS = (
    (METAPHYSICAL, "Donne, 'The Flea'", 'Donne makes a flea the whole of an argument: the insect has already bitten '
     'both of them, so their blood is mixed whether she consents or not. The conceit works because the '
     'logic is knowingly dishonest and the speaker enjoys the trick.'),
    (CAVALIER, "Herrick, 'To the Virgins, to Make Much of Time'", 'Gather ye rosebuds while ye may: four lines '
     'of carpe diem set to a tune that keeps the urgency light. The warning about lost prime is '
     'older than the poem and Herrick does not pretend otherwise.'),
    (SACRED, "Milton, 'Paradise Lost' (1667)", "Of Man's first disobedience: an epic that opens by naming its "
     'subject, its source and its machinery in one sentence, then keeps the promise for twelve books. '
     'Blank verse and a Protestant suspicion of ornament, at scale.'),
    (METAPHYSICAL, "Donne, 'A Valediction: Forbidding Mourning'", 'Parting is drawn as geometry - two lovers are '
     'the fixed foot and the roaming foot of a pair of compasses, so that the circle the lover traces '
     'ends where it started. Physical absence becomes proof of steadiness.'),
    (CAVALIER, "Herrick, 'Corinna's Going A-Maying'", 'An invitation to the maypole, written as a list of what '
     "the morning is already doing without her. Herrick's country verse keeps its ceremony and its "
     'sense of an ending in the same stanza.'),
    (SACRED, "Milton, 'On the Morning of Christ's Nativity'", 'A hymn written at twenty-one that stages the '
     'Nativity as the end of pagan gods: the orbits fall silent, the oracles go pale. Early Milton, '
     'already arranging a large scene out of a small event.'),
    (METAPHYSICAL, "Herbert, 'Easter Wings'", 'The poem is printed sideways: each stanza thins to a single syllable '
     'and swells again, so the shape of the page performs the falling and rising the argument claims. '
     'Herbert never separated what a poem says from how it sits.'),
    (CAVALIER, "Lovelace, 'To Lucasta, Going to the Wars'", 'The story has him writing it inside a cylinder of '
     'prison glass; the poem is calmer than the anecdote, answering the charge that leaving is '
     'unkindness by ranking honour above the person honoured.'),
    (SACRED, "Milton, 'When I Consider How My Light is Spent'", 'The sonnet asks whether God exacts daily '
     'labour from a man who can no longer see, and answers with patience: his best servants are those '
     'who bear his mild yoke. A sonnet of doubt, quoted in epics about blindness.'),
    (METAPHYSICAL, "Herbert, 'The Pulley'", 'God pours almost every blessing on mankind and keeps rest back, so that '
     'weariness drags the creature home to its maker. A mechanical image carries an argument about '
     'why humans cannot be satisfied.'),
    (CAVALIER, "Lovelace, 'The Grasshopper'", "The insect is compared with a rich man's estate and comes out "
     "better: the poet sings in an arbour of his own making. Poverty is recast as freedom, which is "
     'how Royalist gentlemen wrote about losing money.'),
    (SACRED, "Milton, 'Samson Agonistes' (1671)", 'A closet drama that keeps the wrestling off the stage and '
     "stays inside the ruined man's regret, ending on a consent nobody in the poem talks about. "
     'Printed with Paradise Regained as one volume, in the same year.'),
    (METAPHYSICAL, "Marvell, 'To His Coy Mistress'", 'The speaker grants, for a stanza, the premise he means to '
     'destroy: had they world and time enough, hesitation would cost nothing. Then the vanity of the '
     'pretence collapses into an argument for haste, with worms and a chimney of fire doing the work.'),
    (CAVALIER, "Suckling, 'Why so pale and wan, fond lover?'", 'A song that tells the melancholy lover the '
     "diagnosis: she will not sigh him into noticing her. The refrain's shrug is the whole poem, "
     'and the wit is aimed at pose rather than at the girl.'),
    (SACRED, "Crashaw, 'Steps to the Temple' (1646)", 'Sacred verse in the Herbert school taken further: '
     'tears, altars and overripe fruit as devotional equipment. The 1646 edition with its second '
     'part, Delphos, is the collection that made English religious poetry look baroque.'),
    (METAPHYSICAL, "Vaughan, 'The Retreat'", 'A grown man asks to be sent back to infancy, where the soul was '
     "thought to come freshly out of God's hand. The poem treats childhood as the last clean sight "
     'before the world begins to stain it.'),
    (CAVALIER, "Carew, 'He that loves a rosy cheek'", 'Carew lists the features a lover normally praises and '
     'then discards them for a mind worth more than the usual red and white. Elegant, ironic, and '
     'written in the same metre he would mock in others.'),
    (SACRED, "Milton, 'Paradise Regained' (1671)", 'Where Paradise Lost spends its strength on spectacle, this '
     'poem stages a temptation almost nothing happens in, and argues that standing still is the '
     'harder heroism. The shorter epic reads as a deliberate reply to the longer one.'),
    (METAPHYSICAL, "Crashaw, 'The Weaning-Bell'", 'Overripe pears and figs become the figure for a soul that will '
     'not give up sweetness. Crashaw pushes the image past taste on purpose: the fruit is '
     'delicious, and that is exactly the danger.'),
    (CAVALIER, 'Katherine Philips, coterie verse', 'Philips wrote friendship poetry for a circle that gave each '
     'other pastoral names, and was published as the "Matchless Poet". Her work belongs to the same '
     'Royalist sociability as Lovelace, with the allegiance shifted to the company itself.'),
)

REPLIES = (
    ("Donne, 'The Flea'", 'cleric', 'The same trick, cleaner: Crashaw\'s pears are ripe because they '
     'are dangerous, not because the argument needs them.'),
    ("Marvell, 'To His Coy Mistress'", 'cavalier', 'Herrick says the same thing in four lines and '
     'without the worms. I prefer the four lines.'),
    ("Herbert, 'Easter Wings'", 'user', 'Read the page sideways and it turns out the argument is the '
     'shape. Worth the printing cost the first time I saw it.'),
    ("Milton, 'Paradise Lost' (1667)", 'admin', 'The opening sentence does more work than most poems '
     'manage in a page, and then the poem keeps going for twelve books.'),
    ("Lovelace, 'To Lucasta, Going to the Wars'", 'cavalier', 'Written out of prison, and it still '
     'argues the case as if honour were simply the better term. Courtly verse at its most composed.'),
    ("Vaughan, 'The Retreat'", 'cleric', 'Herbert would have said the same about rest; Vaughan wants '
     'to be small instead. Both readings end in the same place.'),
    ("Suckling, 'Why so pale and wan, fond lover?'", 'user', 'A song, and it knows it. Carew is the '
     'same wit with more polish and less air.'),
    ("Crashaw, 'Steps to the Temple' (1646)", 'cavalier', 'Delphos is where the pile gets absurd, and '
     'absurd is part of the point.'),
)


class Command(BaseCommand):
    help = 'Create four users, twenty posts on three themes of 17th-century poetry, and replies.'

    def handle(self, *args, **options):
        now = timezone.now()
        writers = []
        for offset, (username, password, preset, staff) in enumerate(ACCOUNTS):
            user, created = User.objects.get_or_create(username=username, defaults={'email': f'{username}@example.com'})
            if created:
                user.set_password(password)
                if staff:
                    user.is_staff = user.is_superuser = True
                user.save()
            user.profile.set_avatar(preset, None)
            writers.append(user)
            self.stdout.write(f'{"created" if created else "kept"}: {username} ({preset})')

        existing = set(Post.objects.values_list('title', flat=True))
        for number, (theme, title, body) in enumerate(POEMS):
            if title in existing:
                continue
            author = writers[number % len(writers)]
            post = Post.objects.create(title=title, body=f'Theme: {theme}\n\n{body}', author=author)
            Post.objects.filter(pk=post.pk).update(created_at=now - timedelta(days=len(POEMS) - number, hours=number % 6))
            self.stdout.write(f'posted: {title} by {author.username} [{theme}]')

        for title, username, body in REPLIES:
            post = Post.objects.filter(title=title).first()
            if post is None or post.comments.filter(author__username=username).exists():
                continue
            comment = post.comments.create(author=User.objects.get(username=username), body=body)
            Comment.objects.filter(pk=comment.pk).update(created_at=post.created_at + timedelta(hours=3))
            self.stdout.write(f'replied: {username} on {title}')

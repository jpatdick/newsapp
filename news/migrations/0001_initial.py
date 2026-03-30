# Generated migration for the news application.
# Creates tables for: Publisher, CustomUser, Article, Newsletter
# and their associated M2M join tables.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # ------------------------------------------------------------
        # Publisher
        # ------------------------------------------------------------
        migrations.CreateModel(
            name='Publisher',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(
                    max_length=255, unique=True,
                )),
                ('description', models.TextField(blank=True)),
                ('website', models.URLField(blank=True)),
                (
                    'created_at',
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                    ),
                ),
            ],
            options={
                'ordering': ['name'],
            },
        ),

        # ------------------------------------------------------------
        # CustomUser
        # ------------------------------------------------------------
        migrations.CreateModel(
            name='CustomUser',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                # AbstractUser base fields
                ('password', models.CharField(
                    max_length=128,
                    verbose_name='password',
                )),
                ('last_login', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='last login',
                )),
                ('is_superuser', models.BooleanField(
                    default=False,
                    help_text=(
                        'Designates that this user has all permissions'
                        ' without explicitly assigning them.'
                    ),
                    verbose_name='superuser status',
                )),
                ('username', models.CharField(
                    error_messages={
                        'unique': (
                            'A user with that username already exists.'
                        ),
                    },
                    max_length=150,
                    unique=True,
                    verbose_name='username',
                )),
                ('first_name', models.CharField(
                    blank=True,
                    max_length=150,
                    verbose_name='first name',
                )),
                ('last_name', models.CharField(
                    blank=True,
                    max_length=150,
                    verbose_name='last name',
                )),
                ('email', models.EmailField(
                    blank=True,
                    max_length=254,
                    verbose_name='email address',
                )),
                ('is_staff', models.BooleanField(
                    default=False,
                    help_text=(
                        'Designates whether the user can log into'
                        ' the admin site.'
                    ),
                    verbose_name='staff status',
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text=(
                        'Designates whether this user should be'
                        ' treated as active.'
                    ),
                    verbose_name='active',
                )),
                (
                    'date_joined',
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        verbose_name='date joined',
                    ),
                ),
                # Custom fields
                ('role', models.CharField(
                    choices=[
                        ('reader', 'Reader'),
                        ('journalist', 'Journalist'),
                        ('editor', 'Editor'),
                    ],
                    default='reader',
                    max_length=20,
                )),
                ('publisher', models.ForeignKey(
                    blank=True,
                    help_text=(
                        'The publisher this journalist/editor'
                        ' works for.'
                    ),
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='staff',
                    to='news.publisher',
                )),
                # Re-declared M2M fields to avoid reverse accessor
                # clashes with auth.User
                ('groups', models.ManyToManyField(
                    blank=True,
                    related_name='custom_users',
                    to='auth.group',
                )),
                ('user_permissions', models.ManyToManyField(
                    blank=True,
                    related_name='custom_users',
                    to='auth.permission',
                )),
            ],
            options={
                'ordering': ['username'],
            },
        ),

        # subscribed_publishers: Reader -> Publisher (M2M)
        migrations.AddField(
            model_name='customuser',
            name='subscribed_publishers',
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    'Publishers this reader has subscribed to.'
                ),
                related_name='subscriber_readers',
                to='news.publisher',
            ),
        ),

        # subscribed_journalists: Reader -> CustomUser (self M2M)
        migrations.AddField(
            model_name='customuser',
            name='subscribed_journalists',
            field=models.ManyToManyField(
                blank=True,
                help_text='Journalists this reader follows.',
                related_name='reader_followers',
                symmetrical=False,
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        # ------------------------------------------------------------
        # Article
        # ------------------------------------------------------------
        migrations.CreateModel(
            name='Article',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField()),
                (
                    'created_at',
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                    ),
                ),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved', models.BooleanField(
                    default=False,
                    help_text=(
                        'Set to True by an editor to publish'
                        ' the article.'
                    ),
                )),
                ('author', models.ForeignKey(
                    help_text=(
                        'The journalist who authored this article.'
                    ),
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='authored_articles',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('publisher', models.ForeignKey(
                    blank=True,
                    help_text=(
                        'Leave blank for independent'
                        ' (journalist-only) articles.'
                    ),
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='articles',
                    to='news.publisher',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),

        # ------------------------------------------------------------
        # Newsletter
        # ------------------------------------------------------------
        migrations.CreateModel(
            name='Newsletter',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                (
                    'created_at',
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                    ),
                ),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(
                    help_text=(
                        'The journalist who curated this newsletter.'
                    ),
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='authored_newsletters',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('articles', models.ManyToManyField(
                    blank=True,
                    help_text=(
                        'Approved articles included in this'
                        ' newsletter.'
                    ),
                    related_name='newsletters',
                    to='news.article',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

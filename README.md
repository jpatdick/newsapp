# NewsApp – Django News Application

A full-featured Django news platform with role-based access control,
a RESTful API (JWT-authenticated), and automated tests.

---

## Project Structure

```
newsapp/
├── newsproject/          # Django project settings & root URLs
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── news/                 # Main application
│   ├── models.py         # CustomUser, Publisher, Article, Newsletter
│   ├── signals.py        # Group assignment + approval signal (email & API call)
│   ├── serializers.py    # DRF serializers
│   ├── permissions.py    # Custom DRF permission classes
│   ├── api_views.py      # REST API views
│   ├── api_urls.py       # REST API URL routes  (/api/...)
│   ├── views.py          # Web UI views (templates)
│   ├── urls.py           # Web UI URL routes
│   ├── forms.py          # Django forms
│   ├── admin.py          # Admin configuration
│   ├── apps.py           # AppConfig (wires up signals)
│   ├── tests.py          # Automated unit tests (12 test classes)
│   ├── templates/news/   # HTML templates
│   └── management/
│       └── commands/
│           └── setup_news_groups.py
├── .env.example          # Environment variable template
├── requirements.txt
└── README.md
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <repository-url>
cd newsapp
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

### 3. Install dependencies

The `requirements.txt` file includes `mysqlclient`, the MariaDB/MySQL database
driver, so no separate driver installation is needed.

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

The application reads sensitive credentials from environment variables so that
secrets are never hardcoded. A template file is provided in the project root:

```bash
cp .env.example .env
```

Open `.env` and fill in your values. The required variables are:

```
SECRET_KEY=your-django-secret-key
DEBUG=True
DB_NAME=newsapp_db
DB_USER=newsapp_user
DB_PASSWORD=your-db-password
DB_HOST=127.0.0.1
DB_PORT=3306
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
```

See steps 5-8 below for how to obtain the database and Gmail values.
The application reads from these variables at runtime. Never commit your
`.env` file to version control — it should be listed in `.gitignore`.

### 5. Create a MariaDB user account

Before logging into MariaDB, you need an account. If you have not yet set a
root password, secure your installation first:

```bash
sudo mysql_secure_installation
```

Follow the prompts to set a root password and harden the defaults. Once that
is done you can log in:

```bash
mysql -u root -p
```

### 6. Create the database and a dedicated user

Inside the MariaDB shell, run the following SQL, replacing `your_password`
with the value you will put in your `.env` file for `DB_PASSWORD`:

```sql
CREATE DATABASE newsapp_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'newsapp_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON newsapp_db.* TO 'newsapp_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 7. Verify database settings in settings.py

`newsproject/settings.py` reads the database connection from the environment
variables you set in step 4. The defaults match the values above:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'newsapp_db'),
        'USER': os.environ.get('DB_USER', 'newsapp_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}
```

If you used different credentials in step 6, update the corresponding values
in your `.env` file rather than editing `settings.py` directly.

### 8. Configure Gmail SMTP for email

The application sends approval notification emails via Gmail SMTP. You will
need a Gmail App Password (not your regular Gmail password):

1. Enable 2-Step Verification on your Google account at
   https://myaccount.google.com/security
2. Generate an App Password at https://myaccount.google.com/apppasswords —
   select "Mail" and your device type.
3. Add the following to your `.env` file:

```
EMAIL_HOST_USER=your_gmail_address@gmail.com
EMAIL_HOST_PASSWORD=your_16_character_app_password
```

`settings.py` is already configured to use Gmail SMTP and will pick up these
values automatically:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
```

### 9. Apply migrations

```bash
cd newsapp
python manage.py makemigrations news
python manage.py migrate
```

### 10. Create role groups and permissions

```bash
python manage.py setup_news_groups
```

### 11. Create a superuser (developer admin access)

```bash
python manage.py createsuperuser
```

> **Note:** The admin panel (`/admin/`) is intended for developer use only, not
> for day-to-day application use. Regular application users (readers,
> journalists, editors) should use the web interface described below.

### 12. Run the development server

```bash
python manage.py runserver
```

---

## Setup with Docker

If you have [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed, you can bring up the entire application — including a MariaDB database — with a single command, skipping the 12-step manual setup entirely.

### Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose CLI) installed and running.
- A copy of the repository cloned locally.

### 1. Configure email credentials (optional)

The application sends approval notification emails via Gmail SMTP. If you want
email notifications to work, open `docker-compose.yml` and fill in your
credentials in the `web` service's `environment` block:

```yaml
EMAIL_HOST_USER: your_gmail@gmail.com
EMAIL_HOST_PASSWORD: your_16_character_app_password
```

If you leave these blank the app will still run; only approval email delivery
will be skipped.

### 2. Launch the environment

From the project root (the folder containing `docker-compose.yml`), run:

```bash
docker-compose up --build
```

This single command will:

1. Build the Django application image from the `Dockerfile`.
2. Pull and start a MariaDB 10.11 container.
3. Wait for the database to pass its health check before starting Django.
4. Run `python manage.py migrate` to apply all database migrations automatically.
5. Run `python manage.py setup_news_groups` to create the Reader, Journalist, and Editor permission groups automatically.
6. Start the Django development server on `http://localhost:8000`.

### 3. Create a superuser (optional)

To access the Django admin panel at `/admin/`, open a second terminal and run:

```bash
docker-compose exec web python manage.py createsuperuser
```

### 4. Stop the environment

Press `Ctrl+C` in the terminal running Compose, then run:

```bash
docker-compose down
```

Database data is persisted in a named Docker volume (`mariadb_data`), so your
data will still be there the next time you run `docker-compose up`.

## Creating Publishers

Publishers must be created before journalists can associate their articles with
one. This is handled by **Editors** directly through the web interface — no
admin panel access is required.

1. Log in as a user with the **Editor** role.
2. Click **+ Publisher** in the navigation bar, or navigate to
   `/publishers/create/`.
3. Fill in the publisher name, description, and website, then submit.

Editors can also edit existing publishers from the Publishers page.
Once a publisher exists, journalists will see it as an option when creating
or editing an article.

---

## User Roles

| Role       | Create Article | Edit Article          | Delete Article | Approve Article | Create Newsletter | Edit/Delete Newsletter | Create Publisher | View |
|------------|:--------------:|:---------------------:|:--------------:|:---------------:|:-----------------:|:----------------------:|:----------------:|:----:|
| Reader     |       ✗        |          ✗            |       ✗        |        ✗        |         ✗         |           ✗            |        ✗         |  ✓   |
| Journalist |       ✓        | Own, unpublished only |       ✗        |        ✗        |         ✓         |       Own only         |        ✗         |  ✓   |
| Editor     |       ✗        |          ✓            |       ✓        |        ✓        |         ✗         |           ✓            |        ✓         |  ✓   |

> Journalists may only edit their own articles that have **not yet been approved**.
> Once an editor approves an article it is locked from further journalist edits.

---

## REST API Endpoints

All API endpoints are prefixed with `/api/`.

### Authentication

| Method | Endpoint              | Description                        |
|--------|-----------------------|------------------------------------|
| POST   | `/api/token/`         | Obtain JWT access + refresh tokens |
| POST   | `/api/token/refresh/` | Refresh an expired access token    |
| POST   | `/api/register/`      | Register a new user                |

### Articles

| Method | Endpoint                       | Permission                | Description                          |
|--------|--------------------------------|---------------------------|--------------------------------------|
| GET    | `/api/articles/`               | Any authenticated         | List all approved articles           |
| POST   | `/api/articles/`               | Journalist only           | Create a new article                 |
| GET    | `/api/articles/subscribed/`    | Reader only               | Articles from subscribed sources     |
| GET    | `/api/articles/<id>/`          | Any authenticated         | Retrieve a single article            |
| PUT    | `/api/articles/<id>/`          | Owner journalist / Editor | Update an article                    |
| DELETE | `/api/articles/<id>/`          | Owner journalist / Editor | Delete an article                    |
| POST   | `/api/articles/<id>/approve/`  | Editor only               | Approve an article for publication   |

### Newsletters

| Method | Endpoint                 | Permission                | Description              |
|--------|--------------------------|---------------------------|--------------------------|
| GET    | `/api/newsletters/`      | Any authenticated         | List all newsletters     |
| POST   | `/api/newsletters/`      | Journalist only           | Create a newsletter      |
| GET    | `/api/newsletters/<id>/` | Any authenticated         | Retrieve a newsletter    |
| PUT    | `/api/newsletters/<id>/` | Owner journalist / Editor | Update a newsletter      |
| DELETE | `/api/newsletters/<id>/` | Owner journalist / Editor | Delete a newsletter      |

### Internal

| Method | Endpoint          | Description                                     |
|--------|-------------------|-------------------------------------------------|
| POST   | `/api/approved/`  | Internal webhook called by the approval signal  |

---

## Approval Workflow (Django Signals)

When an editor approves an article (`article.approved = True` saved):

1. **`article_approved` signal** fires via `post_save`.
2. **`_notify_subscribers`** sends an email via Gmail SMTP to all readers who
   follow the journalist or have subscribed to the publisher.
3. **`_post_to_approved_endpoint`** sends a POST request to
   `/api/approved/` with the article details (simulates external integration).

---

## Running Tests

```bash
python manage.py test news
```

The test suite covers:
- JWT authentication (valid/invalid credentials, registration)
- Role group permission assignment
- Article CRUD per role (journalist, editor, reader, unauthenticated)
- Subscribed articles filtered by reader subscriptions
- Newsletter CRUD per role
- Signal/email behaviour (using `unittest.mock`)
- Internal `/api/approved/` webhook

---

## Database Design (3NF Normalisation)

```
Publisher(id, name, description, website, created_at)

CustomUser(id, username, email, role, publisher_id→Publisher, ...)
  Reader fields  : subscribed_publishers (M2M→Publisher)
                   subscribed_journalists (M2M→CustomUser)
  Journalist fields: reverse FK from Article.author
                     reverse FK from Newsletter.author

Article(id, title, content, created_at, updated_at, approved,
        author_id→CustomUser, publisher_id→Publisher nullable)

Newsletter(id, title, description, created_at, updated_at,
           author_id→CustomUser)
NewsletterArticle(newsletter_id→Newsletter, article_id→Article)  [M2M join table]
```

All non-key attributes depend solely on the primary key — no partial or
transitive dependencies — satisfying Third Normal Form (3NF).

from .settings import *
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "auto_triage_test",
        "USER": "triage_test_user",
        "PASSWORD": "triage_test_password",
        "HOST": "test_db",
        "PORT": "5432",
    }
}
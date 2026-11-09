from pathlib import Path

import environ
from django.urls import reverse_lazy

from apps.core.unfold import is_owner

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")  
DEBUG = env.bool("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    # local
    "apps.core",
    "apps.accounts",
    "apps.customers",
    "apps.products",
    "apps.inventory",
    "apps.orders",
    "apps.finance",
    'apps.reports',

]

UNFOLD = {
    "SITE_TITLE": "MebelERP",
    "SITE_HEADER": "MebelERP",
    "DASHBOARD_CALLBACK": "apps.core.dashboard.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,  # avtomatik app ro'yxati o'chadi
        "navigation": [
            {
                "title": "Savdo",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "Buyurtmalar", "icon": "shopping_cart",
                     "link": reverse_lazy("admin:orders_order_changelist")},
                    {"title": "Mijozlar", "icon": "group",
                     "link": reverse_lazy("admin:customers_customer_changelist")},
                    {"title": "Mahsulotlar", "icon": "chair",
                     "link": reverse_lazy("admin:products_product_changelist")},
                    {"title": "Mahsulot kategoriyalari", "icon": "category",
                     "link": reverse_lazy("admin:products_productcategory_changelist")},
                ],
            },
            {
                "title": "Ombor",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "Materiallar", "icon": "inventory_2",
                     "link": reverse_lazy("admin:inventory_material_changelist")},
                    {"title": "Material kategoriyalari", "icon": "category",
                     "link": reverse_lazy("admin:inventory_materialcategory_changelist")},
                    {"title": "Ombor harakatlari", "icon": "swap_vert",
                     "link": reverse_lazy("admin:inventory_stockmovement_changelist")},
                ],
            },
            {
                "title": "Moliya",
                "separator": True,
                "permission": is_owner,  # butun bo'lim faqat rahbarga
                "collapsible": True,
                "items": [
                    {"title": "To'lovlar", "icon": "payments",
                     "link": reverse_lazy("admin:finance_payment_changelist")},
                    {"title": "Chiqimlar", "icon": "receipt_long",
                     "link": reverse_lazy("admin:finance_expense_changelist")},
                    {"title": "Valyuta kurslari", "icon": "currency_exchange",
                     "link": reverse_lazy("admin:finance_exchangerate_changelist")},
                ],
            },
            {
                "title": "Hisobotlar",
                "separator": True,
                "permission": is_owner,
                "collapsible": True,
                "items": [
                    {"title": "Moliyaviy hisobot (Excel)", "icon": "download",
                     "link": reverse_lazy("reports:finance_export")},
                ],
            },
            {
                "title": "Tizim",
                "separator": True,
                "permission": is_owner,
                "collapsible": True,
                "items": [
                    {"title": "Foydalanuvchilar", "icon": "manage_accounts",
                     "link": reverse_lazy("admin:accounts_user_changelist")},
                ],
            },
        ],
    },
}

AUTH_USER_MODEL = "accounts.User"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env.str('DB_NAME'),
        'USER': env.str('DB_USER'),
        'PASSWORD': env.str('DB_PASSWORD'),
        'HOST': env.str('DB_HOST'),
        'PORT': env.int('DB_PORT'),

        # production optimizations
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

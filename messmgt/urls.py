"""
URL configuration for messmgt project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from core.views import (
    signup,
    google_login,
    register,
    otp_verify_placeholder,
    forgot_password_request,
    forgot_password_verify,
    forgot_password_reset,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/register/', register, name='account_register'),
    path('accounts/verify-otp/', otp_verify_placeholder, name='otp_verify_placeholder'),
    path('accounts/signup/', signup, name='account_signup'),
    path('accounts/google/login/', google_login, name='google_login'),
    path('accounts/forgot-password/', forgot_password_request, name='forgot_password_request'),
    path('accounts/forgot-password/verify/', forgot_password_verify, name='forgot_password_verify'),
    path('accounts/forgot-password/reset/', forgot_password_reset, name='forgot_password_reset'),
    path('accounts/', include('allauth.urls')),
    path('', include('core.urls')),   # 👈 core app ke urls include
]
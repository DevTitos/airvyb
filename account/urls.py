from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Template views
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('verify-email/<int:user_id>/', views.verify_email_view, name='verify_email'),
    path('password-reset/', views.password_reset_request_view, name='password_reset_request'),
    path('password-reset-confirm/<int:user_id>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('profile/', views.profile_view, name='profile'),
    #path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # AJAX endpoints
    path('ajax/register/', views.ajax_register, name='ajax_register'),
    path('ajax/verify-email/', views.ajax_verify_email, name='ajax_verify_email'),
    path('ajax/login/', views.ajax_login, name='ajax_login'),
    path('ajax/resend-verification/', views.ajax_resend_verification, name='ajax_resend_verification'),
    path('ajax/password-reset-request/', views.ajax_password_reset_request, name='ajax_password_reset_request'),
    path('ajax/password-reset-confirm/', views.ajax_password_reset_confirm, name='ajax_password_reset_confirm'),
    path('ajax/logout/', views.ajax_logout, name='ajax_logout'),
    path('ajax/get-profile/', views.ajax_get_profile, name='ajax_get_profile'),
    path('ajax/update-profile/', views.ajax_update_profile, name='ajax_update_profile'),
    path('ajax/change-password/', views.ajax_change_password, name='ajax_change_password'),
]
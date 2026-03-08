from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Portfolio
    path('dashboard/', views.dashboard, name='dashboard'),
    path('portfolio/', views.portfolio_detail, name='portfolio'),
    
    # Ventures
    path('ventures/', views.venture_list, name='venture_list'),
    path('ventures/<int:venture_id>/', views.venture_detail, name='venture_detail'),
    path('ventures/<int:venture_id>/invest/', views.process_investment, name='process_investment'),
    path('terms/', views.terms_of_service, name='terms_of_service'),
    path('investment-agreement/', views.investment_agreement, name='investment_agreement'),
    
    # Investments
    path('invest/<int:venture_id>/', views.invest, name='invest'),
    path('investments/<int:investment_id>/', views.investment_detail, name='investment_detail'),
    path('investments/success/<int:investment_id>/', views.investment_success, name='investment_success'),
    path('investments/<int:venture_id>/bulk/', views.bulk_investment, name='bulk_investment'),
    
    # Transactions
    path('transactions/', views.transaction_history, name='transactions'),
    path('payment/mpesa/deposit/', views.pay_mpesa, name='mpesa-pay'),
    #path('payment/mpesa/success/', views.depositSuccess, name='mpesa-success'),
    path('payment/withdraw/', views.withdraw_funds, name='withdraw'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    
    # AJAX Endpoints
    path('ajax/venture/<int:venture_id>/stats/', views.ajax_get_venture_stats, name='ajax_venture_stats'),
    path('ajax/calculate-investment/', views.ajax_calculate_investment, name='ajax_calculate_investment'),
    path('ajax/portfolio-summary/', views.ajax_get_portfolio_summary, name='ajax_portfolio_summary'),
    path('ajax/notifications/<int:notification_id>/read/', views.ajax_mark_notification_read, name='ajax_mark_notification_read'),
]
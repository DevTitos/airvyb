from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    # Main Dashboard
    path('finance/', views.finance_dashboard, name='dashboard'),
    
    # Transactions
    path('transactions/', views.transaction_history, name='transactions'),
    path('transactions/<int:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    
    # Deposits
    path('deposit/', views.deposit, name='deposit'),
    path('deposit/initiate/', views.initiate_deposit, name='initiate_deposit'),
    path('finance/deposit/status/<int:transaction_id>/', views.check_deposit_status, name='check_deposit_status'),
    path('payment/mpesa/success/', views.deposit_success_simple, name='mpesa_callback'),
    
    # Withdrawals
    path('withdrawal/', views.withdrawal, name='withdrawal'),
    path('withdrawal/process/', views.process_withdrawal, name='process_withdrawal'),
    
    # Loans
    path('loans/', views.loans, name='loans'),
    path('loans/apply/', views.apply_loan, name='apply_loan'),
    path('loans/<int:loan_id>/', views.loan_detail, name='loan_detail'),
    path('loans/<int:loan_id>/repay/', views.repay_loan, name='repay_loan'),
    path('loans/calculate/', views.calculate_loan, name='calculate_loan'),
    path('loans/eligibility/', views.get_loan_eligibility, name='loan_eligibility'),
    
    # Payment Methods
    path('payment-methods/', views.payment_methods, name='payment_methods'),
    path('payment-methods/add/', views.add_payment_method, name='add_payment_method'),
    path('payment-methods/<int:method_id>/default/', views.set_default_payment_method, name='set_default_payment_method'),
    path('payment-methods/<int:method_id>/delete/', views.delete_payment_method, name='delete_payment_method'),
    
    # API Endpoints
    path('api/wallet-balance/', views.get_wallet_balance, name='wallet_balance'),
]
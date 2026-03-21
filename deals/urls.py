from django.urls import path
from . import views

app_name = 'deals'

urlpatterns = [
    # ============================================
    # PUBLIC VIEWS
    # ============================================
    path('', views.deal_list, name='list'),
    path('deal/<slug:slug>/', views.deal_detail, name='detail'),
    
    # ============================================
    # MEMBER VIEWS
    # ============================================
    path('my-deals/', views.my_deals, name='my_deals'),
    path('opt-in/<int:deal_id>/', views.opt_in_deal, name='opt_in'),
    path('report/<int:report_id>/', views.deal_report, name='report'),
    path('nft-proof/<int:opt_in_id>/', views.nft_proof, name='nft_proof'),
    
    # ============================================
    # AML MANAGEMENT
    # ============================================
    path('aml/dashboard/', views.aml_dashboard, name='aml_dashboard'),
    path('aml/deal/create/', views.aml_create_deal, name='aml_create_deal'),
    path('aml/deal/<int:deal_id>/retry-nft/', views.aml_retry_nft, name='aml_retry_nft'),
    path('aml/debug-nft/<int:deal_id>/', views.debug_nft_status, name='debug_nft_status'),
    
    # ============================================
    # API ENDPOINTS (AJAX)
    # ============================================
    path('api/check-opt-in/<int:deal_id>/', views.api_check_opt_in, name='api_check_opt_in'),
    
]
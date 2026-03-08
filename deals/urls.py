from django.urls import path
from . import views

app_name = 'deals'

urlpatterns = [
    # Public views
    path('', views.deal_list, name='list'),
    path('deal/<slug:slug>/', views.deal_detail, name='detail'),
    
    # Member views
    path('my-deals/', views.my_deals, name='my_deals'),
    path('opt-in/<int:deal_id>/', views.opt_in_deal, name='opt_in'),
    path('report/<int:report_id>/', views.deal_report, name='report'),
    
    # AML management
    path('aml/dashboard/', views.aml_dashboard, name='aml_dashboard'),
]
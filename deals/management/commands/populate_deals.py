# deals/management/commands/populate_deals.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import timedelta
import random

from deals.models import (
    Deal, DealCategory, DealOptIn, DealRevenue, 
    DealCost, DealProfitDistribution, DealReport, DealUpdate
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate deals with sample data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing deals before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing deals...')
            Deal.objects.all().delete()
            DealCategory.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Deals cleared successfully'))

        self.stdout.write('Populating deals with sample data...')
        
        # Create categories if they don't exist
        categories = self.create_categories()
        
        # Get or create test users
        admin_user = self.get_or_create_admin_user()
        test_user = self.get_or_create_test_user()
        
        # Create sample deals
        deals = self.create_sample_deals(categories, admin_user)
        
        # Create opt-ins for deals
        self.create_opt_ins(deals, test_user, admin_user)
        
        # Create revenues and costs
        self.create_financial_data(deals)
        
        # Create reports and updates
        self.create_reports_and_updates(deals)
        
        self.stdout.write(self.style.SUCCESS('Successfully populated deals!'))

    def create_categories(self):
        """Create deal categories"""
        categories_data = [
            {
                'name': 'M-Pesa Outlet',
                'description': 'Investment in M-Pesa agent outlets with steady commission income',
                'icon': 'mobile-alt',
                'order': 1
            },
            {
                'name': 'Service Unit',
                'description': 'Service-based business units with recurring revenue',
                'icon': 'concierge-bell',
                'order': 2
            },
            {
                'name': 'Asset',
                'description': 'Physical assets that generate rental or appreciation income',
                'icon': 'building',
                'order': 3
            },
            {
                'name': 'Retail',
                'description': 'Retail outlets and shops with direct customer sales',
                'icon': 'store',
                'order': 4
            },
            {
                'name': 'Agriculture',
                'description': 'Agricultural projects including farming and processing',
                'icon': 'seedling',
                'order': 5
            },
            {
                'name': 'Real Estate',
                'description': 'Property investments for rental or development',
                'icon': 'home',
                'order': 6
            },
            {
                'name': 'Transport',
                'description': 'Transportation assets like vehicles or logistics',
                'icon': 'truck',
                'order': 7
            },
            {
                'name': 'Technology',
                'description': 'Tech startups and digital service platforms',
                'icon': 'laptop-code',
                'order': 8
            },
        ]
        
        categories = []
        for cat_data in categories_data:
            category, created = DealCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            categories.append(category)
            if created:
                self.stdout.write(f'  Created category: {category.name}')
        
        return categories

    def get_or_create_admin_user(self):
        """Get or create an admin user"""
        try:
            # Try to find an existing staff user
            admin = User.objects.filter(is_staff=True, is_superuser=True).first()
            if admin:
                self.stdout.write(f'  Using existing admin: {admin.email}')
                return admin
        except:
            pass
        
        # Create admin user using email as identifier
        admin_data = {
            'email': 'admin@airvyb.com',
            'first_name': 'Admin',
            'last_name': 'User',
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
            'is_verified': True,
        }
        
        admin, created = User.objects.get_or_create(
            email='admin@airvyb.com',
            defaults=admin_data
        )
        
        if created:
            admin.set_password('Admin123!')
            admin.save()
            self.stdout.write('  Created admin user: admin@airvyb.com / Admin123!')
        else:
            self.stdout.write('  Admin user already exists')
        
        return admin

    def get_or_create_test_user(self):
        """Get or create a test regular user"""
        try:
            # Try to find an existing non-staff user
            test_user = User.objects.filter(is_staff=False).first()
            if test_user:
                self.stdout.write(f'  Using existing test user: {test_user.email}')
                return test_user
        except:
            pass
        
        # Create test user using email as identifier
        test_data = {
            'email': 'investor@example.com',
            'first_name': 'Test',
            'last_name': 'Investor',
            'is_staff': False,
            'is_superuser': False,
            'is_active': True,
            'is_verified': True,
            'phone_number': '0712345678',
        }
        
        test_user, created = User.objects.get_or_create(
            email='investor@example.com',
            defaults=test_data
        )
        
        if created:
            test_user.set_password('Investor123!')
            test_user.save()
            self.stdout.write('  Created test user: investor@example.com / Investor123!')
        else:
            self.stdout.write('  Test user already exists')
        
        return test_user

    def create_sample_deals(self, categories, admin_user):
        """Create sample deals"""
        now = timezone.now()
        
        deals_data = [
            {
                'title': 'Nairobi CBD M-Pesa Outlet',
                'category': categories[0],
                'objective': 'Establish a high-volume M-Pesa agent outlet in Nairobi CBD serving 500+ customers daily',
                'description': 'This outlet will be located in a prime location in Nairobi CBD with high foot traffic. The outlet will offer M-Pesa services, bill payments, and money transfer services.',
                'expected_operations': 'Daily M-Pesa transactions, bill payments, money transfers. Target 500 transactions per day with average commission of Ksh 20 per transaction.',
                'opt_in_amount': 5000,
                'total_capital_required': 500000,
                'min_opt_in_members': 50,
                'max_opt_in_members': 100,
                'risk_level': 'low',
                'duration_months': 24,
                'management_fee_percent': 10,
                'performance_carry_percent': 20,
                'status': 'opt_in_open',
                'opt_in_start': now - timedelta(days=5),
                'opt_in_end': now + timedelta(days=25),
                'disclosed_at': now - timedelta(days=7),
            },
            {
                'title': 'Kiambu Road Service Station',
                'category': categories[1],
                'objective': 'Operate a full-service fuel station along Kiambu Road serving motorists',
                'description': 'Modern fuel station with 4 pumps, convenience store, and car wash services. Located along the busy Kiambu Road with high vehicle traffic.',
                'expected_operations': 'Fuel sales (diesel, petrol), lubricants, convenience store items, car wash services. Projected daily fuel sales of 5000 liters.',
                'opt_in_amount': 10000,
                'total_capital_required': 2000000,
                'min_opt_in_members': 100,
                'max_opt_in_members': 200,
                'risk_level': 'medium',
                'duration_months': 36,
                'management_fee_percent': 12,
                'performance_carry_percent': 20,
                'status': 'opt_in_open',
                'opt_in_start': now - timedelta(days=2),
                'opt_in_end': now + timedelta(days=28),
                'disclosed_at': now - timedelta(days=4),
            },
            {
                'title': 'Thika Rental Apartments',
                'category': categories[5],
                'objective': 'Develop 20 rental apartment units in Thika town',
                'description': 'Construction of 20 modern 2-bedroom apartment units with parking, security, and common amenities. Targeting middle-income tenants.',
                'expected_operations': 'Monthly rental income from 20 units at average Ksh 15,000 per unit. Projected annual rental income of Ksh 3.6M.',
                'opt_in_amount': 25000,
                'total_capital_required': 5000000,
                'min_opt_in_members': 100,
                'max_opt_in_members': 200,
                'risk_level': 'medium',
                'duration_months': 60,
                'management_fee_percent': 15,
                'performance_carry_percent': 25,
                'status': 'setup',
                'setup_start': now - timedelta(days=10),
                'disclosed_at': now - timedelta(days=20),
                'opt_in_start': now - timedelta(days=15),
                'opt_in_end': now - timedelta(days=1),
            },
            {
                'title': 'Machinos Green Farm',
                'category': categories[4],
                'objective': 'Large-scale avocado farming for export market',
                'description': '50-acre avocado farm in Machinos county growing Hass avocados for export to European markets. Includes irrigation system and packing house.',
                'expected_operations': 'Avocado harvesting, processing, and export. First harvest expected in year 3, with full production by year 5. Projected annual revenue of Ksh 10M at full production.',
                'opt_in_amount': 15000,
                'total_capital_required': 3000000,
                'min_opt_in_members': 100,
                'max_opt_in_members': 200,
                'risk_level': 'high',
                'duration_months': 84,
                'management_fee_percent': 12,
                'performance_carry_percent': 20,
                'status': 'active',
                'launched_at': now - timedelta(days=180),
                'disclosed_at': now - timedelta(days=200),
                'opt_in_start': now - timedelta(days=195),
                'opt_in_end': now - timedelta(days=165),
            },
            {
                'title': 'Nakuru Retail Plaza',
                'category': categories[3],
                'objective': 'Retail plaza with 10 shops in Nakuru town',
                'description': 'Modern retail plaza with 10 shop units, ample parking, and high visibility location. Targeting retail businesses and restaurants.',
                'expected_operations': 'Monthly rental income from 10 shops at average Ksh 25,000 per unit. Projected annual rental income of Ksh 3M.',
                'opt_in_amount': 20000,
                'total_capital_required': 4000000,
                'min_opt_in_members': 100,
                'max_opt_in_members': 200,
                'risk_level': 'medium',
                'duration_months': 48,
                'management_fee_percent': 12,
                'performance_carry_percent': 20,
                'status': 'active',
                'launched_at': now - timedelta(days=90),
                'disclosed_at': now - timedelta(days=110),
                'opt_in_start': now - timedelta(days=105),
                'opt_in_end': now - timedelta(days=75),
            },
            {
                'title': 'Kisumu Water Transport',
                'category': categories[6] if len(categories) > 6 else categories[1],
                'objective': 'Water transport services on Lake Victoria',
                'description': 'Two passenger boats providing transport services between Kisumu and surrounding islands. Includes ticketing system and safety equipment.',
                'expected_operations': 'Daily passenger transport services, cargo transport. Projected daily revenue of Ksh 50,000 from passenger and cargo services.',
                'opt_in_amount': 12000,
                'total_capital_required': 2400000,
                'min_opt_in_members': 100,
                'max_opt_in_members': 200,
                'risk_level': 'high',
                'duration_months': 36,
                'management_fee_percent': 12,
                'performance_carry_percent': 20,
                'status': 'monitoring',
                'launched_at': now - timedelta(days=60),
                'disclosed_at': now - timedelta(days=80),
                'opt_in_start': now - timedelta(days=75),
                'opt_in_end': now - timedelta(days=45),
            },
        ]
        
        created_deals = []
        for deal_data in deals_data:
            # Set default values
            deal_data['created_by'] = admin_user
            
            # Calculate total_opted_in and total_collected based on status
            if deal_data['status'] == 'opt_in_open':
                deal_data['total_opted_in'] = random.randint(20, 60)
            elif deal_data['status'] in ['setup', 'active', 'monitoring']:
                deal_data['total_opted_in'] = random.randint(80, deal_data['max_opt_in_members'])
            else:
                deal_data['total_opted_in'] = 0
                
            deal_data['total_collected'] = deal_data['total_opted_in'] * deal_data['opt_in_amount']
            
            # Check if deal already exists
            if not Deal.objects.filter(title=deal_data['title']).exists():
                deal = Deal.objects.create(**deal_data)
                created_deals.append(deal)
                self.stdout.write(f'  Created deal: {deal.title}')
            else:
                deal = Deal.objects.get(title=deal_data['title'])
                created_deals.append(deal)
                self.stdout.write(f'  Deal already exists: {deal.title}')
        
        return created_deals

    def create_opt_ins(self, deals, test_user, admin_user):
        """Create sample opt-ins for deals"""
        for deal in deals:
            # Create opt-in for test user
            if not DealOptIn.objects.filter(user=test_user, deal=deal).exists():
                DealOptIn.objects.create(
                    user=test_user,
                    deal=deal,
                    amount=deal.opt_in_amount,
                    status='confirmed' if deal.status in ['active', 'monitoring', 'setup'] else 'pending',
                    paid_at=timezone.now() if deal.status in ['active', 'monitoring', 'setup'] else None
                )
                self.stdout.write(f'  Created opt-in for {test_user.email} on {deal.title}')
            
            # Create opt-in for admin user (if different from test user)
            if admin_user.id != test_user.id and not DealOptIn.objects.filter(user=admin_user, deal=deal).exists():
                DealOptIn.objects.create(
                    user=admin_user,
                    deal=deal,
                    amount=deal.opt_in_amount,
                    status='confirmed',
                    paid_at=timezone.now()
                )
                self.stdout.write(f'  Created opt-in for {admin_user.email} on {deal.title}')

    def create_financial_data(self, deals):
        """Create sample revenue and cost data for active deals"""
        now = timezone.now()
        
        for deal in deals:
            if deal.status in ['active', 'monitoring']:
                # Create 3 months of revenue data
                for i in range(1, 4):
                    month_start = (now.replace(day=1) - timedelta(days=30*i)).date()
                    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    
                    # Calculate revenue (5-10% of capital per month)
                    revenue_amount = deal.total_capital_required * Decimal(str(random.uniform(0.05, 0.1)))
                    
                    # Create revenue record
                    DealRevenue.objects.get_or_create(
                        deal=deal,
                        period_start=month_start,
                        period_end=month_end,
                        defaults={
                            'amount': revenue_amount,
                            'description': f'Monthly revenue for {month_start.strftime("%B %Y")}'
                        }
                    )
                    
                    # Create costs (30-50% of revenue)
                    cost_amount = revenue_amount * Decimal(str(random.uniform(0.3, 0.5)))
                    DealCost.objects.get_or_create(
                        deal=deal,
                        period_start=month_start,
                        period_end=month_end,
                        cost_type=random.choice(['operating', 'staff', 'utilities', 'maintenance']),
                        defaults={
                            'amount': cost_amount,
                            'description': f'Operating costs for {month_start.strftime("%B %Y")}'
                        }
                    )
                    
                    self.stdout.write(f'  Created financial data for {deal.title} - {month_start.strftime("%B %Y")}')

    def create_reports_and_updates(self, deals):
        """Create sample reports and updates"""
        now = timezone.now()
        
        for deal in deals:
            if deal.status in ['active', 'monitoring']:
                # Create updates
                for i in range(1, 4):
                    update_date = now - timedelta(days=30*i)
                    DealUpdate.objects.get_or_create(
                        deal=deal,
                        title=f'Monthly Update {i}',
                        defaults={
                            'content': f'Deal progress update for month {i}. Operations running smoothly. Revenue targets being met.',
                            'is_important': i == 1,
                            'created_at': update_date
                        }
                    )
                
                # Create a report
                report_period = (now - timedelta(days=30)).date()
                DealReport.objects.get_or_create(
                    deal=deal,
                    period=report_period,
                    defaults={
                        'title': f'Monthly Report - {report_period.strftime("%B %Y")}',
                        'summary': 'The deal performed well this month with all targets met.',
                        'revenue_details': 'Total revenue of Ksh 250,000 from operations.',
                        'cost_details': 'Operating costs of Ksh 75,000 including staff and utilities.',
                        'aml_share': 25000,
                        'net_profit': 150000,
                        'status_update': 'Active - Performing well',
                        'next_steps': 'Continue operations and explore expansion opportunities.'
                    }
                )
                
                self.stdout.write(f'  Created reports and updates for {deal.title}')
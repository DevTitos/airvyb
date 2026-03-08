from django.db import migrations

def create_initial_categories(apps, schema_editor):
    DealCategory = apps.get_model('deals', 'DealCategory')
    
    categories = [
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
    
    for cat in categories:
        DealCategory.objects.get_or_create(
            name=cat['name'],
            defaults={
                'description': cat['description'],
                'icon': cat['icon'],
                'order': cat['order'],
                'is_active': True
            }
        )

def reverse_func(apps, schema_editor):
    """Reverse function - do nothing"""
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('deals', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_categories, reverse_func),
    ]
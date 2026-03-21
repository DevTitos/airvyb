from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction as db_transaction
from django.views.decorators.http import require_POST, require_GET
from decimal import Decimal
import json
import logging
import string
import random
import os

from .models import Deal, DealOptIn, DealCategory, DealReport, DealUpdate
from finance.models import Wallet, Transaction
from finance.hedera_consensus import hedera_consensus
from django.conf import settings

logger = logging.getLogger(__name__)

# ============================================
# HEDERA NFT UTILITIES
# ============================================

def create_hedera_nft_collection(deal, supply_key=None):
    """
    Create an NFT collection for a deal on Hedera
    Returns token_id if successful, None otherwise
    """
    try:
        from hiero_sdk_python import (
            Client, Network, AccountId, PrivateKey, TokenId,
            TokenCreateTransaction, TokenType, SupplyType
        )
        from cryptography.fernet import Fernet
        import json
        import os
        import hashlib
        
        # Initialize encryption cipher
        encryption_key = os.getenv('HEDERA_ENCRYPTION_KEY')
        if not encryption_key:
            logger.error("HEDERA_ENCRYPTION_KEY not found in environment")
            return None
        
        cipher = Fernet(encryption_key.encode())
        
        # Initialize client
        network = Network(network=os.getenv('HEDERA_NETWORK', 'testnet'))
        client = Client(network)
        operator_id = AccountId.from_string(os.getenv('OPERATOR_ID'))
        operator_key = PrivateKey.from_string_ed25519(os.getenv('OPERATOR_KEY'))
        client.set_operator(operator_id, operator_key)
        
        # Generate supply key if not provided
        if not supply_key:
            supply_key = PrivateKey.generate()
            supply_key_public = supply_key.public_key()
            # Store encrypted supply key in deal
            deal.hedera_supply_key_encrypted = cipher.encrypt(
                supply_key.to_string().encode()
            ).decode()
            deal.save(update_fields=['hedera_supply_key_encrypted'])
        else:
            supply_key_public = supply_key.public_key()
        
        # Create token name and symbol (limited to 100 chars)
        token_name = f"AVB{deal.reference[:6]}"
        token_symbol = f"AVB{deal.reference[:3]}"
        
        # Create a short metadata string (keep under 100 bytes)
        metadata_str = f"{deal.title[:20]}|{deal.reference[:6]}|{deal.opt_in_amount}"
        
        # Ensure metadata doesn't exceed 100 bytes
        if len(metadata_str.encode('utf-8')) > 100:
            # Truncate to 95 bytes to be safe
            max_bytes = 95
            while len(metadata_str.encode('utf-8')) > max_bytes and len(metadata_str) > 10:
                metadata_str = metadata_str[:-1]
        
        logger.info(f"Creating NFT collection with metadata: {metadata_str}")
        
        # Create NFT collection
        transaction = (
            TokenCreateTransaction()
            .set_token_name(token_name)
            .set_token_symbol(token_symbol)
            .set_token_type(TokenType.NON_FUNGIBLE_UNIQUE)
            .set_supply_type(SupplyType.FINITE)
            .set_max_supply(deal.max_opt_in_members or 1000)
            .set_treasury_account_id(operator_id)
            .set_admin_key(operator_key.public_key())
            .set_supply_key(supply_key_public)
            .set_metadata(metadata_str.encode())
            .freeze_with(client)
        )
        
        # Sign with operator key
        transaction.sign(operator_key)
        
        # Sign with supply key if it's a new key
        if supply_key:
            transaction.sign(supply_key)
        
        # Execute transaction
        receipt = transaction.execute(client)
        
        # Get token ID from receipt
        if hasattr(receipt, 'token_id') and receipt.token_id:
            token_id_obj = receipt.token_id
            token_id = str(token_id_obj)
            
            logger.info(f"NFT collection created with token ID: {token_id}")
            
            # Store token ID in deal
            deal.hedera_token_id = token_id
            deal.save(update_fields=['hedera_token_id'])
            
            # Store the actual metadata in deal model for reference
            deal.hedera_metadata_uri = f"https://airvyb.com/deals/{deal.slug}/metadata"
            deal.save(update_fields=['hedera_metadata_uri'])
            
            # Create a topic for deal updates (metadata can be stored here)
            from finance.hedera_consensus import hedera_consensus
            full_metadata = {
                "deal_id": deal.id,
                "deal_reference": deal.reference,
                "title": deal.title,
                "objective": deal.objective[:200],
                "description": deal.description[:200],
                "opt_in_amount": str(deal.opt_in_amount),
                "risk_level": deal.risk_level,
                "duration_months": deal.duration_months,
                "total_capital_required": str(deal.total_capital_required),
                "min_opt_in_members": deal.min_opt_in_members,
                "max_opt_in_members": deal.max_opt_in_members,
                "created_at": deal.created_at.isoformat(),
                "type": "deal_metadata"
            }
            
            topic_result = hedera_consensus.submit_message(full_metadata)
            
            if topic_result.get('status') == 'success':
                deal.hedera_topic_id = topic_result.get('topic')
                deal.save(update_fields=['hedera_topic_id'])
            
            return token_id
        else:
            logger.error("No token ID returned in receipt")
            return None
            
    except Exception as e:
        logger.error(f"Failed to create NFT collection for deal {deal.id}: {str(e)}", exc_info=True)
        return None


def mint_opt_in_nft(opt_in):
    """
    Mint an NFT for a confirmed opt-in
    Returns serial number if successful, None otherwise
    """
    try:
        from hiero_sdk_python import (
            Client, Network, AccountId, PrivateKey, TokenId,
            TokenMintTransaction, ResponseCode
        )
        from cryptography.fernet import Fernet
        import os
        
        deal = opt_in.deal
        
        # Check if deal has NFT collection
        if not deal.hedera_token_id:
            logger.error(f"Deal {deal.id} has no NFT collection")
            return None
        
        # Initialize encryption cipher
        encryption_key = os.getenv('HEDERA_ENCRYPTION_KEY')
        if not encryption_key:
            logger.error("HEDERA_ENCRYPTION_KEY not found in environment")
            return None
        
        cipher = Fernet(encryption_key.encode())
        
        # Initialize client
        network = Network(network=os.getenv('HEDERA_NETWORK', 'testnet'))
        client = Client(network)
        operator_id = AccountId.from_string(os.getenv('OPERATOR_ID'))
        operator_key = PrivateKey.from_string_ed25519(os.getenv('OPERATOR_KEY'))
        client.set_operator(operator_id, operator_key)
        
        # Convert token ID string to TokenId object
        try:
            token_id_obj = TokenId.from_string(deal.hedera_token_id)
            logger.info(f"Token ID converted: {token_id_obj}")
        except Exception as e:
            logger.error(f"Failed to convert token ID: {str(e)}")
            return None
        
        # Decrypt supply key
        supply_key = None
        if deal.hedera_supply_key_encrypted:
            try:
                supply_key_str = cipher.decrypt(
                    deal.hedera_supply_key_encrypted.encode()
                ).decode()
                supply_key = PrivateKey.from_string_ed25519(supply_key_str)
                logger.info(f"Supply key decrypted successfully for deal {deal.id}")
            except Exception as e:
                logger.error(f"Failed to decrypt supply key: {str(e)}")
                return None
        
        # Create minimal metadata (under 100 bytes)
        metadata_str = f"{opt_in.reference[:8]}|{opt_in.user.id}|{opt_in.amount}|{deal.reference[:8]}"
        
        # Ensure metadata doesn't exceed 100 bytes
        if len(metadata_str.encode('utf-8')) > 100:
            max_bytes = 95
            while len(metadata_str.encode('utf-8')) > max_bytes and len(metadata_str) > 10:
                metadata_str = metadata_str[:-1]
        
        logger.info(f"Minting NFT with metadata: {metadata_str} (length: {len(metadata_str.encode('utf-8'))} bytes)")
        
        # Build transaction
        transaction = (
            TokenMintTransaction()
            .set_token_id(token_id_obj)
            .set_metadata([metadata_str.encode()])
            .freeze_with(client)
        )
        
        # Sign with operator key
        transaction.sign(operator_key)
        
        # Sign with supply key if available
        if supply_key:
            transaction.sign(supply_key)
            logger.info("Transaction signed with supply key")
        
        # Execute transaction
        logger.info("Executing NFT mint transaction...")
        receipt = transaction.execute(client)
        
        # Log the full receipt for debugging
        logger.info(f"Receipt received: {receipt}")
        logger.info(f"Receipt attributes: {dir(receipt)}")
        
        # Check transaction status
        if hasattr(receipt, 'status'):
            logger.info(f"Transaction status: {receipt.status}")
            if receipt.status != ResponseCode.SUCCESS:
                status_name = ResponseCode(receipt.status).name
                logger.error(f"Transaction failed with status: {status_name}")
                return None
        
        # Try to get serial numbers - different ways to access
        serial_number = None
        
        # Method 1: Check for serials attribute
        if hasattr(receipt, 'serials'):
            logger.info(f"Receipt has serials: {receipt.serials}")
            if receipt.serials and len(receipt.serials) > 0:
                serial_number = receipt.serials[0]
        
        # Method 2: Check for serials in receipt object
        elif hasattr(receipt, 'serial_numbers'):
            logger.info(f"Receipt has serial_numbers: {receipt.serial_numbers}")
            if receipt.serial_numbers and len(receipt.serial_numbers) > 0:
                serial_number = receipt.serial_numbers[0]
        
        # Method 3: Check if receipt itself is a list of serials
        elif isinstance(receipt, list) and len(receipt) > 0:
            serial_number = receipt[0]
        
        # Method 4: Check receipt's topic_sequence_number (sometimes used for NFT serials)
        elif hasattr(receipt, 'topic_sequence_number'):
            logger.info(f"Receipt has topic_sequence_number: {receipt.topic_sequence_number}")
            serial_number = receipt.topic_sequence_number
        
        # If we have a serial number, store it
        if serial_number:
            nft_id = f"{deal.hedera_token_id}/{serial_number}"
            
            # Store NFT info in opt-in
            opt_in.hedera_serial_number = serial_number
            opt_in.hedera_nft_id = nft_id
            opt_in.hedera_message_id = str(receipt.transaction_id) if hasattr(receipt, 'transaction_id') else str(receipt)
            opt_in.save(update_fields=['hedera_serial_number', 'hedera_nft_id', 'hedera_message_id'])
            
            # Log on HCS
            from finance.hedera_consensus import hedera_consensus
            full_metadata = {
                "type": "nft_minted",
                "opt_in_id": opt_in.id,
                "opt_in_reference": opt_in.reference,
                "nft_id": nft_id,
                "serial": serial_number,
                "user_id": opt_in.user.id,
                "user_email": opt_in.user.email,
                "amount": str(opt_in.amount),
                "opted_in_at": opt_in.created_at.isoformat(),
                "deal_id": deal.id,
                "deal_reference": deal.reference,
                "deal_title": deal.title
            }
            
            hedera_consensus.submit_message(full_metadata, topic_id=deal.hedera_topic_id)
            
            logger.info(f"NFT minted successfully for opt-in {opt_in.id} with serial: {serial_number}")
            return serial_number
        else:
            logger.error(f"No serial number found in receipt for opt-in {opt_in.id}")
            logger.error(f"Full receipt: {receipt}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to mint NFT for opt-in {opt_in.id}: {str(e)}", exc_info=True)
        return None
    

# ============================================
# UTILITY FUNCTIONS
# ============================================

def id_generator(size=12, chars=string.ascii_uppercase + string.digits):
    """Generate random reference ID"""
    return ''.join(random.choice(chars) for _ in range(size))

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================
# DEAL LISTING
# ============================================

@require_GET
def deal_list(request):
    """List all available deals"""
    category = request.GET.get('category')
    status = request.GET.get('status', 'opt_in_open')
    
    deals = Deal.objects.all()
    
    if category:
        deals = deals.filter(category_id=category)
    
    if status:
        deals = deals.filter(status=status)
    
    # Get opted-in deals for current user
    user_opt_in_deal_ids = []
    user_opt_ins = {}
    
    if request.user.is_authenticated:
        user_opt_ins = {
            opt_in.deal_id: opt_in 
            for opt_in in DealOptIn.objects.filter(
                user=request.user
            ).select_related('deal')
        }
        user_opt_in_deal_ids = list(user_opt_ins.keys())
    
    context = {
        'deals': deals,
        'categories': DealCategory.objects.filter(is_active=True),
        'user_opt_in_deal_ids': user_opt_in_deal_ids,
        'user_opt_ins': user_opt_ins,
        'current_category': category,
        'current_status': status,
    }
    
    return render(request, 'deals/deal_list.html', context)


# ============================================
# DEAL DETAIL
# ============================================

@require_GET
def deal_detail(request, slug):
    """Show deal details"""
    deal = get_object_or_404(Deal, slug=slug)
    
    # Check if user has opted in
    user_opt_in = None
    if request.user.is_authenticated:
        try:
            user_opt_in = DealOptIn.objects.get(
                user=request.user,
                deal=deal
            )
        except DealOptIn.DoesNotExist:
            pass
    
    # Get recent reports
    reports = deal.reports.all()[:3]
    
    # Get updates
    updates = deal.updates.all()[:5]
    
    context = {
        'deal': deal,
        'user_opt_in': user_opt_in,
        'reports': reports,
        'updates': updates,
        'can_opt_in': (
            deal.is_opt_in_open and
            not user_opt_in and
            (deal.available_slots is None or deal.available_slots > 0)
        ),
    }
    
    return render(request, 'deals/deal_detail.html', context)


# ============================================
# OPT-IN TO DEAL
# ============================================

# deals/views.py - Updated opt_in_deal function

@login_required
@require_POST
def opt_in_deal(request, deal_id):
    """Member opts in to a deal - NFT will be minted automatically"""
    deal = get_object_or_404(Deal, id=deal_id)
    
    # Check if opt-in is open
    if not deal.is_opt_in_open:
        messages.error(request, 'Opt-in period for this deal is closed.')
        return redirect('deals:detail', slug=deal.slug)
    
    # Check if user already opted in
    if DealOptIn.objects.filter(user=request.user, deal=deal).exists():
        messages.warning(request, 'You have already opted in to this deal.')
        return redirect('deals:detail', slug=deal.slug)
    
    # Check available slots
    if deal.available_slots is not None and deal.available_slots <= 0:
        messages.error(request, 'No available slots for this deal.')
        return redirect('deals:detail', slug=deal.slug)
    
    # Check Wallet Balance
    try:
        wallet = Wallet.objects.get(user=request.user)
    except Wallet.DoesNotExist:
        messages.error(request, 'You need to create a wallet first.')
        return redirect('finance:dashboard')
    
    if wallet.balance < deal.opt_in_amount:
        messages.error(request, f'Insufficient funds. Please add funds to your wallet and try again.')
        return redirect('deals:detail', slug=deal.slug)
    
    try:
        with db_transaction.atomic():
            # Get balance before
            balance_before = wallet.balance
            
            # Deduct payment from wallet
            wallet.balance -= deal.opt_in_amount
            wallet.save()
            
            # Create transaction record
            reference = f"OPTIN-{timezone.now().strftime('%Y%m%d%H%M%S')}-{request.user.id}-{id_generator(6)}"
            transaction = Transaction.objects.create(
                user=request.user,
                transaction_type='investment',
                payment_method='wallet',
                reference=reference,
                amount=deal.opt_in_amount,
                fee=0,
                net_amount=deal.opt_in_amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                description=f"Opt-in to deal: {deal.title}",
                status='completed',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                initiated_at=timezone.now(),
                metadata={
                    'deal_id': deal.id,
                    'deal_reference': deal.reference,
                    'deal_title': deal.title
                }
            )
            
            # Create opt-in record
            opt_in = DealOptIn.objects.create(
                user=request.user,
                deal=deal,
                transaction=transaction,
                amount=deal.opt_in_amount,
                status='confirmed',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Update deal stats
            deal.total_opted_in += 1
            deal.total_collected += deal.opt_in_amount
            deal.save()
            
            # Submit to Hedera Consensus Service
            try:
                from finance.hedera_consensus import hedera_consensus
                hedera_data = {
                    'type': 'deal_opt_in',
                    'opt_in_id': opt_in.id,
                    'reference': opt_in.reference,
                    'user_id': request.user.id,
                    'user_email': request.user.email,
                    'deal_id': deal.id,
                    'deal_reference': deal.reference,
                    'amount': float(deal.opt_in_amount),
                    'timestamp': timezone.now().isoformat()
                }
                hedera_consensus.submit_message(hedera_data, topic_id=deal.hedera_topic_id)
            except Exception as e:
                logger.error(f"HCS submission failed: {str(e)}")
            
            # ============================================
            # MINT NFT FOR THE OPT-IN
            # ============================================
            nft_minted = False
            if deal.hedera_token_id:
                try:
                    logger.info(f"Starting NFT minting for opt-in {opt_in.id}")
                    serial = mint_opt_in_nft(opt_in)
                    if serial:
                        nft_minted = True
                        logger.info(f"NFT minted successfully for opt-in {opt_in.id} with serial: {serial}")
                        messages.success(
                            request,
                            f'Successfully opted in to {deal.title}! Your NFT proof has been minted with serial #{serial}.'
                        )
                    else:
                        logger.error(f"Failed to mint NFT for opt-in {opt_in.id}")
                        messages.warning(
                            request,
                            f'Successfully opted in to {deal.title}, but NFT minting failed. Our team will resolve this shortly.'
                        )
                except Exception as e:
                    logger.error(f"Error minting NFT for opt-in {opt_in.id}: {str(e)}", exc_info=True)
                    messages.warning(
                        request,
                        f'Successfully opted in to {deal.title}, but NFT minting encountered an issue. Please check back later.'
                    )
            else:
                logger.warning(f"No NFT collection found for deal {deal.id}")
                messages.success(
                    request,
                    f'Successfully opted in to {deal.title}!'
                )
            
            return redirect('deals:detail', slug=deal.slug)
    
    except Exception as e:
        logger.error(f"Opt-in error: {str(e)}", exc_info=True)
        messages.error(request, 'An error occurred. Please try again.')
        return redirect('deals:detail', slug=deal.slug)

# ============================================
# MY DEALS (USER'S OPT-INS)
# ============================================

@login_required
@require_GET
def my_deals(request):
    """Show deals the user has opted into"""
    opt_ins = DealOptIn.objects.filter(
        user=request.user,
        status='confirmed'
    ).select_related('deal', 'deal__category').order_by('-created_at')
    
    context = {
        'opt_ins': opt_ins,
    }
    
    return render(request, 'deals/my_deals.html', context)


# ============================================
# NFT PROOF VIEW
# ============================================

@login_required
@require_GET
def nft_proof(request, opt_in_id):
    """View NFT proof for an opt-in"""
    opt_in = get_object_or_404(
        DealOptIn, 
        id=opt_in_id, 
        user=request.user,
        status='confirmed'
    )
    
    context = {
        'opt_in': opt_in,
        'nft_exists': bool(opt_in.hedera_nft_id),
    }
    
    return render(request, 'deals/nft_proof.html', context)


# ============================================
# DEAL REPORT VIEW
# ============================================

@login_required
@require_GET
def deal_report(request, report_id):
    """View a specific deal report"""
    report = get_object_or_404(DealReport, id=report_id)
    
    # Check if user is opted in to this deal
    if not DealOptIn.objects.filter(
        user=request.user,
        deal=report.deal,
        status='confirmed'
    ).exists():
        messages.error(request, 'You must opt in to this deal to view reports.')
        return redirect('deals:detail', slug=report.deal.slug)
    
    context = {
        'report': report,
    }
    
    return render(request, 'deals/deal_report.html', context)


# ============================================
# DEAL DASHBOARD (AML Management)
# ============================================

@login_required
def aml_dashboard(request):
    """Dashboard for AML to manage deals"""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('deals:list')
    
    deals = Deal.objects.all().order_by('-created_at')
    
    stats = {
        'total_deals': deals.count(),
        'active_deals': deals.filter(status='active').count(),
        'opt_in_open': deals.filter(status='opt_in_open').count(),
        'total_opted_in': sum(deal.total_opted_in for deal in deals),
        'total_collected': sum(deal.total_collected for deal in deals),
    }
    
    context = {
        'deals': deals,
        'stats': stats,
    }
    
    return render(request, 'deals/aml_dashboard.html', context)


# ============================================
# CREATE DEAL (AML)
# ============================================

@login_required
def aml_create_deal(request):
    """Create a new deal with NFT collection"""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('deals:list')
    
    if request.method == 'POST':
        try:
            with db_transaction.atomic():
                # Create deal
                deal = Deal.objects.create(
                    title=request.POST.get('title'),
                    category_id=request.POST.get('category'),
                    objective=request.POST.get('objective'),
                    description=request.POST.get('description'),
                    opt_in_amount=Decimal(request.POST.get('opt_in_amount')),
                    total_capital_required=Decimal(request.POST.get('total_capital_required')),
                    min_opt_in_members=int(request.POST.get('min_opt_in_members', 1)),
                    max_opt_in_members=request.POST.get('max_opt_in_members') or None,
                    expected_operations=request.POST.get('expected_operations'),
                    risk_level=request.POST.get('risk_level', 'medium'),
                    duration_months=int(request.POST.get('duration_months')),
                    management_fee_percent=Decimal(request.POST.get('management_fee_percent', 10)),
                    performance_carry_percent=Decimal(request.POST.get('performance_carry_percent', 20)),
                    opt_in_start=request.POST.get('opt_in_start'),
                    opt_in_end=request.POST.get('opt_in_end'),
                    status='sourcing',
                    created_by=request.user
                )
                
                # Create Hedera NFT collection
                token_id = create_hedera_nft_collection(deal)
                
                if token_id:
                    deal.hedera_token_id = token_id
                    deal.save()
                    
                    messages.success(
                        request, 
                        f'Deal created successfully! NFT Collection ID: {token_id}'
                    )
                else:
                    messages.warning(
                        request,
                        'Deal created but NFT collection creation failed. You can retry later.'
                    )
                
                return redirect('deals:aml_dashboard')
                
        except Exception as e:
            logger.error(f"Deal creation error: {str(e)}", exc_info=True)
            messages.error(request, f'Error creating deal: {str(e)}')
            return redirect('deals:aml_create_deal')
    
    # GET request - show form
    categories = DealCategory.objects.filter(is_active=True)
    context = {
        'categories': categories,
    }
    return render(request, 'deals/aml_create_deal.html', context)


# ============================================
# RETRY NFT CREATION
# ============================================

@login_required
def aml_retry_nft(request, deal_id):
    """Retry creating NFT collection for a deal"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    deal = get_object_or_404(Deal, id=deal_id)
    
    if deal.hedera_token_id:
        return JsonResponse({'error': 'NFT collection already exists'}, status=400)
    
    try:
        token_id = create_hedera_nft_collection(deal)
        
        if token_id:
            deal.hedera_token_id = token_id
            deal.save(update_fields=['hedera_token_id'])
            return JsonResponse({
                'success': True,
                'token_id': token_id,
                'message': 'NFT collection created successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to create NFT collection. Check logs for details.'
            }, status=500)
    except Exception as e:
        logger.error(f"Error in retry NFT: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# API: CHECK OPT-IN STATUS
# ============================================

@login_required
@require_GET
def api_check_opt_in(request, deal_id):
    """API endpoint to check if user is opted in"""
    deal = get_object_or_404(Deal, id=deal_id)
    
    try:
        opt_in = DealOptIn.objects.get(
            user=request.user,
            deal=deal,
            status='confirmed'
        )
        return JsonResponse({
            'opted_in': True,
            'opt_in_id': opt_in.id,
            'nft_id': opt_in.hedera_nft_id,
            'has_nft': bool(opt_in.hedera_nft_id)
        })
    except DealOptIn.DoesNotExist:
        return JsonResponse({'opted_in': False})
    



##########################################
############DEBUG VIEWS###################

@login_required
def debug_nft_status(request, deal_id):
    """Debug endpoint to check NFT collection status"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    deal = get_object_or_404(Deal, id=deal_id)
    
    try:
        from hiero_sdk_python import (
            Client, Network, AccountId, PrivateKey, TokenId,
            TokenInfoQuery
        )
        import os
        
        # Initialize client
        network = Network(network=os.getenv('HEDERA_NETWORK', 'testnet'))
        client = Client(network)
        operator_id = AccountId.from_string(os.getenv('OPERATOR_ID'))
        operator_key = PrivateKey.from_string_ed25519(os.getenv('OPERATOR_KEY'))
        client.set_operator(operator_id, operator_key)
        
        # Convert token ID
        token_id = TokenId.from_string(deal.hedera_token_id)
        
        # Query token info
        query = TokenInfoQuery().set_token_id(token_id)
        token_info = query.execute(client)
        
        return JsonResponse({
            'success': True,
            'token_id': deal.hedera_token_id,
            'token_name': getattr(token_info, 'name', 'N/A'),
            'token_symbol': getattr(token_info, 'symbol', 'N/A'),
            'total_supply': getattr(token_info, 'total_supply', 'N/A'),
            'supply_type': str(getattr(token_info, 'supply_type', 'N/A')),
            'has_supply_key': hasattr(token_info, 'supply_key') and token_info.supply_key is not None
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
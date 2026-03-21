# deals/management/commands/retry_failed_nfts.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from deals.models import DealOptIn
from deals.views import mint_opt_in_nft
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Retry NFT minting for opt-ins that are confirmed but have no NFT'

    def handle(self, *args, **options):
        # Find opt-ins that are confirmed but don't have NFTs
        failed_opt_ins = DealOptIn.objects.filter(
            status='confirmed',
            hedera_nft_id__isnull=True
        )
        
        self.stdout.write(f"Found {failed_opt_ins.count()} opt-ins without NFTs")
        
        for opt_in in failed_opt_ins:
            self.stdout.write(f"Retrying NFT mint for opt-in {opt_in.id}...")
            
            try:
                serial = mint_opt_in_nft(opt_in)
                if serial:
                    self.stdout.write(self.style.SUCCESS(
                        f"Successfully minted NFT for opt-in {opt_in.id} with serial {serial}"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to mint NFT for opt-in {opt_in.id}"
                    ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Error minting NFT for opt-in {opt_in.id}: {str(e)}"
                ))
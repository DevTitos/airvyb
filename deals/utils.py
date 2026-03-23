# deals/utils.py
import os
import uuid
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
import qrcode
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class NFTImageGenerator:
    """Generate unique NFT images for deal participation proofs"""
    
    def __init__(self):
        self.width = 800
        self.height = 800
        self.colors = {
            'primary': '#ff006e',
            'secondary': '#8338ec',
            'accent': '#3a86ff',
            'gold': '#ffbe0b',
            'green': '#00c853',
            'dark': '#1a1a2e',
            'light': '#ffffff'
        }
    
    def generate_opt_in_nft(self, opt_in, deal):
        """
        Generate a unique NFT image for a deal opt-in
        Returns: ContentFile object with the image
        """
        try:
            # Create a new image with gradient background
            img = Image.new('RGB', (self.width, self.height), color='#0f0f1a')
            draw = ImageDraw.Draw(img)
            
            # Draw gradient background (simulated with multiple layers)
            for i in range(self.height):
                color_value = int(20 + (i / self.height) * 60)
                draw.rectangle([0, i, self.width, i+1], fill=(color_value, color_value, color_value+30))
            
            # Draw decorative circles
            draw.ellipse([-100, -100, 300, 300], fill=(255, 0, 110, 30), outline=None)
            draw.ellipse([self.width-200, self.height-200, self.width+100, self.height+100], 
                        fill=(58, 134, 255, 30), outline=None)
            
            # Draw border
            border_width = 4
            for i in range(border_width):
                draw.rectangle([i, i, self.width-i-1, self.height-i-1], 
                             outline=(255, 215, 0), width=1)
            
            # Load fonts (use default if custom fonts not available)
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 48)
                subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 28)
                small_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 20)
            except:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Draw main title
            title = f"AIRVYB INVEST"
            bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - title_width//2, 80), title, fill=(255, 215, 0), font=title_font)
            
            # Draw deal title
            deal_title = deal.title[:30]
            if len(deal.title) > 30:
                deal_title += "..."
            bbox = draw.textbbox((0, 0), deal_title, font=subtitle_font)
            title_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - title_width//2, 160), deal_title, fill=(255, 255, 255), font=subtitle_font)
            
            # Draw NFT badge
            badge_y = 260
            badge_text = "PROOF OF PARTICIPATION"
            bbox = draw.textbbox((0, 0), badge_text, font=small_font)
            badge_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - badge_width//2, badge_y), badge_text, fill=(0, 200, 83), font=small_font)
            
            # Draw participant details box
            box_y = 320
            box_height = 280
            draw.rectangle([100, box_y, self.width-100, box_y+box_height], 
                          fill=(20, 20, 40, 180), outline=(255, 215, 0), width=2)
            
            # Draw participant info
            y_offset = box_y + 40
            info_lines = [
                f"Opt-In ID: {opt_in.reference[:12]}...",
                f"Amount: KES {opt_in.amount:,.0f}",
                f"Date: {opt_in.created_at.strftime('%d %b %Y')}",
                f"Serial: #{opt_in.hedera_serial_number if opt_in.hedera_serial_number else 'Minting...'}",
                f"Network: Hedera Testnet"
            ]
            
            for line in info_lines:
                bbox = draw.textbbox((0, 0), line, font=small_font)
                line_width = bbox[2] - bbox[0]
                draw.text((self.width//2 - line_width//2, y_offset), line, fill=(255, 255, 255), font=small_font)
                y_offset += 45
            
            # Generate QR code with NFT ID
            nft_id = f"https://hashscan.io/testnet/token/{opt_in.hedera_nft_id}" if opt_in.hedera_nft_id else f"https://airvyb.co.ke/deals/{deal.slug}/proof/{opt_in.id}"
            qr = qrcode.QRCode(box_size=5, border=1)
            qr.add_data(nft_id)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="#ff006e", back_color="white")
            qr_img = qr_img.resize((120, 120))
            
            # Paste QR code
            img.paste(qr_img, (self.width-180, self.height-160))
            
            # Draw footer
            footer_y = self.height - 50
            footer_text = "Verified on Hedera Consensus Service"
            bbox = draw.textbbox((0, 0), footer_text, font=small_font)
            footer_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - footer_width//2, footer_y), footer_text, fill=(100, 100, 150), font=small_font)
            
            # Add Hedera logo text
            draw.text((40, self.height-45), "⚡ HEDERA", fill=(0, 200, 83), font=small_font)
            
            # Save to BytesIO
            buffer = BytesIO()
            img.save(buffer, format='PNG', quality=95)
            buffer.seek(0)
            
            # Create filename
            filename = f"nft_{opt_in.reference}_{uuid.uuid4().hex[:8]}.png"
            
            return ContentFile(buffer.getvalue(), name=filename)
            
        except Exception as e:
            logger.error(f"Failed to generate NFT image for opt-in {opt_in.id}: {str(e)}")
            return None

    def generate_deal_collection_image(self, deal):
        """
        Generate a cover image for the NFT collection
        """
        try:
            img = Image.new('RGB', (self.width, self.height), color='#0f0f1a')
            draw = ImageDraw.Draw(img)
            
            # Gradient background
            for i in range(self.height):
                color_value = int(30 + (i / self.height) * 80)
                draw.rectangle([0, i, self.width, i+1], fill=(color_value, color_value, color_value+40))
            
            # Decorative elements
            draw.ellipse([-150, -150, 250, 250], fill=(255, 0, 110, 50), outline=None)
            draw.ellipse([self.width-200, self.height-200, self.width+150, self.height+150], 
                        fill=(58, 134, 255, 50), outline=None)
            
            # Border
            for i in range(4):
                draw.rectangle([i, i, self.width-i-1, self.height-i-1], outline=(255, 215, 0), width=1)
            
            # Load fonts
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 56)
                subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 32)
            except:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
            
            # Draw title
            title = "AIRVYB DEAL"
            bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - title_width//2, 250), title, fill=(255, 215, 0), font=title_font)
            
            # Draw deal name
            deal_name = deal.title[:25]
            if len(deal.title) > 25:
                deal_name += "..."
            bbox = draw.textbbox((0, 0), deal_name, font=subtitle_font)
            name_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - name_width//2, 350), deal_name, fill=(255, 255, 255), font=subtitle_font)
            
            # Draw info
            info_y = 480
            info_text = f"Opt-In: KES {deal.opt_in_amount:,.0f} | Duration: {deal.duration_months} months"
            bbox = draw.textbbox((0, 0), info_text, font=subtitle_font)
            info_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - info_width//2, info_y), info_text, fill=(0, 200, 83), font=subtitle_font)
            
            # Footer
            footer_text = "NFT Collection | Hedera Token Service"
            bbox = draw.textbbox((0, 0), footer_text, font=subtitle_font)
            footer_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - footer_width//2, self.height-80), footer_text, fill=(100, 100, 150), font=subtitle_font)
            
            buffer = BytesIO()
            img.save(buffer, format='PNG', quality=95)
            buffer.seek(0)
            
            filename = f"deal_collection_{deal.reference}_{uuid.uuid4().hex[:8]}.png"
            return ContentFile(buffer.getvalue(), name=filename)
            
        except Exception as e:
            logger.error(f"Failed to generate collection image for deal {deal.id}: {str(e)}")
            return None
# Airvyb - Community Deal Participation Platform

[![Hedera](https://img.shields.io/badge/Built%20on-Hedera-00c853?style=for-the-badge&logo=hedera&logoColor=white)](https://hedera.com)
[![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Hedera Hackathon](https://img.shields.io/badge/Hedera-Hello%20Future%20Apex%202026-ff0066?style=for-the-badge)](https://hellofuturehackathon.dev/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live-Demo-00c853?style=for-the-badge)](https://airvyb.co.ke)

> **Every participation is verifiable. Every transaction is immortal. Every member has proof.**

---

## 📸 Screenshots

<div align="center">
  <img src="media/1.png" alt="Fianace Dashboard" width="75%">
  <img src="media/2.png" alt="Transactions" width="75%">
  <br><br>
  <img src="media/3.1.png" alt="Deals" width="75%">
  <img src="media/4.png" alt="NFT Proof" width="75%">
  <br><br>
  <img src="media/5.png" alt="Hedera HashScan Verification" width="45%">
  <img src="media/6.png" alt="Member Dashboard" width="45%">
</div>

---

## 🎯 Track: DeFi & Tokenization

Airvyb transforms community participation into verifiable, immutable proof using Hedera NFTs. When members opt into community deals, they receive a unique NFT — a permanent record of their contribution that lives forever on Hedera.

**5 active members are already participating in real deals on our testnet. Their NFTs are live on HashScan.**

---

## 📖 Overview

**Airvyb** is a community participation platform that enables members to join curated deals managed by Airvyb Management Ltd (AML). Each deal represents a collective action — farm cooperatives, solar mini-grids, real estate acquisitions, or community programs.

When a member opts in:
1. They contribute KES via M-Pesa
2. A unique NFT is minted on Hedera Token Service
3. Every transaction is recorded on Hedera Consensus Service
4. They receive immutable proof of participation

**Not a financial product.** Airvyb is a community participation tool with professional oversight, built for the Kenyan market.

---

## 🔥 The Problem

| Challenge | Reality |
|-----------|---------|
| **No Verifiable Proof** | Participation records are PDFs — easily lost, easily forged |
| **High Barriers** | Most platforms require KES 10,000+ or USD/crypto |
| **No Transparency** | No way to independently verify participation |
| **Centralized Records** | Single points of failure, potential manipulation |

**13.7 million Kenyan youth want to participate in community initiatives. Most are excluded.**

---

## 💡 The Solution

<div align="center">
  <img src="media/1.png" alt="Airvyb Dashboard" width="80%">
  <p><em>Member dashboard showing wallet balance and recent deals</em></p>
</div>

### How Airvyb Works

```
graph TD
    A[Member Browses Deals] --> B[Selects Deal]
    B --> C[Opts In with KES via M-Pesa]
    C --> D[NFT Minted on Hedera Token Service]
    D --> E[Transaction on Hedera Consensus Service]
    E --> F[Member Receives NFT Proof]
    F --> G[Verifiable on HashScan Forever]
```

# Step-by-Step Flow
Discover Deals - Browse curated investment opportunities from AML

Opt In - Select a deal and opt in using wallet balance

Payment Processing - Funds deducted from wallet, transaction recorded

NFT Minting - Unique NFT minted on Hedera Token Service

Proof Generation - User receives NFT as immutable proof

Verification - View transaction and NFT on HashScan

🔗 Hedera Integration
1. Hedera Token Service (HTS) - NFT Collections
Each deal is an NFT collection:


# Create NFT collection for a deal
token_id = create_hedera_nft_collection(deal)
# Returns: "0.0.1234567"
2. Hedera Consensus Service (HCS) - Immutable Records
Every transaction is timestamped and stored:


# Submit transaction to HCS
hedera_data = {
    'type': 'deal_opt_in',
    'user_id': user.id,
    'amount': deal.opt_in_amount,
    'timestamp': timezone.now().isoformat()
}
hedera_consensus.submit_message(hedera_data)
3. Hedera Wallet Integration
Auto-creation of Hedera accounts for users:


# Auto-create wallet on user verification
account_data = HederaService.create_account(user.email)
user.hedera_account_id = account_data['account_id']
4. NFT Minting Process

def mint_opt_in_nft(opt_in):
    # Prepare metadata (under 100 bytes)
    metadata = f"{opt_in.reference[:8]}|{opt_in.user.id}|{opt_in.amount}"
    
    # Mint NFT on Hedera
    transaction = TokenMintTransaction() \
        .set_token_id(token_id) \
        .set_metadata([metadata.encode()]) \
        .freeze_with(client)
    
    receipt = transaction.execute(client)
    serial_number = receipt.serials[0]
    return serial_number
🏗️ Technical Architecture

┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Django Templates)              │
├─────────────────────────────────────────────────────────────┤
│                    Business Logic Layer                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Deal Views  │  │ Wallet Mgmt │  │ Transaction Processing│ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Hedera Integration Layer                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ HTS (NFT)   │  │ HCS (Logs)  │  │ Account Creation    │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Database (PostgreSQL)                     │
└─────────────────────────────────────────────────────────────┘
Core Models
python
# Deal Model - NFT Collection
class Deal(models.Model):
    hedera_token_id = models.CharField(max_length=50, unique=True)
    hedera_topic_id = models.CharField(max_length=50)
    total_opted_in = models.IntegerField(default=0)

# DealOptIn Model - NFT Proof
class DealOptIn(models.Model):
    user = models.ForeignKey(User)
    deal = models.ForeignKey(Deal)
    hedera_serial_number = models.IntegerField(null=True)
    hedera_nft_id = models.CharField(max_length=100, null=True)
✨ Key Features
For Members
🔍 Browse Deals - Filter by category, risk level, status

💰 Wallet Management - View balance, transaction history

📝 Opt-In to Deals - One-click participation

🎨 NFT Proof - Receive unique NFT as proof

📊 Dashboard - Track all investments in one place

🔗 HashScan Integration - Verify transactions instantly

For AML (Admin)
🏗️ Deal Creation - Create new deals with NFT collections

📈 Analytics Dashboard - Track total opt-ins, collections

🔄 Retry Mechanism - Recover from failed NFT minting

📊 Revenue Tracking - Monitor deal performance

🛠️ Tech Stack
Backend
Framework: Django 5.2

Database: PostgreSQL

Payment: IntaSend M-Pesa API

Caching: Redis

Task Queue: Celery (async processing)

Hedera Integration
SDK: hiero-sdk-python

Services:

Hedera Token Service (HTS) - NFT minting

Hedera Consensus Service (HCS) - Transaction logs

Hedera Account Service - Wallet creation

Network: Testnet (with mainnet ready)

Frontend
Templates: Django Templates

CSS: Custom + Font Awesome

JavaScript: Vanilla JS

Charts: Chart.js

DevOps
Container: Docker

CI/CD: GitHub Actions

Hosting: Ready for any cloud provider

🚀 Installation
Prerequisites
Python 3.10+

PostgreSQL

Redis (optional)

Hedera Testnet Account

Step 1: Clone Repository
bash
git clone https://github.com/yourusername/airvyb-invest.git
cd airvyb-invest
Step 2: Set Up Virtual Environment
bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Step 3: Install Dependencies
bash
pip install -r requirements.txt
Step 4: Configure Environment Variables
Create .env file:

env
# Django
SECRET_KEY=your-secret-key
DEBUG=True

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/airvyb

# Hedera
OPERATOR_ID=0.0.xxxxx
OPERATOR_KEY=your-operator-private-key
HEDERA_NETWORK=testnet
HEDERA_ENCRYPTION_KEY=your-encryption-key

# IntaSend
INTASEND_TOKEN=your-intasend-token
INTASEND_PUBLISHABLE_KEY=your-publishable-key
Step 5: Generate Hedera Encryption Key
python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())
# Add this to .env as HEDERA_ENCRYPTION_KEY
Step 6: Run Migrations
bash
python manage.py migrate
Step 7: Create Superuser
bash
python manage.py createsuperuser
Step 8: Run Development Server
bash
python manage.py runserver
🎮 Usage
Member Flow
Register - Create account with email/phone

Add Funds - Deposit via M-Pesa

Browse Deals - Find investment opportunities

Opt In - Choose a deal and invest

Receive NFT - Get your proof of participation

Track - Monitor all investments on dashboard

Admin Flow
Create Deal - Set up new investment opportunity

Configure NFT - Automatic collection creation

Monitor - Track opt-ins and collections

Retry - Recover failed NFT minting

🎥 Demo
Live Demo
Website: https://airvyb.co.ke

Demo Video: https://youtu.be/GGQNo683X8w

Test Credentials

Email: demo@airvyb.co.ke
Password: Demo123!
HashScan Verification
NFT Collection: https://hashscan.io/testnet/token/0.0.48764329

Sample Transaction: https://hashscan.io/testnet/transaction/0.0.48764329-123456789-000000000

🌍 Impact & Use Cases
Social Impact
Financial Inclusion - Low minimum investments enable participation

Transparency - Immutable records build trust

Accessibility - Simple interface for non-technical users

Economic Impact
Capital Formation - Aggregates small investments into larger deals

Job Creation - Funds real business operations

Wealth Building - Provides access to curated opportunities

Hedera Network Impact
Increased TPS - Thousands of transactions per deal

New Accounts - Each member gets a Hedera wallet

Network Usage - NFT minting + HCS messages

Adoption - Real-world use case demonstrates value

🗺️ Future Roadmap
Phase 1: Core Platform (Current)
✅ User registration & wallet creation

✅ Deal browsing and opt-in

✅ NFT minting on Hedera

✅ HCS transaction logging

Phase 2: Enhanced Features (Q3 2026)
🔲 Secondary market for NFT trading

🔲 Automated profit distributions

🔲 Deal analytics dashboard

🔲 Mobile app (React Native)

Phase 3: Ecosystem Expansion (Q4 2026)
🔲 Cross-chain compatibility

🔲 DAO governance for deal selection

🔲 DeFi integration (staking, lending)

🔲 Global expansion to new markets

Phase 4: Enterprise Solutions (2027)
🔲 White-label platform for institutions

🔲 Advanced compliance tools

🔲 Custom deal structuring

🔲 AI-powered risk assessment

👥 Team
Role	Name	GitHub
Lead Developer	Titos Kipkoech	@devtitos
Smart Contract Engineer	Titos Kipkoech	@devtitos
🙏 Acknowledgments
Hedera - For providing the infrastructure and support

IntaSend - For M-Pesa payment integration

Airvyb Management Ltd - For deal sourcing and curation

Hackathon Organizers - For creating this opportunity

📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

📞 Contact
Website: https://airvyb.co.ke

Email: invest@airvyb.co.ke

Discord: Join our community

Twitter: @AirvybInvest

🔗 Quick Links
Live Demo

Demo Video

GitHub Repository

HashScan Explorer

Pitch Deck

<div align="center"> <strong>Built with ❤️ for the Hedera Hello Future Apex Hackathon 2026</strong> </div>

# Airvyb Invest - Tokenized Deal Participation Platform

[![Hedera](https://img.shields.io/badge/Built%20on-Hedera-00c853?style=for-the-badge&logo=hedera&logoColor=white)](https://hedera.com)
[![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Hedera Hackathon](https://img.shields.io/badge/Hedera-Hello%20Future%20Apex%202026-ff0066?style=for-the-badge)](https://hellofuturehackathon.dev/)

> **Transforming investment participation through NFT-backed proofs on Hedera**

## 🎯 Track: DeFi & Tokenization

Airvyb Invest democratizes access to curated investment opportunities by tokenizing deal participation as NFTs on the Hedera network. Each member who opts into a deal receives a unique, immutable NFT proof, creating a transparent, verifiable investment history.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [How It Works](#how-it-works)
- [Hedera Integration](#hedera-integration)
- [Technical Architecture](#technical-architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Demo](#demo)
- [Impact & Use Cases](#impact--use-cases)
- [Future Roadmap](#future-roadmap)
- [Team](#team)
- [License](#license)

---

## 📖 Overview

**Airvyb Invest** is a decentralized investment platform that enables members to discover, evaluate, and participate in curated deals sourced by Airvyb Management Ltd (AML). Each deal is represented as an NFT collection on Hedera, and when members opt in, they receive a unique NFT as immutable proof of participation. Every transaction is recorded on Hedera Consensus Service, creating a transparent, auditable history of all investments.

### Key Metrics
- **💰 Prize Pool**: $250,000
- **🚀 Track**: DeFi & Tokenization
- **⏱️ Hackathon**: Hedera Hello Future Apex 2026
- **🏆 Category**: Best Use of Hedera Token Service + Consensus Service

---

## 🔥 Problem Statement

Traditional investment opportunities face several critical challenges:

1. **Lack of Transparency** - No immutable proof of participation or investment history
2. **High Barriers to Entry** - Minimum investments often exclude small investors
3. **Centralized Record-Keeping** - Single points of failure and potential manipulation
4. **No Verifiable Proof** - Investors cannot easily prove their stake or participation
5. **Limited Accessibility** - Complex processes exclude non-technical users

---

## 💡 Solution

**Airvyb Invest** solves these problems by leveraging Hedera's high-performance network:

### Core Innovations

1. **NFT-Backed Participation** - Each member who opts into a deal receives a unique NFT on Hedera, serving as immutable proof of their investment
2. **Transparent Record-Keeping** - All transactions stored on Hedera Consensus Service, creating an auditable, tamper-proof history
3. **Low Minimum Investment** - As low as KES 100/month, democratizing access
4. **User-Friendly Interface** - Simple, intuitive dashboard for managing investments
5. **Real-Time Verification** - View all transactions on HashScan with one click

---

## ⚙️ How It Works

```mermaid
graph TD
    A[User Browses Deals] --> B[Selects Deal to Opt In]
    B --> C[Wallet Balance Check]
    C --> D[Process Payment]
    D --> E[Create Opt-In Record]
    E --> F[Mint NFT on Hedera]
    F --> G[User Receives NFT Proof]
    G --> H[Transaction Stored on HCS]
    H --> I[Viewable on HashScan]
Step-by-Step Flow
Discover Deals - Browse curated investment opportunities from AML

Opt In - Select a deal and opt in using wallet balance

Payment Processing - Funds deducted from wallet, transaction recorded

NFT Minting - Unique NFT minted on Hedera Token Service

Proof Generation - User receives NFT as immutable proof

Verification - View transaction and NFT on HashScan

🔗 Hedera Integration
1. Hedera Token Service (HTS) - NFT Collections
Each deal is an NFT collection:

python
# Create NFT collection for a deal
token_id = create_hedera_nft_collection(deal)
# Returns: "0.0.1234567"
2. Hedera Consensus Service (HCS) - Immutable Records
Every transaction is timestamped and stored:

python
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

python
# Auto-create wallet on user verification
account_data = HederaService.create_account(user.email)
user.hedera_account_id = account_data['account_id']
4. NFT Minting Process
python
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
text
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
Website: https://airvyb-invest.vercel.app

Demo Video: https://youtu.be/your-demo-link

Test Credentials
text
Email: demo@airvyb.com
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
Role	Name	GitHub	LinkedIn
Lead Developer	[Your Name]	@yourgithub	Your LinkedIn
Smart Contract Engineer	[Name]	@github	LinkedIn
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

<div align="center"> <strong>Built with ❤️ for the Hedera Hello Future Apex Hackathon 2026</strong> </div> ```
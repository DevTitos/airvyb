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
  <img src="media/1.png" alt="Fianace Dashboard" width="80%">
  <img src="media/2.png" alt="Transactions" width="80%">
  <br><br>
  <img src="media/3.1.png" alt="Deals" width="45%">
  <img src="media/4.png" alt="NFT Proof" width="45%">
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
1. Discover Deals - Browse curated investment opportunities from AML

2. Opt In - Select a deal and opt in using wallet balance

3. Payment Processing - Funds deducted from wallet, transaction recorded

4. NFT Minting - Unique NFT minted on Hedera Token Service

5. Proof Generation - User receives NFT as immutable proof

6. Verification - View transaction and NFT on HashScan


# 🔗 Hedera Integration
1. Hedera Token Service (HTS) - NFT Collections
Each deal is an NFT collection:

```
# Create NFT collection for a deal
token_id = create_hedera_nft_collection(deal)
# Returns: "0.0.1234567"
```
# 2. Hedera Consensus Service (HCS) - Immutable Records
Every transaction is timestamped and stored:

```
# Submit transaction to HCS
hedera_data = {
    'type': 'deal_opt_in',
    'user_id': user.id,
    'amount': deal.opt_in_amount,
    'timestamp': timezone.now().isoformat()
}
hedera_consensus.submit_message(hedera_data)
```
# 3. Hedera Wallet Integration
Auto-creation of Hedera accounts for users:
```
# Auto-create wallet on user verification
account_data = HederaService.create_account(user.email)
user.hedera_account_id = account_data['account_id']
```
# 4. NFT Minting Process
```
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
```
# 🏗️ Technical Architecture
```
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

```
# Core Models
```
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
```
---
# For Members
🔍 Browse Deals - Filter by category, risk level, status
💰 Wallet Management - View balance, transaction history
📝 Opt-In to Deals - One-click participation
🎨 NFT Proof - Receive unique NFT as proof
📊 Dashboard - Track all investments in one place
🔗 HashScan Integration - Verify transactions instantly

# For AML (Admin)
🏗️ Deal Creation - Create new deals with NFT collections
📈 Analytics Dashboard - Track total opt-ins, collections
🔄 Retry Mechanism - Recover from failed NFT minting
📊 Revenue Tracking - Monitor deal performance

---

## 🛠️ Tech Stack

<div align="center">

| Category | Technologies |
|----------|--------------|
| **🎨 Frontend** | Django Templates • Custom CSS • Font Awesome • Chart.js • Vanilla JS |
| **⚙️ Backend** | Django 5.2 • PostgreSQL • Redis • Celery • IntaSend API |
| **🔗 Hedera** | hiero-sdk-python • HTS (NFTs) • HCS (Logs) • Hedera Account Service • Testnet |
| **🐳 DevOps** | Docker • GitHub Actions • Cloud Ready |

</div>

---

## 🚀 Quick Start

### Prerequisites

<div align="center">
  
| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| PostgreSQL | 14+ |
| Redis | 7+ (optional) |
| Hedera Account | Testnet |

</div>

## 🚀 Quick Start

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| PostgreSQL | 14+ |
| Redis | 7+ (optional) |
| Hedera Account | Testnet |

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/airvyb.git
cd airvyb

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start the server
python manage.py runserver
Environment Variables (.env)
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

```

# 🎮 How It Works
## Member Journey
Step	Action	Result
1️⃣	Register	Create account with email/phone
2️⃣	Add Funds	Deposit via M-Pesa
3️⃣	Browse Deals	Discover community deals
4️⃣	Opt In	Participate with KES
5️⃣	Receive NFT	Get proof on Hedera
6️⃣	Track	Monitor all participations
## Admin Flow
Step	Action	Result
1️⃣	Create Deal	Set up new community deal
2️⃣	Configure NFT	Auto-create NFT collection
3️⃣	Monitor	Track opt-ins & progress
4️⃣	Retry	Recover failed NFT minting
🎥 Live Demo
🌐 Website	https://airvyb.co.ke
🎬 Demo Video	Watch on YouTube
🔗 HashScan	View NFT Collection
## Test Credentials
text
Email: demo@airvyb.co.ke
Password: Demo123!
# 🌍 Impact
Social Impact	Economic Impact	Hedera Impact
🎯 Financial Inclusion
KES 500 minimum	💰 Capital Formation
Aggregates small contributions	📈 Increased TPS
Thousands of transactions
🔍 Transparency
Immutable records	👥 Job Creation
Funds real operations	👤 New Accounts
Each member gets wallet
🤝 Accessibility
Simple interface	🏗️ Wealth Building
Curated opportunities	🌐 Network Usage
NFTs + HCS messages
# 🗺️ Roadmap
```
Phase	Status	Features
Phase 1: Core Platform	✅ Complete	User registration • Wallet creation • Deal browsing • NFT minting • HCS logging
Phase 2: Enhanced Features	🔲 Q3 2026	NFT marketplace • Automated distributions • Analytics • Mobile app
Phase 3: Ecosystem Expansion	🔲 Q4 2026	Cross-chain • DAO governance • DeFi integration • Regional expansion
Phase 4: Enterprise	🔲 2027	White-label • Compliance tools • Custom structuring • AI risk assessment
```

# 👥 Team
Role	Name	GitHub
Lead Developer	Titos Kipkoech	@devtitos
Smart Contract Engineer	Titos Kipkoech	@devtitos
🙏 Acknowledgments
# Partner	Support
Hedera	Infrastructure & ecosystem support
IntaSend	M-Pesa payment integration
Airvyb Management Ltd	Deal sourcing & curation
Hackathon Organizers	Creating this opportunity
# 📄 License
This project is licensed under the MIT License — see the LICENSE file for details.

# 📞 Connect With Us
🌐 Website	📧 Email	🐙 GitHub	🐦 Twitter
🔗 Quick Links
🌐 Live Demo	🎬 Demo Video	📂 GitHub Repo
🔍 HashScan	📊 Pitch Deck	📝 License

<div align="center"> <br> <strong>Built with ❤️ for the Hedera Hello Future Apex Hackathon 2026</strong> <br><br> <img src="media/5.png" alt="Hedera HashScan" width="250"> <br> <em>Every participation. Forever verifiable.</em> </div> 
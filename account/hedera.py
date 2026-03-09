# hedera.py
import os
from decimal import Decimal
from cryptography.fernet import Fernet
from django.conf import settings
from dotenv import load_dotenv
from hiero_sdk_python import (
    Client,
    Network,
    AccountId,
    PrivateKey,
    AccountCreateTransaction,
    ResponseCode,
)

load_dotenv()

class HederaService:
    """Minimal Hedera Hashgraph service"""
    
    cipher = Fernet(settings.HEDERA_ENCRYPTION_KEY.encode()) if hasattr(settings, 'HEDERA_ENCRYPTION_KEY') else None
    
    @classmethod
    def get_client(cls):
        """Get Hedera client"""
        network = Network(network=getattr(settings, 'HEDERA_NETWORK', 'testnet'))
        client = Client(network)
        
        operator_id = AccountId.from_string(os.getenv('OPERATOR_ID'))
        operator_key = PrivateKey.from_string_ed25519(os.getenv('OPERATOR_KEY'))
        client.set_operator(operator_id, operator_key)
        
        return client
    
    @classmethod
    def encrypt_private_key(cls, private_key):
        """Encrypt private key for storage"""
        if not cls.cipher:
            return private_key
        return cls.cipher.encrypt(private_key.encode()).decode()
    
    @classmethod
    def decrypt_private_key(cls, encrypted_key):
        """Decrypt private key for use"""
        if not cls.cipher:
            return encrypted_key
        return cls.cipher.decrypt(encrypted_key.encode()).decode()
    
    @classmethod
    def create_account(cls, identifier):
        """Create new Hedera account (minimal balance)"""
        client = cls.get_client()
        
        # Generate new key pair
        new_private_key = PrivateKey.generate("ed25519")
        new_public_key = new_private_key.public_key()
        
        # Create account with minimal balance (5 HBAR = 500,000,000 tinybars)
        # This covers basic account creation and a few transactions
        transaction = (
            AccountCreateTransaction()
            .set_key(new_public_key)
            .set_initial_balance(500000000)  # 5 HBAR in tinybars
            .set_account_memo(f"Wallet for {identifier[:30]}")
            .freeze_with(client)
        )
        
        # Sign with operator key
        operator_key = PrivateKey.from_string_ed25519(os.getenv('OPERATOR_KEY'))
        transaction.sign(operator_key)
        
        try:
            receipt = transaction.execute(client)
            
            if receipt.status != ResponseCode.SUCCESS:
                print(f"Account creation failed: {ResponseCode(receipt.status).name}")
                return None
            
            account_id = receipt.account_id
            if account_id:
                return {
                    'account_id': str(account_id),
                    'public_key': new_public_key.to_string(),
                    'private_key': new_private_key.to_string(),
                }
            return None
            
        except Exception as e:
            print(f"Account creation failed: {str(e)}")
            return None
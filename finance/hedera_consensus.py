# finance/hedera_consensus.py
import json
import os
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from hiero_sdk_python import (
    Client,
    Network,
    AccountId,
    PrivateKey,
    TopicId,
    TopicCreateTransaction,
    TopicMessageSubmitTransaction,
)
from dotenv import load_dotenv

load_dotenv()

class HederaConsensusService:
    """Hedera Consensus Service for storing transactions"""
    
    def __init__(self):
        self.operator_id = AccountId.from_string(os.getenv('OPERATOR_ID'))
        self.operator_key = PrivateKey.from_string_ed25519(os.getenv('OPERATOR_KEY'))
        self.network = Network(network=os.getenv('HEDERA_NETWORK', 'testnet'))
        self.topic_id = os.getenv('TOPIC_ID')
        
    def _get_client(self):
        """Get Hedera client"""
        client = Client(self.network)
        client.set_operator(self.operator_id, self.operator_key)
        return client
    
    def create_topic(self, memo="Airvyb Transactions"):
        """Create a new consensus topic"""
        client = self._get_client()
        
        transaction = (
            TopicCreateTransaction(
                memo=memo,
                admin_key=self.operator_key.public_key()
            )
            .freeze_with(client)
            .sign(self.operator_key)
        )
        
        try:
            receipt = transaction.execute(client)
            if receipt and receipt.topicId:
                topic_id = str(receipt.topicId)
                print(f"Topic created with ID: {topic_id}")
                return topic_id
            else:
                print("Topic creation failed: Topic ID not returned in receipt.")
                return None
        except Exception as e:
            print(f"Topic creation failed: {str(e)}")
            return None
    
    def submit_message(self, message_data, topic_id=None):
        """
        Submit message to Hedera Consensus Service
        
        Args:
            message_data: dict containing transaction data
            topic_id: optional topic ID (uses TOPIC_ID from env if not provided)
        
        Returns:
            dict with submission result
        """
        client = self._get_client()
        
        # Use provided topic_id or from env
        topic = topic_id or self.topic_id
        
        if not topic:
            # Create a topic if none exists
            topic = self.create_topic()
            if not topic:
                return {
                    'status': 'failed',
                    'message': 'Failed to create Hedera topic'
                }
        
        topic_id = TopicId.from_string(topic)
        
        # Prepare message
        if isinstance(message_data, dict):
            # Convert Decimal to float for JSON serialization
            message_data = self._prepare_for_json(message_data)
            message = json.dumps(message_data, default=str)
        else:
            message = str(message_data)
        
        transaction = (
            TopicMessageSubmitTransaction(topic_id=topic_id, message=message)
            .freeze_with(client)
            .sign(self.operator_key)
        )
        
        try:
            receipt = transaction.execute(client)
            
            # Extract message ID from receipt if available
            message_id = None
            if hasattr(receipt, 'transaction_id') and receipt.transaction_id:
                message_id = str(receipt.transaction_id)
            
            print(f"Message submitted to topic {topic}: {message[:100]}...")
            
            return {
                'status': 'success',
                'topic': topic,
                'message_id': message_id,
                'consensus_timestamp': str(receipt.consensus_timestamp) if hasattr(receipt, 'consensus_timestamp') else None,
                'sequence_number': getattr(receipt, 'topic_sequence_number', None),
                'running_hash': getattr(receipt, 'topic_running_hash', None),
            }
        except Exception as e:
            print(f"Message submission failed: {str(e)}")
            return {
                'status': 'failed',
                'message': f"Message submission failed: {str(e)}"
            }
    
    def _prepare_for_json(self, data):
        """Prepare data for JSON serialization"""
        if isinstance(data, dict):
            return {k: self._prepare_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._prepare_for_json(item) for item in data]
        elif isinstance(data, Decimal):
            return float(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, timezone.datetime):
            return data.isoformat()
        else:
            return data


# Singleton instance
hedera_consensus = HederaConsensusService()
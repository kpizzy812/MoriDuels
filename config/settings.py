import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
MAIN_BOT_TOKEN = os.getenv('MAIN_BOT_TOKEN')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
CHANNEL_IDS = [int(x.strip()) for x in os.getenv('CHANNEL_IDS', '').split(',') if x.strip()]

# Telegram User Bot
TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '')
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE', '')

# Database
DATABASE_URL = os.getenv('DATABASE_URL')
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'mori_duels'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

# Solana
SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL')
MORI_TOKEN_MINT = os.getenv('MORI_TOKEN_MINT')
BOT_PRIVATE_KEY = os.getenv('BOT_PRIVATE_KEY')
BOT_WALLET_ADDRESS = os.getenv('BOT_WALLET_ADDRESS')

# APIs
JUPITER_API_KEY = os.getenv('JUPITER_API_KEY')
HELIUM_API_KEY = os.getenv('HELIUM_API_KEY')
BIRDEYE_API_KEY = os.getenv('BIRDEYE_API_KEY')

# Game Settings
HOUSE_ACCOUNTS = [x.strip() for x in os.getenv('HOUSE_ACCOUNTS', '').split(',') if x.strip()]
MIN_BET = float(os.getenv('MIN_BET', 1))
MAX_BET = float(os.getenv('MAX_BET', 100000))
HOUSE_COMMISSION = float(os.getenv('HOUSE_COMMISSION', 0.30))
WITHDRAWAL_COMMISSION = float(os.getenv('WITHDRAWAL_COMMISSION', 0.05))
MATCH_TIMEOUT = int(os.getenv('MATCH_TIMEOUT', 10))

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
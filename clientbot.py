import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from web3 import Web3
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
BERA_WALLET_ADDRESS = os.getenv('BERA_WALLET_ADDRESS')

# RPC URLs and Chain IDs for networks
RPC_URLS = {
    'BERA': os.getenv('BERA_RPC_URL'),
    'SEPOLIA': os.getenv('SEPOLIA_RPC_URL'),
    'HOLESKY': os.getenv('HOLESKY_RPC_URL')
}

CHAIN_IDS = {
    'BERA': int(os.getenv('BERA_CHAIN_ID')),
    'SEPOLIA': int(os.getenv('SEPOLIA_CHAIN_ID')),
    'HOLESKY': int(os.getenv('HOLESKY_CHAIN_ID'))
}

# In-memory storage for tracking requests
user_requests = {}

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message with sub-menu buttons when /start is issued."""
    keyboard = [
        [InlineKeyboardButton("Claim Sepolia ETH", callback_data='claim_sepolia')],
        [InlineKeyboardButton("Claim Holesky ETH", callback_data='claim_holesky')],
        [InlineKeyboardButton("Claim BERA v2 token", callback_data='claim_bera')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Choose what you would like to claim:', reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()  # Acknowledge the button press

    if query.data == 'claim_sepolia':
        await query.edit_message_text("Please provide your Sepolia wallet address.")
        context.user_data['network'] = 'SEPOLIA'
    elif query.data == 'claim_holesky':
        await query.edit_message_text("Please provide your Holesky wallet address.")
        context.user_data['network'] = 'HOLESKY'
    elif query.data == 'claim_bera':
        await query.edit_message_text("Please provide your BERA wallet address.")
        context.user_data['network'] = 'BERA'

async def receive_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the wallet address provided by the user."""
    wallet_address = update.message.text
    user_id = update.effective_user.id
    network = context.user_data.get('network', 'BERA')
    logging.info(f"Wallet address received: {wallet_address} for network: {network}")

    # Check if user has made a request in the last 24 hours
    if user_id in user_requests and network in user_requests[user_id]:
        last_request = user_requests[user_id][network]
        time_since_last_claim = datetime.now() - last_request['timestamp']
        if time_since_last_claim < timedelta(hours=24):
            time_left = timedelta(hours=24) - time_since_last_claim
            await update.message.reply_text(f'Cool down! Come back after {time_left}. \n'
                                            'Want more tokens!! connect with @sepolia_sell .')
            return

    try:
        # Send the tokens to the provided wallet address
        send_tokens(wallet_address, network)

        # Store the request
        if user_id not in user_requests:
            user_requests[user_id] = {}
        user_requests[user_id][network] = {'wallet': wallet_address, 'timestamp': datetime.now()}

        # Confirmation message
        await update.message.reply_text(f'0.1 {network} token has been sent to {wallet_address}.\n'
                                        'Want more tokens!! connect with @sepolia_sell .')

    except Exception as e:
        logging.error(f"Error sending tokens: {e}")
        await update.message.reply_text('An error occurred while sending tokens. Please try again later.')

def send_tokens(wallet_address, network):
    """Send tokens to the given wallet address on the specified network."""
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URLS[network]))
        nonce = w3.eth.get_transaction_count(w3.to_checksum_address(BERA_WALLET_ADDRESS))
        gas_price = w3.eth.gas_price  # Fetch gas price directly from the network

        tx = {
            'from': w3.to_checksum_address(BERA_WALLET_ADDRESS),
            'to': w3.to_checksum_address(wallet_address),
            'value': int(w3.to_wei(0.1, 'ether')),  # Ensure value is in wei and correctly formatted
            'gas': 21000,  # Standard gas limit for ETH transfers
            'gasPrice': gas_price,  # Correctly fetched gas price
            'nonce': nonce,
            'chainId': CHAIN_IDS[network],
        }

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logging.info(f"Transaction sent: {tx_hash.hex()} on {network} network.")
    except Exception as e:
        logging.error(f"Error sending tokens: {e}")
        raise

def main():
    """Start the bot."""
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_wallet))

    logging.info("Bot is polling...")
    application.run_polling()

if __name__ == '__main__':
    main()

import os
import time
import logging
import re
import threading
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from dotenv import load_dotenv
from database import Group, Session
import random

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
DEFAULT_DELAY_BETWEEN_GROUPS = int(os.getenv("DELAY_BETWEEN_GROUPS", 5))
DEFAULT_SENDING_INTERVAL = int(os.getenv("SENDING_INTERVAL", 600))  # Interval between sending messages in seconds
DELAY_RANDOM_PERCENTAGE = int(os.getenv("DELAY_RANDOM_PERCENTAGE", 0))


# Initialize Pyrogram client
app = Client("userbot", api_id=API_ID, api_hash=API_HASH)

# Connect to the database
db_session = Session()

# Variable to hold the message to send to all groups
message_to_send = None

# Event for controlling spam thread
stop_event = threading.Event()
spam_thread = None

def calculate_random_delay(base_delay):
    """
    Calcola un ritardo casuale basato su una percentuale massima di incremento.
    """
    max_increase = (DELAY_RANDOM_PERCENTAGE / 100) * base_delay
    random_delay = base_delay + random.uniform(0, max_increase)
    return random_delay

# Function to add a group to the database
def add_group(client: Client, message: Message):
    chat = message.chat
    if db_session.query(Group).filter_by(chat_id=chat.id).first():
        message.edit_text(f"The group '{chat.title}' is already in the database.")
        logging.info(f"Group '{chat.title}' (ID: {chat.id}) is already in the database.")
    else:
        new_group = Group(chat_id=chat.id, username=chat.username)
        db_session.add(new_group)
        db_session.commit()
        message.edit_text(f"The group '{chat.title}' has been successfully added to the database.")
        logging.info(f"Group '{chat.title}' (ID: {chat.id}) added to the database.")

def remove_group(client: Client, message: Message):
    chat = message.chat
    group = db_session.query(Group).filter_by(chat_id=chat.id).first()
    if group:
        db_session.delete(group)
        db_session.commit()
        message.edit_text(f"The group '{chat.title}' has been removed from the database.")
        logging.info(f"Group '{chat.title}' (ID: {chat.id}) removed from the database.")
    else:
        message.edit_text(f"The group '{chat.title}' is not in the database.")
        logging.warning(f"Attempted to remove group '{chat.title}' (ID: {chat.id}) that is not in the database.")

def set_message_to_send(client: Client, message: Message):
    global message_to_send
    message_to_send = message.reply_to_message.text
    message.edit_text("Message has been saved for broadcasting.")
    logging.info("A new message has been saved for broadcasting.")

def send_message_to_groups(delay_between_groups):
    global message_to_send
    if message_to_send:
        groups = db_session.query(Group).all()
        for group in groups:
            if stop_event.is_set():  # Check if the stop event is set
                logging.info("Stopping message broadcast.")
                break
            try:
                app.send_message(chat_id=group.chat_id, text=message_to_send)
                logging.info(f"Message sent to group '{group.username}'")
                delay = calculate_random_delay(delay_between_groups)
                logging.info(f"Delay set to {delay} seconds.")
                time.sleep(delay)
            except Exception as e:
                logging.error(f"Error sending message to group '{group.username}': {e}")

def background_message_sender(delay_between_groups, sending_interval):
    logging.info("Background spam task started.")
    while not stop_event.is_set():
        send_message_to_groups(delay_between_groups)
        if not stop_event.is_set():
            delay = calculate_random_delay(sending_interval)
            logging.info(f"Interval set to {delay} seconds.")
            time.sleep(delay)

def start_spam(client: Client, message: Message):
    global spam_thread

    if spam_thread and spam_thread.is_alive():
        message.edit_text("Spam is already running.")
        return

    try:
        delay_between_groups = int(message.text.split()[1])
        sending_interval = int(message.text.split()[2])
    except (IndexError, ValueError):
        delay_between_groups = DEFAULT_DELAY_BETWEEN_GROUPS
        sending_interval = DEFAULT_SENDING_INTERVAL

    stop_event.clear()
    spam_thread = threading.Thread(target=background_message_sender, args=(delay_between_groups, sending_interval))
    spam_thread.daemon = True
    spam_thread.start()
    message.edit_text(f"Spam started with a {delay_between_groups}s delay between groups and {sending_interval}s sending interval.")
    logging.info(f"Spam started with a {delay_between_groups}s delay and {sending_interval}s interval.")

def stop_spam(client: Client, message: Message):
    global spam_thread

    if not (spam_thread and spam_thread.is_alive()):
        message.edit_text("Spam is not running.")
        return

    stop_event.set()
    spam_thread.join(timeout=1)  # Wait for the thread to stop, with a timeout
    message.edit_text("Spam stopped.")
    logging.info("Spam stopped.")

@app.on_message(filters.private & filters.regex(r"^\.([a-zA-Z]+)"))
def private_command_handler(client: Client, message: Message):
    match = re.match(r"^\.([a-zA-Z]+)", message.text)
    if match:
        command = match.group(1)
        if command == "addmessage" and message.reply_to_message:
            set_message_to_send(client, message)
        elif command == "sendall":
            send_all(client, message)
        elif command == "startspam":
            start_spam(client, message)
        elif command == "stopspam":
            stop_spam(client, message)

@app.on_message(filters.me & filters.group & filters.regex(r"^\.([a-zA-Z]+)"))
def command_handler(client: Client, message: Message):
    logging.info(f"Command received: {message.text}")
    match = re.match(r"^\.([a-zA-Z]+)", message.text)
    if match:
        command = match.group(1)
        print(f"Sended command: {message.text}")

        if command == "add":
            add_group(client, message)
        elif command == "remove":
            remove_group(client, message)

def send_all(client: Client, message: Message):
    if not message_to_send:
        message.edit_text("No message has been saved. Use .addmessage to save a message.")
        logging.warning("Attempted to send messages without a saved message.")
        return
    message.edit_text("Starting message broadcast to all groups...")
    send_message_to_groups(DEFAULT_DELAY_BETWEEN_GROUPS)
    message.edit_text("Message broadcast completed.")
    logging.info("Message broadcast to all groups completed.")

def main():
    with app:
        logging.info("Userbot started.")

        # Send a message to self indicating that the bot is active
        app.send_message("me", "Userbot is active and running!")

        idle()

if __name__ == "__main__":
    main()

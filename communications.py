import requests
import os
from dotenv import load_dotenv
from pathlib import Path 
from twilio.rest import Client
from gtts import gTTS
import tempfile
import re 
import threading

def load_env_manually():
    env_vars = {}
    try:
        with open('.env', 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    match = re.match(r'^([^=]+)=(.*)$', line)
                    if match:
                        key = match.group(1).strip()
                        value = match.group(2).strip()
                        env_vars[key] = value
        return env_vars
    except FileNotFoundError:
        print("Error: .env file not found")
        return {}

# Debug: Print the current working directory
print(f"Current working directory: {os.getcwd()}")
# Debug: List all files in the current directory
print(f"Files in directory: {os.listdir()}")

# Load environment variables
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# SIMPLE TRANSLATION DICTIONARY
translation_dict = {
    'en': "Reminder: Take {dosage} of {name}. Reply TAKEN or SKIPPED.",
    'hi': "Reminder: {name} की {dosage} लें। जवाब दें: TAKEN या SKIPPED",
    'te': "Reminder: {name} యొక్క {dosage} తీసుకోండి. స్పందించండి: TAKEN లేదా SKIPPED",
    'ta': "Reminder: {name} இன் {dosage} எடுத்துக் கொள்ளுங்கள். பதில்: TAKEN அல்லது SKIPPED",
    'ml': "Reminder: {name} എന്നതിന്റെ {dosage} എടുക്കുക. പ്രതികരിക്കുക: TAKEN അല്ലെങ്കിൽ SKIPPED"
}

def send_sms_async(phone_number, message):
    """Sends an SMS using Twilio API in a separate thread (non-blocking)."""
    def sms_task():
        TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
        TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
        TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            print("ERROR: Twilio credentials not found. Please check your .env file.")
            return

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        to_number = f"+91{phone_number}"

        print(f"DEBUG: Attempting to send SMS to: {to_number}")
        print(f"DEBUG: From Twilio Number: {TWILIO_PHONE_NUMBER}")
        print(f"DEBUG: Message: {message}")

        try:
            twilio_message = client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=to_number
            )
            print(f"SUCCESS: Twilio SMS sent! Message SID: {twilio_message.sid}")
        except Exception as e:
            print(f"ERROR: Failed to send Twilio SMS: {e}")
    
    thread = threading.Thread(target=sms_task)
    thread.start()
    print(f"Twilio SMS process started for {phone_number}. Server can continue immediately.")

def make_voice_call(phone_number, message, language='en'):
    """Generates a voice message and initiates a call using Twilio Voice API."""
    def voice_task():
        TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
        TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
        TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            print("ERROR: Twilio credentials not found.")
            return

        # Convert text to speech
        try:
            tts = gTTS(text=message, lang=language, slow=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                temp_audio_file = fp.name
                tts.save(temp_audio_file)
            print(f"Voice message generated for {language}")
        except Exception as e:
            print(f"Failed to generate voice: {e}")
            return

        # Make the voice call
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        international_number = f"+91{phone_number}"

        # TwiML instructions for the call
        twiml = f"""
        <Response>
            <Play>{temp_audio_file}</Play>
            <Pause length="5"/>
            <Say language="{language}">To confirm you took your medicine, press 1. To say you skipped, press 2.</Say>
            <Gather input="dtmf" timeout="10" numDigits="1" action="/webhook/voice" method="POST"/>
        </Response>
        """

        try:
            call = client.calls.create(
                twiml=twiml,
                to=international_number,
                from_=TWILIO_PHONE_NUMBER
            )
            print(f"Voice call initiated! Call SID: {call.sid}")
        except Exception as e:
            print(f"Failed to make voice call: {e}")
        finally:
            # Clean up temporary file
            os.unlink(temp_audio_file)
    
    thread = threading.Thread(target=voice_task)
    thread.start()
    print(f"Voice call process started for {phone_number}.")

def send_reminder(patient_phone, patient_data, medicine_data):
    """Orchestrates the reminder process. Called by the scheduler in app.py."""
    try:
        patient_lang = patient_data.get('language', 'en')
        message_template = translation_dict.get(patient_lang, translation_dict['en'])
        translated_message = message_template.format(
            dosage=medicine_data['dosage'],
            name=medicine_data['name']
        )

        print(f"Translated message for {patient_lang}: {translated_message}")

        # Send both SMS and Voice call
        sms_response = send_sms_async(patient_phone, translated_message)
        make_voice_call(patient_phone, translated_message, patient_lang)
        
        print(f"Reminder sent via SMS and Voice to {patient_phone}.")

    except Exception as e:
        print(f"Error in send_reminder: {e}")

def send_caretaker_alert(caretaker_phone, message):
    """Send alert to caretaker"""
    def alert_task():
        TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
        TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
        TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            print("ERROR: Twilio credentials not found.")
            return

        international_number = f"+91{caretaker_phone}"
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        try:
            twilio_message = client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=international_number
            )
            print(f"Caretaker alert sent! SID: {twilio_message.sid}")
        except Exception as e:
            print(f"Failed to send caretaker alert: {e}")
    
    thread = threading.Thread(target=alert_task)
    thread.start()
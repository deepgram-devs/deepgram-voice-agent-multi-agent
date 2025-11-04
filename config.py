"""
Configuration for Multi-Agent Voice System

This config file contains only environment variables and settings
used by the multi-agent system (main_multiagent.py).

For the deprecated warm transfer implementation configuration,
see: dev_docs/deprecated/old_implementation/old_config.py
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file - THIS IS THE ONLY PLACE WE DO THIS
load_dotenv()

###################
# ENV VARIABLES   #
###################

# Server Configuration
LEAD_SERVER_HOST = os.getenv('LEAD_SERVER_HOST', '0.0.0.0')
LEAD_SERVER_PORT = int(os.getenv('LEAD_SERVER_PORT', '8000'))
LEAD_SERVER_EXTERNAL_URL = os.getenv('LEAD_SERVER_EXTERNAL_URL')

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# Phone Numbers
LEAD_PHONE_NUMBER = os.getenv('LEAD_PHONE_NUMBER')

# API Keys
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Validate required environment variables
required_vars = [
    'TWILIO_ACCOUNT_SID',
    'TWILIO_AUTH_TOKEN',
    'TWILIO_PHONE_NUMBER',
    'LEAD_PHONE_NUMBER',
    'LEAD_SERVER_EXTERNAL_URL',
    'DEEPGRAM_API_KEY',
    'GROQ_API_KEY'
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

from openai import OpenAI
import shelve
from dotenv import load_dotenv
import os
import time
import logging
import json
from supabase import create_client, Client
import os
import uuid
import pyodbc
import time

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
client = OpenAI(api_key=OPENAI_API_KEY)

# Update database configuration for Azure SQL
DB_SERVER = os.getenv("DB_SERVER")  # yourserver.database.windows.net
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DRIVER = os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")  # or 17 depending on your system

tools = [
    {
        "type": "function",
        "function": {
            "name": "generate_game_url",
            "description": "Generate a URL for the Whack-A-Me game based on user inputs and images",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The unique order ID for the game",
                    },
                    "game_text": {
                        "type": "object",
                        "properties": {
                            "introText": {
                                "type": "string",
                                "description": "The apology message or description",
                            },
                            "endText": {
                                "type": "string",
                                "description": "The ending message (defaults to 'I'll be better')",
                            },
                            "usedText": {
                                "type": "string",
                                "description": "Previously used text in the game session",
                            }
                        },
                        "required": ["introText", "endText", "usedText"]
                    },
                    "user_names": {
                        "type": "object",
                        "properties": {
                            "sender": {
                                "type": "string",
                                "description": "Name of the person sending the apology",
                            },
                            "receiver": {
                                "type": "string",
                                "description": "Name of the person receiving the apology",
                            }
                        },
                        "required": ["sender", "receiver"]
                    },
                    "face_cutout": {
                        "type": "string",
                        "description": "URL or base64 of the face cutout image",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "The Wix user ID of the creator",
                    }
                },
                "required": ["order_id", "game_text", "user_names", "face_cutout", "user_id"],
            },
        }
    }
]

def generate_game_url(order_id: str, game_text: dict, user_names: dict, face_cutout: str, user_id: str) -> str:
    """Store game data in Supabase and return the game URL"""
    # Initialize Supabase client
    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    supabase_key = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)

    # Generate UUIDs
    uuid_order_id = str(uuid.uuid4())
    uuid_user_id = str(uuid.uuid4())

    # Prepare game data following the same structure as frontend
    request_data = {
        "order_id": uuid_order_id,
        "user_id": uuid_user_id,
        "userImage": face_cutout,
        "userName": user_names.get("sender", ""),
        "gameText": game_text,
        "status": "PREVIEW",
        "gameURL": f"https://games.pinenli.me/?order_id={uuid_order_id}",
        "gameType": "Whack-A-Me"
    }

    # Prepare database record
    game_data = {
        "user_id": uuid_user_id,
        "order_id": uuid_order_id,
        "game_data": request_data,  # Store the entire request data
        "game_type": "Whack-A-Me"
    }

    print(game_data)
    try:
        # Insert data into Supabase without returning count
        result = supabase.table('GameDB').insert(game_data).execute()
        
        if hasattr(result, 'error') and result.error is not None:
            raise Exception(f"Failed to store game data: {result.error}")
            
    except Exception as e:
        raise Exception(f"Failed to store game data: {str(e)}")

    # Return the game URL with UUID
    return f"https://whack-a-me.com/game/{uuid_order_id}"


def upload_file(path):
    # Upload a file with an "assistants" purpose
    file = client.files.create(
        file=open("../../data/airbnb-faq.pdf", "rb"), purpose="assistants"
    )


def create_assistant():
    """
    You currently cannot set the temperature for Assistant via the API.
    """
    assistant = client.beta.assistants.create(
        name="Whack-A-Me",
        instructions="We're going to create a personalised game for a customer that helps you apologize for something silly that they've done. In order to create this game, we need the following information from them: 1. What is your name?* 2. Who is this for?* 3. Describe how you annoyed them to help us create a fun poem* 4. Write a small ending message This shows up at the end of the game. By default it is I'll be better!  5. We just need two pictures from you. One smiling and One Frowning. These images will be uploaded. We need to ask the customer to upload this. It helps us create an avatar for them. This is going to be a WhatsApp Bot. You are the assistant helping people make this game on WhatsApp.",
        model="gpt-4o",
        tools=tools
    )
    return assistant


def get_db_connection():
    """Create and return a database connection"""
    connection_string = (
        f'DRIVER={DB_DRIVER};'
        f'SERVER={DB_SERVER};'
        f'DATABASE={DB_NAME};'
        f'UID={DB_USER};'
        f'PWD={DB_PASSWORD};'
        'Encrypt=yes;'
        'TrustServerCertificate=no;'
        'Connection Timeout=30;'
    )
    return pyodbc.connect(connection_string)

def init_db():
    """Initialize the database table if it doesn't exist"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # SQL Server syntax for creating table if not exists
        cur.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='thread_messages' AND xtype='U')
            CREATE TABLE thread_messages (
                wa_id VARCHAR(255) PRIMARY KEY,
                thread_id VARCHAR(255) NOT NULL,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def check_if_thread_exists(wa_id):
    """Check if a thread exists for the given wa_id"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT thread_id FROM thread_messages WHERE wa_id = ?", (wa_id,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()

def store_thread(wa_id, thread_id):
    """Store thread information in the database"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # SQL Server MERGE statement (equivalent to PostgreSQL's INSERT ... ON CONFLICT)
        cur.execute("""
            MERGE thread_messages AS target
            USING (SELECT ? as wa_id, ? as thread_id) AS source
            ON target.wa_id = source.wa_id
            WHEN MATCHED THEN
                UPDATE SET thread_id = source.thread_id
            WHEN NOT MATCHED THEN
                INSERT (wa_id, thread_id)
                VALUES (source.wa_id, source.thread_id);
        """, (wa_id, thread_id))
        conn.commit()
    except Exception as e:
        print(f"Error storing thread: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def run_assistant(thread):
    assistant = client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)
    
    # Check for any existing runs
    runs = client.beta.threads.runs.list(thread_id=thread.id)
    for run in runs.data:
        if run.status in ["in_progress", "queued"]:
            # Wait for the existing run to complete
            while run.status not in ["completed", "failed", "expired"]:
                time.sleep(0.5)
                run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    # Create new run
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )

    while run.status not in ["completed", "failed"]:
        time.sleep(0.5)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        
        if run.status == "requires_action":
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            
            for tool_call in tool_calls:
                if tool_call.function.name == "generate_game_url":
                    # Parse the arguments and call the function
                    args = json.loads(tool_call.function.arguments)
                    output = generate_game_url(**args)
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": output
                    })
            
            # Submit the outputs back to the assistant
            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    new_message = messages.data[0].content[0].text.value
    logging.info(f"Generated message: {new_message}")
    return new_message


def generate_response(message_body, wa_id, name):
    # Check if there is already a thread_id for the wa_id
    thread_id = check_if_thread_exists(wa_id)

    # If a thread doesn't exist, create one and store it
    if thread_id is None:
        logging.info(f"Creating new thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.create()
        store_thread(wa_id, thread.id)
        thread_id = thread.id
    else:
        logging.info(f"Retrieving existing thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.retrieve(thread_id)

    # Check for any active runs and wait for them to complete
    runs = client.beta.threads.runs.list(thread_id=thread_id)
    for run in runs.data:
        if run.status in ['queued', 'in_progress', 'requires_action']:
            while True:
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )
                if run.status in ['completed', 'failed', 'cancelled']:
                    break
                time.sleep(1)

    # Add message to thread
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message_body,
    )

    # Run the assistant and get the new message
    new_message = run_assistant(thread)
    logging.info(f"To {name}: {new_message}")
    return new_message


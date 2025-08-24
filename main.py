
import json
import queue
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from dispatcher import Dispatcher
from listener import start_listening_service

# --- INITIAL SETUP ---
def get_system_prompt():
    """
    Loads the entire system prompt from a single file.
    This file should contain the role description, rules, and the full API spec.
    """
    try:
        with open('system_prompt.txt', 'r') as f:
            # add live context
            prompt = f.read() +  f"\n\n--- LIVE CONTEXT ---\nCurrent Date and Time: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}"
            return prompt
    except FileNotFoundError:
        raise FileNotFoundError("Error: 'system_prompt.txt' not found.")
    

# --- CORE LOGIC ---
def get_llm_response(client, conversation_history):
    """
    Sends the conversation history to the LLM and gets a response.
    """
    try:
        print("\nSending request to LLM...")
        response = client.chat.completions.create(
            model="gpt-4o",  # Using a modern and capable model
            messages=conversation_history,
            max_tokens=500, # Max tokens for the response
            temperature=0.2, # Lower temperature for more deterministic, command-like responses
            response_format={"type": "json_object"} # Enforce JSON output
        )
        # The response content is a string containing the JSON
        return response.choices[0].message.content
    except Exception as e:
        print(f"An error occurred with the LLM API call: {e}")
        return None


def parse_and_execute(command_json_str, dispatcher):
    """
    Parses the JSON response from the LLM and "executes" the command.
    """
    try:
        command_data = json.loads(command_json_str)

        if "function" in command_data and "parameters" in command_data:
            dispatcher.execute( command_data["function"], command_data["parameters"])
        else:
            print("Error: LLM response is missing 'function' or 'parameters' key.")
    except json.JSONDecodeError:
        print(f"Error: LLM did not return a valid JSON object. Response was:\n{command_json_str}")
        

# --- MAIN APPLICATION LOOP ---
def main():
    """
    Main function to run the Jarvis assistant loop.
    """

    load_dotenv()
    openai_client = OpenAI(api_key=os.getenv('OPENAI_KEY'))
    dispatcher = Dispatcher()  
    # start the listener threads for the microphones
    command_queue = queue.Queue()    
    listener_threads = start_listening_service(command_queue)

    conversation_history = []

    print("\n--- Jarvis Main Application is Running ---")
    print("Waiting for commands from the listener service...")
    

    # 4. Start the main "Consumer" loop
    try:
        while True:
            # This line will block and wait until a command appears in the queue.
            # This is the equivalent of waiting for input().
            tagged_command = command_queue.get()

            print(f"\n--- MAIN: Popped command from queue: '{tagged_command}' ---")

            # Prepare the prompt for the LLM
            live_prompt = get_system_prompt()
            
            # Add the new user message to the persistent history
            conversation_history.append({"role": "user", "content": tagged_command})

            # Construct the full message list to send to the API
            messages_to_send = [
                {"role": "system", "content": live_prompt},
                *conversation_history # Add all previous user/assistant turns
            ]           

            # Get the LLM's command
            llm_response_json = get_llm_response(openai_client, messages_to_send)

            # Execute the command and update history
            if llm_response_json:
                # Add the assistant's response to the history for future context
                conversation_history.append({"role": "assistant", "content": llm_response_json})
                parse_and_execute(llm_response_json, dispatcher)
            
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-10:]
            
        
    except KeyboardInterrupt:
        print("\n--- Shutting down all services ---")
        for thread in listener_threads:
            thread.stop()
        for thread in listener_threads:
            thread.join()
        print("All listener threads shut down. Exiting.")

if __name__ == "__main__":
    main()
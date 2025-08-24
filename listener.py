import threading
import time
import numpy as np
import openwakeword
import pyaudio
import speech_recognition as sr
from openwakeword.model import Model
from pathlib import Path
import socket

# --- CONFIGURATION ---
SERVER_HOST = '0.0.0.0'  # Listen on all available network interfaces
SERVER_PORT = 12345      # The port for mic_clients to connect to

# Audio stream settings (must match the client)
AUDIO_RATE = 16000
AUDIO_WIDTH = 2 # 2 bytes for paInt16 (16-bit audio)
CHUNK_SIZE = 1280 # 80ms chunks for openWakeWord

# --- PRODUCER: THE CLIENT HANDLER THREAD ---

class ClientHandler(threading.Thread):
    """
    A "Producer" thread. Handles a single microphone client connection.
    It receives raw audio, listens for a wake word, transcribes the command,
    and puts the result into the shared queue.
    """
    def __init__(self, client_socket, address, command_queue, oww_model):
        super().__init__()
        self.client_socket = client_socket
        self.address = address
        self.command_queue = command_queue
        self.oww_model = oww_model
        self.is_running = True
        self.recognizer = sr.Recognizer()
        self.mic_id = "Unknown"

    def run(self):
        try:
            # The first message from the client is its unique ID
            self.mic_id = self.client_socket.recv(1024).decode('utf-8')
            print(f"[{self.mic_id}] Accepted connection from {self.address}")
            
            # Send a confirmation byte to the client to start streaming
            self.client_socket.sendall(b'\x01')

            while self.is_running:
                # Receive audio data from the client
                audio_chunk = self.client_socket.recv(CHUNK_SIZE)
                if not audio_chunk:
                    break # Client disconnected

                audio_np = np.frombuffer(audio_chunk, dtype=np.int16)
                
                prediction = self.oww_model.predict(audio_np)
                
                if prediction['hey_jarvis_v0.1'] > 0.5:
                    print(f"\n--- Wake Word Detected on [{self.mic_id}]! ---")
                    # Pass the chunk that triggered the wake word to the transcriber
                    self.transcribe_and_queue_command(initial_chunk=audio_chunk)
                    print(f"[{self.mic_id}] Resuming wake word listening...")

        except ConnectionResetError:
            print(f"Client '{self.mic_id}' at {self.address} disconnected.")
        except Exception as e:
            print(f"Error in [{self.mic_id}] handler: {e}")
        finally:
            print(f"[{self.mic_id}] Closing connection.")
            self.client_socket.close()

    def transcribe_and_queue_command(self, initial_chunk):
        # This function is more complex now as it needs to handle a live stream
        # For now, we'll try to transcribe the initial chunk, but a more robust
        # solution would buffer a few seconds of audio after the wake word.
        try:
            print(f"[{self.mic_id}] Transcribing audio...")
            
            # Convert the raw audio chunk to SpeechRecognition's AudioData format
            audio_data = sr.AudioData(initial_chunk, AUDIO_RATE, AUDIO_WIDTH)
            command_text = self.recognizer.recognize_google(audio_data)
            
            tagged_message = f"METADATA: {{source_room: '{self.mic_id}'}} REQUEST: {command_text}"
            self.command_queue.put(tagged_message)

        except sr.UnknownValueError:
            print(f"[{self.mic_id}] Could not understand audio after wake word.")
        except sr.RequestError as e:
            print(f"[{self.mic_id}] STT service error; {e}")

    def stop(self):
        self.is_running = False

# --- SERVICE STARTER FUNCTION ---

def start_listening_service(command_queue):
    """
    Initializes the wake word model and starts the TCP server to listen for mic clients.
    Returns the main server thread so it can be managed.
    """
    print("Downloading wake word models (if necessary)...")
    # This will download all pre-trained models to the default cache location.
    # It only downloads them if they don't already exist.
    openwakeword.utils.download_models()
    
    # Initialize the model using the simple, correct name.
    # The library will find the model file in its cache.
    oww_model = Model(wakeword_models=['hey_jarvis_v0.1'])

    # Create a new thread for the server itself
    server_thread = threading.Thread(target=run_server, args=(command_queue, oww_model))
    # FIX: Set the thread as a daemon thread
    server_thread.daemon = True
    server_thread.start()
    
    print(f"\n--- Jarvis Listener Service is Running in the Background on {SERVER_HOST}:{SERVER_PORT} ---")
    # We no longer need to return the thread, as it will exit with the main app
    return None


def run_server(command_queue, oww_model):
    """The main loop for the TCP server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(5) # Allow up to 5 pending connections

    client_threads = []

    try:
        while True:
            # This is a blocking call that waits for a new client to connect
            client_socket, address = server_socket.accept()
            
            # Create and start a new thread for each connecting client
            handler = ClientHandler(client_socket, address, command_queue, oww_model)
            handler.start()
            client_threads.append(handler)

    except Exception as e:
        print(f"Server error: {e}")
    finally:
        print("Shutting down listener server.")
        for t in client_threads:
            t.stop()
            t.join()
        server_socket.close()

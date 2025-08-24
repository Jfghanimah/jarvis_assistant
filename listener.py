# listener.py

import threading
import time
import numpy as np
import openwakeword
import pyaudio
import speech_recognition as sr
from openwakeword.model import Model
from pathlib import Path
import socket
import audioop

# --- CONFIGURATION ---
SERVER_HOST = '0.0.0.0'  # Listen on all available network interfaces
SERVER_PORT = 12345      # The port for mic_clients to connect to

# Audio stream settings (must match the client)
AUDIO_RATE = 16000
AUDIO_WIDTH = 2 # 2 bytes for paInt16 (16-bit audio)
CHUNK_SIZE = 1280 # 80ms chunks for openWakeWord

# VAD Settings
VAD_THRESHOLD = 600  # RMS volume threshold to start/stop recording. Adjust this for your mic sensitivity.
VAD_SILENCE_TIMEOUT = 2.0  # Seconds of silence to wait before stopping recording.

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
                    self.transcribe_and_queue_command()
                    
                    # FIX: Reset the model's internal state to prevent re-triggering
                    self.oww_model.reset()
                    
                    print(f"[{self.mic_id}] Resuming wake word listening...")

        except ConnectionResetError:
            print(f"Client '{self.mic_id}' at {self.address} disconnected.")
        except Exception as e:
            print(f"Error in [{self.mic_id}] handler: {e}")
        finally:
            print(f"[{self.mic_id}] Closing connection.")
            self.client_socket.close()

    def transcribe_and_queue_command(self):
        try:
            print(f"[{self.mic_id}] Capturing command (VAD enabled)...")
            
            command_audio_frames = []
            is_speaking = False
            silence_chunks = 0
            max_silence_chunks = int(VAD_SILENCE_TIMEOUT * AUDIO_RATE / CHUNK_SIZE)

            while True:
                audio_chunk = self.client_socket.recv(CHUNK_SIZE)
                if not audio_chunk:
                    break
                
                # Calculate the volume (RMS) of the chunk
                rms = audioop.rms(audio_chunk, AUDIO_WIDTH)

                if rms > VAD_THRESHOLD:
                    # If sound is detected, start recording and reset silence counter
                    if not is_speaking:
                        print(f"[{self.mic_id}] Speaking detected.")
                        is_speaking = True
                    command_audio_frames.append(audio_chunk)
                    silence_chunks = 0
                elif is_speaking:
                    # If we were recording but are now in silence
                    silence_chunks += 1
                    command_audio_frames.append(audio_chunk) # Also capture the silence
                    if silence_chunks > max_silence_chunks:
                        print(f"[{self.mic_id}] Silence detected. Ending capture.")
                        break
            
            if not command_audio_frames:
                print(f"[{self.mic_id}] No command captured after wake word.")
                return

            full_command_audio = b''.join(command_audio_frames)
            audio_data = sr.AudioData(full_command_audio, AUDIO_RATE, AUDIO_WIDTH)

            print(f"[{self.mic_id}] Transcribing audio...")
            command_text = self.recognizer.recognize_google(audio_data)
            tagged_message = f"METADATA: {{source_room: '{self.mic_id}'}} MESSAGE: {command_text}"
            self.command_queue.put(tagged_message)

        except sr.UnknownValueError:
            print(f"[{self.mic_id}] Could not understand audio after wake word.")
        except sr.RequestError as e:
            print(f"[{self.mic_id}] STT service error; {e}")
        except Exception as e:
            print(f"An error occurred during transcription: {e}")

    def stop(self):
        self.is_running = False

# --- SERVICE STARTER FUNCTION ---

def start_listening_service(command_queue):
    """
    Initializes the wake word model and starts the TCP server to listen for mic clients.
    Returns the main server thread so it can be managed.
    """
    print("Downloading wake word models (if necessary)...")
    openwakeword.utils.download_models()
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
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(5) # Allow up to 5 pending connections

    client_threads = []

    try:
        while True:
            # This is a blocking call that waits for a new client to connect
            client_socket, address = server_socket.accept()
            
            # Create and start a new thread for each connecting client
            handler = ClientHandler(client_socket, address, command_queue, oww_model)
            handler.daemon = True
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

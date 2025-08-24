import pyaudio
import socket
import threading
import sys

# --- CONFIGURATION ---
SERVER_HOST = '127.0.0.1'  # <-- IMPORTANT: Change this to the IP address of your main server
SERVER_PORT = 12345         # The port the listener service is waiting on
MIC_ID = "laptop_mic"       # A unique identifier for this microphone

# Audio stream settings (must match the server's expectations)
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def list_audio_devices(p):
    """Lists all available audio input devices."""
    print("\n--- Available Audio Input Devices ---")
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            print(f"Input Device ID {i} - {p.get_device_info_by_host_api_device_index(0, i).get('name')}")
    print("-------------------------------------\n")


def stream_audio(client_socket):
    """Captures audio from the microphone and streams it to the server."""
    audio = pyaudio.PyAudio()
    list_audio_devices(audio)
    stream = None
    
    try:
        print(f"Attempting to open microphone stream at {RATE} Hz...")
        stream = audio.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK)
        print(">>> Microphone is live and streaming to the server...")
        
        # First, send the mic_id to identify this client
        client_socket.sendall(MIC_ID.encode('utf-8'))
        
        # Wait for a confirmation byte before streaming
        confirmation = client_socket.recv(1)
        if confirmation != b'\x01':
            print("Server did not acknowledge. Closing.")
            return

        while True:
            data = stream.read(CHUNK)
            client_socket.sendall(data)

    except OSError as e:
        print(f"\n!!! AUDIO ERROR !!!")
        print(f"Error opening audio stream: {e}")
        print(f"This usually means the sample rate ({RATE} Hz) is not supported by your microphone.")
        print("Please check your microphone's settings.")
    except (BrokenPipeError, ConnectionResetError):
        print("Connection to the server was lost.")
    except KeyboardInterrupt:
        print("Stopping stream.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
        audio.terminate()
        client_socket.close()
        print("Stream and connection closed.")

def main():
    """Connects to the server and starts the audio stream."""
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        print(f"Attempting to connect to server at {SERVER_HOST}:{SERVER_PORT}...")
        client_socket.connect((SERVER_HOST, SERVER_PORT))
        print("Successfully connected to the server.")
        stream_audio(client_socket)
    except ConnectionRefusedError:
        print("Connection refused. Is the listener_service.py running on the server?")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    main()

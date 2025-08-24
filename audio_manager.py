import os
from gtts import gTTS
from playsound import playsound
import tempfile

class AudioManager:
    """
    Handles all audio-related tasks for the Jarvis system,
    such as Text-to-Speech (TTS) generation and playback.
    """
    def __init__(self):
        """
        Initializes the AudioManager.
        """
        print("Audio Manager initialized.")

    def speak(self, text, target_speakers, volume):
        """
        Converts text to speech and plays it.

        In a real multi-speaker system, this function would be much more complex.
        It would need to:
        1. Identify the correct audio output device ID for the 'target_speakers'.
        2. Route the audio stream to that specific device.

        For this simulation, we will generate the audio and play it on the
        default output device of the computer running the script.

        Args:
            text (str): The text to be spoken.
            target_speakers (list or str): The speakers to play the sound on.
            volume (int): The target volume (currently unused in this simulation).
        """
        if not text:
            print("Audio Manager: No text provided to speak.")
            return

        print(f"Audio Manager: Generating TTS for text: '{text}'")
        
        try:
            # Create a gTTS object
            tts = gTTS(text=text, lang='en', slow=False)

            # Use a temporary file to save the speech audio
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as fp:
                temp_filename = fp.name
            
            tts.save(temp_filename)

            # Play the sound file
            playsound(temp_filename)
            
            # Clean up the temporary file
            os.remove(temp_filename)

        except Exception as e:
            print(f"Audio Manager Error: Failed to generate or play TTS audio. {e}")


# This block allows you to test the AudioManager independently.
if __name__ == '__main__':
    print("--- Testing AudioManager ---")
    audio_manager = AudioManager()
    audio_manager.speak(
        text="Hello, this is a test of the text to speech system.",
        target_speakers=["office"],
        volume=80
    )

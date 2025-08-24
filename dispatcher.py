import time
from audio_manager import AudioManager

class Dispatcher:
    """
    Handles the execution of commands received from the LLM.
    This class acts as a bridge between the AI's instructions
    and the actual smart home device control logic.
    """
    def __init__(self):
        """
        Initializes the Dispatcher and maps function names to handler methods.
        """
        self.function_map = {
            "playMusic": self._handle_play_music,
            "setVolume": self._handle_set_volume,
            "makeAnnouncement": self._handle_make_announcement,
            # As you add more functions to your API, you will add their handlers here.
        }
        self.audio_manager = AudioManager()

        print("Dispatcher initialized.")

    def execute(self, function_name, parameters):
        """
        Executes a command by calling the appropriate handler method.

        Args:
            function_name (str): The name of the function to execute.
            parameters (dict): A dictionary of parameters for the function.
        """
        handler = self.function_map.get(function_name)

        if handler:
            print(f"\n--- DISPATCHER ---")
            print(f"Received command: '{function_name}' with params: {parameters}")
            try:
                # Call the associated handler method with the parameters
                handler(parameters)
            except Exception as e:
                print(f"Error executing '{function_name}': {e}")
        else:
            print(f"\n--- DISPATCHER WARNING ---")
            print(f"Unknown function called: '{function_name}'. No action taken.")

    # --- Handler Methods ---

    def _handle_play_music(self, params):
        """
        Simulates the action of playing music on speakers.
        In a real application, this would contain the code to interact
        with Sonos, Spotify, etc.
        """
        target = params.get('zone') or params.get('speakers', 'unknown location')
        song_info = params.get('song') or params.get('playlist', 'something')
        artist = f" by {params.get('artist')}" if params.get('artist') else ""
        platform = f" on {params.get('platform')}" if params.get('platform') else ""
        volume = f" at {params.get('volume')}% volume" if params.get('volume') is not None else ""

        print(f"Action: Playing '{song_info}{artist}' in '{target}'{platform}{volume}.")

    def _handle_set_volume(self, params):
        """
        Simulates setting the volume on speakers.
        """
        target = params.get('zone') or params.get('speakers', 'unknown location')
        volume = params.get('volume', 'a default level')

        print(f"Action: Setting volume to {volume}% in '{target}'.")


    def _handle_make_announcement(self, params):
        """
        Simulates making an announcement.
        """
        message = params.get('message', 'No message provided.')
        target = params.get('zone') or params.get('speakers', 'all')
        volume = f" at {params.get('volume')}% volume" if params.get('volume') is not None else ""

        print(f"Action: Announcing to '{target}'{volume}: '{message}'")
        self.audio_manager.speak(text=message, target_speakers=target, volume=volume)

# This block allows you to test the dispatcher independently.
# To run, execute `python dispatcher.py` in your terminal.
if __name__ == '__main__':
    print("--- Testing Dispatcher ---")
    dispatcher = Dispatcher()

    # Test case 1: Play Music
    music_command = {
        "function": "playMusic",
        "parameters": {
            "playlist": "dinner party",
            "speakers": ["kitchen", "family room"]
        }
    }
    dispatcher.execute(music_command['function'], music_command['parameters'])

    # Test case 2: Set Volume
    volume_command = {
        "function": "setVolume",
        "parameters": {
            "speakers": ["master room"],
            "volume": 20
        }
    }
    dispatcher.execute(volume_command['function'], volume_command['parameters'])

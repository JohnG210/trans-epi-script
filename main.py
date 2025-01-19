import ffmpeg
import requests
from difflib import SequenceMatcher
import whisper
import shutil
import sys

import os
import re

# Function to parse the .srt file and extract the transcript (remove timestamps and sequence numbers)
def parse_srt_file(srt_path):
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split the content by double newlines (each subtitle entry is separated by two newlines)
    subtitle_entries = content.split("\n\n")
    
    transcript = ""
    
    for entry in subtitle_entries:
        lines = entry.split("\n")
        
        if len(lines) >= 3:
            # The first line is the sequence number, the second line is the timestamp, and the rest are the transcript.
            transcript += " ".join(lines[2:]) + " "  # Join the lines of the transcript and add to the result
    
    return transcript.strip()

# Function to find all .srt files in the directory, assuming episode numbers are in the filename or folder name
def find_srt_files(base_path):
    episode_transcripts = {}
    
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".srt"):
                # Assuming episode number is in the filename, e.g., "S01E01.srt"
                match = re.search(r"S(\d+)E(\d+)", file, re.IGNORECASE)
                if match:
                    season = match.group(1)
                    episode = match.group(2)
                    episode_number = int(episode)
                    
                    # Get the full path of the .srt file
                    srt_path = os.path.join(root, file)
                    
                    # Parse the .srt file and get the transcript
                    transcript = parse_srt_file(srt_path)
                    
                    # Add the transcript to the dictionary with episode number as the key
                    episode_transcripts[episode_number] = transcript
    
    return episode_transcripts

# TMDb API Key (replace with your own API key)
API_KEY = '5d11293443f6a405ff6f61dcea0f2f93'
BASE_URL = 'https://api.themoviedb.org/3'

## movietb
def create_guest_session():
    """Create a guest session to authenticate requests."""
    url = f"{BASE_URL}/authentication/guest_session/new?api_key={API_KEY}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        guest_session_id = data.get("guest_session_id")
        if guest_session_id:
            print(f"Guest session created: {guest_session_id}")
            return guest_session_id
    print(f"Failed to create guest session: {response.status_code}")
    return None

def get_episodes_by_season(tv_show_id, season_number, guest_session_id):
    """Get episode details for a specific TV show season."""
    url = f"{BASE_URL}/tv/{tv_show_id}/season/{season_number}&guest_session_id={guest_session_id}?api_key={API_KEY}"
    response = requests.get(url)
    
    if response.status_code == 200:
        season_data = response.json()
        episodes = season_data.get('episodes', [])
        return [(episode['name'], episode['episode_number'], episode['runtime']) for episode in episodes]
    else:
        print(f"Error fetching data from TMDb API: {response.status_code}")
        return []

# Function to extract the first minute from a video
def extract_first_minute(video_file):
    audio_file = "first_minute.wav"
    
    # Suppress printouts
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    
    try:
        (
            ffmpeg
            .input(video_file, ss=0, t=60*15)
            .output(audio_file, format='wav', acodec='pcm_s16le', ac=1, ar='44100')
            .run(overwrite_output=True)
        )
    finally:
        # Restore original stdout and stderr
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
    
    return audio_file

# Function to transcribe audio using OpenAI Whisper
def transcribe_audio(audio_file):
    # Suppress printouts
    original_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_file)
    finally:
        # Restore original stdout
        sys.stdout.close()
        sys.stdout = original_stdout
    
    return result["text"]

# Function to fetch episode transcripts from TMDb (or any other API)
def fetch_episode_transcripts(show_id, season_number):
    api_key = ""
    url = f"https://api.themoviedb.org/3/tv/{show_id}/season/{season_number}/episodes?api_key={api_key}"
    response = requests.get(url)
    episodes = response.json()['episodes']
    episode_transcripts = {}
    
    for episode in episodes:
        episode_number = episode['episode_number']
        episode_title = episode['name']
        # Assuming a method to fetch transcript for an episode exists
        transcript = get_episode_transcript(episode_number, season_number)
        episode_transcripts[episode_number] = transcript
    
    return episode_transcripts

# Function to compare transcripts and find the best match
def find_best_match(first_minute_transcript, episode_transcripts):
    best_match = None
    highest_ratio = 0
    
    for episode_number, transcript in episode_transcripts.items():
        ratio = SequenceMatcher(None, first_minute_transcript, transcript).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = episode_number
    
    return best_match, highest_ratio

# Main function
def identify_episode(video_file, show_id, season_number, episode_transcripts):
    # Step 1: Extract first minute of video
    audio_file = extract_first_minute(video_file)
    
    # Step 2: Transcribe the first minute
    first_minute_transcript = transcribe_audio(audio_file)
    
    # # Step 3: Fetch episode transcripts for the given show and season
    # episode_transcripts = fetch_episode_transcripts(show_id, season_number)
    
    # Step 4: Find the best matching episode
    best_match, score = find_best_match(first_minute_transcript, episode_transcripts)
    print(f"\n\nBest match for {video_file}: Episode {best_match} with a similarity score of {score*100}%")
    return best_match

def process_videos(input_directory, output_directory, show_id, season_number, episode_transcripts):
    # Create output directory if it doesn't exist
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Loop through all files in the input directory
    for filename in os.listdir(input_directory):
        if filename.endswith(('.mkv', '.mp4', '.avi', '.mov')):  # Add other video file types if needed
            video_file = os.path.join(input_directory, filename)
            
            # Identify the episode number for this video file
            episode_number = identify_episode(video_file, show_id, season_number, episode_transcripts)

            # Build the new file name based on the show name and episode details
            new_filename = f"{show_id}_S{season_number:02}E{episode_number:02}{os.path.splitext(filename)[1]}"

            # Define the full path for the new file location
            new_file_path = os.path.join(output_directory, new_filename)

            # Copy and rename the file to the output directory
            shutil.copy2(video_file, new_file_path)
            print(f"File {filename} copied as {new_filename}")

def main():
    # Create a guest session
    guest_session_id = create_guest_session()
    if not guest_session_id:
        print("Exiting... Unable to create a guest session.")
        return

    # Get TV Show ID and season number
    # tv_show_id = input("Enter the TMDb TV Show ID: ")
    tv_show_id = 48891
    # season_number = int(input("Enter the season number: "))
    season_number = 1
    # show_name = input("Enter the name of the show (used for naming files): ").replace(" ", "_")
    show_name = "brooklyn-nine-nine".replace(" ", "_")

    
    # Get episodes' names and durations
    episodes = get_episodes_by_season(tv_show_id, season_number, guest_session_id)
    
    if not episodes:
        print("No episodes found. Exiting...")
        return
    
    print(f"Found {len(episodes)} episodes.")

    # Find all .srt files and extract the transcripts
    season_number = 7
    folder_path = f"/Users/johnathangaliano/Documents/fix-show-names/2013-brooklyn-nine-nine/Season {season_number}"
    episode_transcripts = find_srt_files(folder_path)
    
    if episode_transcripts:
        print(f"Collected {len(episode_transcripts)} episode transcripts:")
        # Optionally print the first 3 episodes' transcripts as a preview
        for episode, transcript in list(episode_transcripts.items())[:3]:
            print(f"\nEpisode {episode} Transcript:\n{transcript[:500]}...")  # Print the first 500 chars as preview
    else:
        print("No .srt files found in the provided directory.")

    # Example usage
    input_directory = f"/Users/johnathangaliano/Documents/fix-show-names/og/Season 0{season_number}"
    output_directory = f"/Users/johnathangaliano/Documents/fix-show-names/output_{season_number}"
    show_id = "brooklyn-nine-nine"  # TMDb Show ID for your show

    process_videos(input_directory, output_directory, show_id, season_number, episode_transcripts)

if __name__ == "__main__":
    main()

import ffmpeg
from difflib import SequenceMatcher
import whisper
import shutil
import sys
import os
import re
from pathlib import Path
import argparse

# Builds the episode transcripts from the .srt files
class EpisodeTranscriptsBuilder:
    def __init__(self):
        self.trans_array = []

    def parse_srt_file(self, srt_path):
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        subtitle_entries = content.split("\n\n")
        transcript = ""
        
        for entry in subtitle_entries:
            lines = entry.split("\n")
            if len(lines) >= 3:
                transcript += " ".join(lines[2:]) + " "
        
        return transcript.strip()

    # Function to find all .srt files in the directory, assuming episode numbers are in the filename or folder name
    def find_srt_files(self, base_path):
        episode_transcripts = {}
        srt_files = Path(base_path).rglob("*.srt")
        print(f"Searching for .srt files in: {base_path}")
        srt_files = list(srt_files)  # Convert to list to print and iterate multiple times
        print(f"Found {len(srt_files)} .srt files")
        for srt_file in srt_files:
            print(f"Processing file: {srt_file}")
            match = re.search(r"S(\d+)E(\d+)", srt_file.name, re.IGNORECASE)
            if match:
                episode_number = int(match.group(2))
                transcript = self.parse_srt_file(srt_file)
                episode_transcripts[episode_number] = transcript
        return episode_transcripts

# Converts audio to transcript using the whisper library
class AudioToTranscriptConverter:
    def __init__(self, model_name="base"):
        self.model = whisper.load_model(model_name)

    def convert_audio_to_transcript(self, audio_path):
        result = self.model.transcribe(audio_path)
        return result['text']

    def extract_audio(self, video_file):
        audio_file = "Current_episode.wav"
        
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
        except Exception as e:
            print(f"Error extracting audio from {video_file}: {e}\n")
            raise Exception("Make sure ffmpeg is installed and added to PATH https://www.ffmpeg.org/download.html\n")
        finally:
            # Restore original stdout and stderr
            sys.stdout.close()
            sys.stderr.close()
            sys.stdout = original_stdout
            sys.stderr = original_stderr
        
        return audio_file

# Handles inputs from the command line
class ArgumentParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Process video files and transcripts.")
        self.parser.add_argument("--season_number", type=int, required=True, help="Season number")
        self.parser.add_argument("--video_input_directory", type=str, required=True, help="Path to the video input directory")
        self.parser.add_argument("--transcript_input_directory", type=str, required=True, help="Path to the transcript input directory")
        self.parser.add_argument("--output_directory", type=str, required=True, help="Path to the output directory")
        self.parser.add_argument("--show_name", type=str, required=True, help="Show name")

    def parse_args(self):
        args = self.parser.parse_args()
        return {
             "season_number": int(args.season_number),
            "video_input_directory": Path(rf"{args.video_input_directory}{args.season_number}"),
            "transcript_input_directory": Path(rf"{args.transcript_input_directory}{args.season_number}"),
            "output_directory": Path(rf"{args.output_directory}{args.season_number}"),
            "show_name": args.show_name
        }

def rename_and_move_episodes(final_dict, output_directory, show_name, season_number):
    for episode_number, data in final_dict.items():
        best_match_episode = data["best_match_episode"]
        original_file = data["original_file"]
        file_extension = os.path.splitext(original_file)[1]
        new_filename = Path(f"{output_directory}/{show_name}-S{season_number}E{best_match_episode}{file_extension}")
        new_filename.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(original_file, new_filename)

def find_matching_episodes(video_input_directory, episode_transcripts, audio_converter):
    final_dict = {}
    video_files = Path(video_input_directory).rglob("*")
    print(f"Searching for files in: {video_input_directory}")
    video_files = list(video_files)  # Convert to list to print and iterate multiple times
    print(f"Found {len(video_files)} .srt files")
    for file in video_files:
        file_path = Path(video_input_directory) / file
        if str(file_path).endswith(('.mkv', '.mp4', '.avi', '.mov')):
            # Generate the transcript for the current episode
            video_path = file_path
            audio_path = audio_converter.extract_audio(video_path)
            audio_transcript = audio_converter.convert_audio_to_transcript(audio_path)
            # Delete the audio file
            os.remove(audio_path)
            
            # Compare the generated transcript with the transcripts of other episodes
            scores = {}
            cur_match_score = 0
            current_episode_match = None
            for other_episode_number, other_transcript in episode_transcripts.items():
                score = SequenceMatcher(None, audio_transcript, other_transcript).ratio()
                scores[other_episode_number] = score
                if score > cur_match_score:
                    cur_match_score = score
                    current_episode_match = other_episode_number

            if current_episode_match in final_dict:
                raise ValueError(f"Duplicate entry found for episode {current_episode_match}")

            final_dict[current_episode_match] = {
                "original_file": video_path,
                "scores": scores,
                "best_match_episode": current_episode_match,
                "best_match_score": cur_match_score
            }
    return final_dict

def main():
    arg_parser = ArgumentParser()
    config = arg_parser.parse_args()

    # Get all the "truth" transcripts for the episodes
    episode_transcripts_builder = EpisodeTranscriptsBuilder()
    episode_transcripts = episode_transcripts_builder.find_srt_files(config["transcript_input_directory"])

    # Initialize the audio converter
    audio_converter = AudioToTranscriptConverter()

    # Match the episodes based on the transcripts
    final_dict = find_matching_episodes(config["video_input_directory"], episode_transcripts, audio_converter)

    # Rename and move the episodes to the output directory
    rename_and_move_episodes(final_dict, config["output_directory"], config["show_name"], config["season_number"])

if __name__ == "__main__":
    main()
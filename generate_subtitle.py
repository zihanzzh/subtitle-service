import argparse  #define command line like --input
import subprocess #runs ffmpeg
import os
from transcriber import transcribe_audio
from translator import (
    group_subtitles,
    load_gemini_api_key,
    setup_gemini,
    translate_groups,
    split_and_assign_translation,
    write_srt_file
)

# This function extracts audio
# from the given video file 
# using ffmpeg 
def extract_audio(input_path, audio_path):
  command = [
    "ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "copy", audio_path
  ]

  result = subprocess.run(command, capture_output = True)
  if result.returncode != 0:
    print("Audio extraction failed.")
    print(result.stderr.decode()) #print the error message
  else:
    print(f"Audio extracted to: {audio_path}")

# Burn the subtitle back to the video using ffmpeg
def burn_subtitles_to_video(input_video, srt_file, output_video):
    command = [
        "ffmpeg","-i", input_video,"-vf", f"subtitles={srt_file}",output_video
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Subtitles burned successfully! Final video: {output_video}")
    else:
        print(f"FFmpeg failed:\n{result.stderr}")
  
def main():
  #create a command-line parser
  parser = argparse.ArgumentParser(description = "Generate subtitles for a video")
  parser.add_argument('--input', required=True, help="path to input video file")
  parser.add_argument('--lang', default='English', help="target subtitle language")
  parser.add_argument('--output', default = 'output.mp4', help="final output video file name")
  args = parser.parse_args()
  input_video = args.input
  audio_file = "temp_audio.aac"
  print(f"processing video: {input_video}")
  #step 1: extract the voice track
  extract_audio (input_video, audio_file)

  #step 2: convert voice to transcribed text
  transcribe_audio (audio_file, lang = args.lang)

  # Step 3: Translate subtitles
  srt_file = "temp_audio.srt"
  
  groups = group_subtitles(srt_file)
  print(f"Loaded {len(groups)} subtitle groups.")

  # Set up Gemini
  api_key = load_gemini_api_key()
  model = setup_gemini(api_key)

  # Translate
  translated_batches = translate_groups(groups, model, target_lang="Chinese")

  # Split and assign new time ranges, then write final srt
  final_blocks = split_and_assign_translation(translated_batches)
  write_srt_file(final_blocks, "translated.srt")

  print("Translation complete. Output saved to translated.srt")

  # Step 4: Burn subtitles back to video
  burn_subtitles_to_video(input_video=input_video, srt_file="translated.srt", output_video=args.output )

if __name__ == "__main__":
    main()
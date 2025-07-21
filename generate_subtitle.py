import argparse  #define command line like --input
import subprocess #runs ffmpeg
import os
from transcriber import transcribe_audio
from translator import (
    group_subtitles,
    load_gemini_api_key,
    setup_gemini,
    translate_groups,
    translate_groups_deepseek,
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
  parser.add_argument('--input', nargs='+', required=True, help="path to input video file")
  parser.add_argument('--lang', default='English', help="target subtitle language")
  args = parser.parse_args()

  # Set up Gemini
  api_key = load_gemini_api_key()
  model = setup_gemini(api_key)

  for input_video in args.input:
        print(f"Processing video: {input_video}")
        base_name = os.path.splitext(os.path.basename(input_video))[0]
        audio_file = f"{base_name}_audio.aac"
        srt_file = f"{base_name}.srt"
        translated_srt = f"{base_name}_translated.srt"
        output_video = f"{base_name}-cn.mp4"

        # Step 1: Extract audio
        extract_audio(input_video, audio_file)

        # Step 2: Transcribe to .srt
        transcribe_audio(audio_file, lang=args.lang)

        # Step 3: Translate subtitles
        groups = group_subtitles(srt_file)
        print(f"Loaded {len(groups)} subtitle groups.")
        translated_batches = translate_groups(groups, model, target_lang="Chinese")
        #translated_batches = translate_groups_deepseek(groups, model_name="deepseek-r1:70b", target_lang="Chinese")
        final_blocks = split_and_assign_translation(translated_batches)
        write_srt_file(final_blocks, translated_srt)
        print("Translation complete.")

        # Step 4: Burn subtitles
        burn_subtitles_to_video(input_video, translated_srt, output_video)


if __name__ == "__main__":
    main()
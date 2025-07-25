import argparse  #define command line like --input
import subprocess #runs ffmpeg
import os
import shutil
import json
from datetime import datetime
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

def load_config(path="config.json"):
   with open(path, "r") as f:
      return json.load(f)

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

  # Load configuration
  config = load_config()
  prefix = config["user_id_prefix"]
  workspace_root = config["workspace_root"]
  final_output_path = config["final_output_path"]
  cleanup = config.get("cleanup_temp", True)

  # Set up Gemini
  api_key = load_gemini_api_key()
  model = setup_gemini(api_key)

  for input_video in args.input:
        # Generate unique workspace ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        task_id = f"{prefix}_{timestamp}"
        workspace_dir = os.path.join(workspace_root, task_id)
        os.makedirs(workspace_dir, exist_ok=True)
        print(f"\n[Workspace] Created: {workspace_dir}")

        # Copy input video to workspace
        input_base = os.path.basename(input_video)
        workspace_input = os.path.join(workspace_dir, input_base)
        shutil.copy2(input_video, workspace_input)

        # Build all paths
        base_name = os.path.splitext(input_base)[0]
        audio_file = os.path.join(workspace_dir, f"{base_name}_audio.aac")
        srt_file = os.path.join(workspace_dir, f"{base_name}.srt")
        translated_srt = os.path.join(workspace_dir, f"{base_name}_translated.srt")
        workspace_output = os.path.join(workspace_dir, f"{base_name}_cn.mp4")
        final_output_name = f"{task_id}-cn.mp4"
        final_output = os.path.join(final_output_path, final_output_name)

        print(f"[Start] Processing: {input_video}")
        # Step 1: Extract audio
        extract_audio(workspace_input, audio_file)
        # Step 2: Transcribe to .srt
        transcribe_audio(audio_file, lang=args.lang, output_srt_path=srt_file)

        # Step 3: Translate subtitles
        groups = group_subtitles(srt_file)
        print(f"Loaded {len(groups)} subtitle groups.")
        translated_batches = translate_groups(groups, model, target_lang="Chinese")
        #translated_batches = translate_groups_deepseek(groups, model_name="deepseek-r1:70b", target_lang="Chinese")
        final_blocks = split_and_assign_translation(translated_batches)
        write_srt_file(final_blocks, translated_srt)
        print("Translation complete.")

        # Step 4: Burn subtitles
        burn_subtitles_to_video(workspace_input, translated_srt, workspace_output)

        # Export final video
        os.makedirs(final_output_path, exist_ok=True)
        shutil.copy2(workspace_output, final_output)
        print(f"[Output] Final video exported to: {final_output}")

        # Cleanup
        if cleanup:
            shutil.rmtree(workspace_dir)
            print(f"[Cleanup] Removed temp workspace: {workspace_dir}")





if __name__ == "__main__":
    main()
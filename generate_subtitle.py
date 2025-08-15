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

# import database model and app context
from app import db, Upload, app


def load_config(path="project_files/config.json"):
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

def update_status(task_id, new_status):
   with app.app_context():
      task = db.session.get(Upload, task_id)
      if task:
         task.status = new_status
         db.session.commit()
  
def main():
  #create a command-line parser
  parser = argparse.ArgumentParser(description = "Generate subtitles for a video")
  parser.add_argument('--input', nargs='+', required=True, help="path to input video file")
  parser.add_argument('--lang', default='English', help="target subtitle language")
  parser.add_argument('--task_id', required=True, help="unique task ID from frontend")
  args = parser.parse_args()
  task_id = args.task_id

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
        # create workspace  
        workspace_dir = os.path.join(workspace_root, task_id)
        os.makedirs(workspace_dir, exist_ok=True)
        print(f"\n[Workspace] Created: {workspace_dir}")

        # Copy input video to workspace
        input_base = os.path.basename(input_video)
        workspace_input = os.path.join(workspace_dir, input_base)
        shutil.copy2(input_video, workspace_input)

        # Build all paths
        # Strip the task_id prefix from the filename if it starts with it
        if input_base.startswith(f"{task_id}-"):
          base_name = os.path.splitext(input_base[len(f"{task_id}-"):])[0]
        else:
          base_name = os.path.splitext(input_base)[0]
        audio_file = os.path.join(workspace_dir, f"{base_name}_audio.aac")
        srt_file = os.path.join(workspace_dir, f"{base_name}.srt")
        translated_srt = os.path.join(workspace_dir, f"{base_name}_translated.srt")
        workspace_output = os.path.join(workspace_dir, f"{base_name}_cn.mp4")
        final_output_name = f"{task_id}-{base_name}-cn.mp4"
        final_output = os.path.join(final_output_path, final_output_name)

        print(f"[Start] Processing: {input_video}")
        # Step 1: Extract audio
        update_status(task_id, "Extracting audio...")
        extract_audio(workspace_input, audio_file)
        # Step 2: Transcribe to .srt
        update_status(task_id, "Transcribing audio...")
        transcribe_audio(audio_file, lang=args.lang, output_srt_path=srt_file)

        # Step 3: Translate subtitles
        update_status(task_id, "Translating subtitles...")
        groups = group_subtitles(srt_file)
        print(f"Loaded {len(groups)} subtitle groups.")
        translated_batches = translate_groups(groups, model, target_lang="Chinese")
        #translated_batches = translate_groups_deepseek(groups, model_name="deepseek-r1:70b", target_lang="Chinese")
        final_blocks = split_and_assign_translation(translated_batches)
        write_srt_file(final_blocks, translated_srt)
        print("Translation complete.")

        # Step 4: Burn subtitles
        update_status(task_id, "Burning subtitles...")
        burn_subtitles_to_video(workspace_input, translated_srt, workspace_output)

        # Export final video
        update_status(task_id, "Finalizing output...")
        os.makedirs(final_output_path, exist_ok=True)
        shutil.copy2(workspace_output, final_output)
        print(f"[Output] Final video exported to: {final_output}")

        # Cleanup
        if cleanup:
            shutil.rmtree(workspace_dir)
            print(f"[Cleanup] Removed temp workspace: {workspace_dir}")

        update_status(task_id, "Completed")


if __name__ == "__main__":
    main()
import subprocess
import os
import shutil  # <-- needed to remove folder

# Map full language names to WhisperX-compatible codes
LANGUAGE_CODE_MAP = {
    "english": "en",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "russian": "ru",
    # Add more if needed
}

def transcribe_audio(audio_path, lang="English"):
    lang_code = LANGUAGE_CODE_MAP.get(lang.lower(), "en")
    base_name = os.path.splitext(os.path.basename(audio_path))[0].replace("_audio", "")
    output_dir = f"{base_name}_whisperx_output"

    print("Running WhisperX using subprocess...")

    command = [
        "whisperx",
        audio_path,
        "--model", "large-v3",
        "--language", lang_code,
        "--device", "cuda",
        "--output_format", "srt",
        "--output_dir", output_dir
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ WhisperX transcription failed.")
        print(result.stderr)
        return

    print("✅ WhisperX transcription complete.")

    original_audio_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_srt = os.path.join(output_dir, f"{original_audio_name}.srt")
    final_srt = f"{base_name}.srt"

    if os.path.exists(output_srt):
        os.rename(output_srt, final_srt)
        print(f"✅ SRT file saved as: {final_srt}")

        # Clean up the empty folder
        try:
            shutil.rmtree(output_dir)
            print(f"🧹 Removed temporary folder: {output_dir}")
        except Exception as e:
            print(f"⚠️ Failed to remove temp folder: {e}")
    else:
        print("❌ Expected SRT file not found.")
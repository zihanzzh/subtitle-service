import subprocess
import os

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

def transcribe_audio(audio_path, lang="English", output_srt_path=None):
    lang_code = LANGUAGE_CODE_MAP.get(lang.lower(), "en")

    # Determine workspace directory from output path
    if output_srt_path is None:
        raise ValueError("You must provide output_srt_path.")

    workspace_dir = os.path.dirname(os.path.abspath(output_srt_path))
    base_name = os.path.splitext(os.path.basename(audio_path))[0]

    print("Running WhisperX using subprocess...")

    command = [
        "whisperx",
        audio_path,
        "--model", "large-v3",
        "--language", lang_code,
        "--device", "cuda",
        "--output_format", "srt",
        "--output_dir", workspace_dir
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ WhisperX transcription failed.")
        print(result.stderr)
        return

    print("✅ WhisperX transcription complete.")

    # Rename the WhisperX output .srt to exact desired filename
    generated_srt = os.path.join(workspace_dir, f"{base_name}.srt")
    if os.path.exists(generated_srt):
        if generated_srt != output_srt_path:
            os.rename(generated_srt, output_srt_path)
        print(f"✅ SRT file saved as: {output_srt_path}")
    else:
        print("❌ Expected SRT file not found.")
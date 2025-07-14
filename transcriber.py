import subprocess

#transcribe audio using whisper, generate a .srt subtitle file
def transcribe_audio(audio_path, lang="English"):
    command = [
        "python3", "-m", "whisper",audio_path,"--model", "large-v3-turbo","--language", lang, "-f", "srt","--output_dir", "./"
    ]

    result = subprocess.run(command, capture_output=True)

    if result.returncode != 0:
        print("Transcription failed.")
        print(result.stderr.decode())
    else:
        print("Transcription completed.")
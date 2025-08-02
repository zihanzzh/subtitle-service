from flask import Flask, render_template, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import os
import time
import subprocess
import sys
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///subtitle_tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Upload Table Model
class Upload(db.Model):
    id = db.Column(db.String, primary_key=True)  # task_id
    original_filename = db.Column(db.String, nullable=False)
    final_filename = db.Column(db.String, nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    status = db.Column(db.String, default='Processing')
    language = db.Column(db.String, nullable=False)
    download_path = db.Column(db.String, nullable=False)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        video_file = request.files["video"]
        language = request.form.get("lang")

        # Generate task ID
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime()) + f"_{int(time.time() * 1000000) % 1000000}"
        task_id = f"user_{timestamp}"

        # Save video
        original_filename = secure_filename(video_file.filename)
        save_filename = f"{task_id}-{original_filename}"  
        save_path = os.path.join(UPLOAD_FOLDER, save_filename)
        video_file.save(save_path)

        print("✅ Video saved to:", save_path)
        print("🗣️ Language selected:", language)
        print("📁 Task ID:", task_id)

        # Run generate_subtitle.py
        try:
            subprocess.run(
                [sys.executable, "generate_subtitle.py", "--input", save_path, "--task_id", task_id],
                check=True
            )
            print("✅ Subtitle generation completed.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to run subtitle generation: {e}")

        # Extract output filename (same as input, but saved in outputs/)
        final_output_name = f"{task_id}-{original_filename[:-4]}-cn.mp4"  # remove .mp4 then add -cn.mp4

        # Record to database
        new_upload = Upload(
            id=task_id,
            original_filename=original_filename,
            final_filename=final_output_name,
            upload_time=datetime.now(timezone.utc),
            status="Completed", 
            language=language,
            download_path=final_output_name
        )
        db.session.add(new_upload)
        db.session.commit()

        return render_template("result.html", output_filename=final_output_name)
    
    return render_template("upload.html")

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("outputs", filename, as_attachment=True)



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
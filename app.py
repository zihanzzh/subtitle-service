from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        video_file = request.files["video"]
        language = request.form.get("lang")
        print("Uploaded:", video_file.filename)
        print("Selected language:", language)
        # We’ll process this in next steps
        return "Video uploaded successfully!"
    return render_template("upload.html")



if __name__ == "__main__":
    app.run(debug=True)
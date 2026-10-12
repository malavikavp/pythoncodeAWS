
import os
import uuid
from flask import Flask, render_template, request
import boto3
import pymysql
from werkzeug.utils import secure_filename

app = Flask(__name__)

BUCKET_NAME = os.environ.get("S3_BUCKET")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "admin")
DB_NAME = os.environ.get("DB_NAME", "studentdb")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

s3 = boto3.client("s3", region_name="ap-south-1")


def get_db_connection():
    if not all([DB_HOST, DB_USER, DB_NAME, DB_PASSWORD]):
        raise RuntimeError("Database environment variables are missing")

    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor
    )


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    course = request.form.get("course", "").strip()
    photo = request.files.get("photo")

    if not name or not email or not course or not photo:
        return "Please complete all fields and select a photo.", 400

    if not BUCKET_NAME:
        return "S3 bucket configuration is missing.", 500

    if not photo.filename:
        return "Please select a photo.", 400

    safe_name = secure_filename(photo.filename)
    object_key = f"students/{uuid.uuid4().hex}_{safe_name}"

    try:
        s3.upload_fileobj(
            photo,
            BUCKET_NAME,
            object_key,
            ExtraArgs={"ContentType": photo.mimetype or "application/octet-stream"}
        )

        # Store the S3 object URL. The bucket can remain private.
        photo_url = (
            f"https://{BUCKET_NAME}.s3.ap-south-1.amazonaws.com/{object_key}"
        )

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO students (name, email, course, photo_url)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (name, email, course, photo_url)
                )
            connection.commit()
        finally:
            connection.close()

        return "Student registered successfully!", 200

    except Exception:
        app.logger.exception("Student registration failed")
        return "Registration failed. Check the application logs.", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

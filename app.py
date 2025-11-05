# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (최종 안정판 - 완전형)
- 교수 페이지 정상 접근
- 학생/교수 권한 완전 분리
- 파일명 한글 정상 표시
- 질문 수정 시 기존 파일 보존 + 새 파일 추가
- dtype 및 인코딩 완전 안정화
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import pandas as pd
import os, re
from datetime import datetime

app = Flask(__name__)
app.secret_key = "key_flask_secret"

# ───────────── 경로 설정 ─────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")

# ───────────── CSV 로드/저장 ─────────────
def load_csv(path):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        except:
            df = pd.read_csv(path, encoding="utf-8", dtype=str)
    else:
        df = pd.DataFrame(columns=["id", "email", "content", "files", "date"])
    return df

def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")

# ───────────── 파일명 한글 보존 ─────────────
def safe_filename(filename):
    filename = os.path.basename(filename)
    # 영문 + 한글 + 괄호 + 공백 + 점 + 숫자 허용
    return re.sub(r'[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9._() ]', '', filename).strip()

# ───────────── 홈 (로그인) ─────────────
@app.route("/", methods=["GET", "POST"])
def home():
    message = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        allowed_file = os.path.join(BASE_DIR, "employed_allowed_emails.txt")

        if not os.path.exists(allowed_file):
            message = "⚠️ 이메일 등록 파일이 없습니다."
            return render_template("home.html", message=message)

        with open(allowed_file, "r", encoding="utf-8") as f:
            emails = [line.strip() for line in f if line.strip()]

        if not emails:
            message = "⚠️ 등록된 이메일이 없습니다."
            return render_template("home.html", message=message)

        professor_email = emails[0]
        student_emails = emails[1:]

        if email == professor_email:
            session["email"] = email
            session["role"] = "professor"
            flash("✅ 교수 계정으로 로그인되었습니다.", "success")
            return redirect(url_for("professor_page"))
        elif email in student_emails:
            session["email"] = email
            session["role"] = "student"
            flash("✅ 학생 계정으로 로그인되었습니다.", "success")
            return redirect(url_for("questions_page"))
        else:
            message = "❌ 등록되지 않은 이메일입니다."
    return render_template("home.html", message=message)

# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))

# ───────────── 교수 페이지 (메시지 작성/수정/삭제/게시확정) ─────────────
DATA_MESSAGES = os.path.join(BASE_DIR, "professor_messages.csv")

@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다. (교수 전용 페이지)", "danger")
        return redirect(url_for("questions_page"))

    df = load_csv(DATA_MESSAGES)
    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        if msg:
            new_row = pd.DataFrame([{
                "message": msg,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "confirmed": "no"
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            save_csv(DATA_MESSAGES, df)
            flash("📢 교수 메시지가 등록되었습니다.", "success")
        else:
            flash("⚠️ 메시지를 입력해주세요.", "warning")
        return redirect(url_for("professor_page"))

    return render_template("professor.html", email=session["email"], messages=df.to_dict("records"))


@app.route("/confirm_message/<int:index>", methods=["POST"])
def confirm_message(index):
    df = load_csv(DATA_MESSAGES)
    if 0 <= index < len(df):
        df.at[index, "confirmed"] = "yes"
        save_csv(DATA_MESSAGES, df)
        flash("✅ 게시가 확정되었습니다.", "success")
    return redirect(url_for("professor_page"))


@app.route("/edit_message/<int:index>", methods=["POST"])
def edit_message(index):
    df = load_csv(DATA_MESSAGES)
    if 0 <= index < len(df):
        df.at[index, "message"] = str(request.form.get("new_message", "").strip())
        df.at[index, "date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_csv(DATA_MESSAGES, df)
        flash("✏️ 메시지가 수정되었습니다.", "info")
    return redirect(url_for("professor_page"))


@app.route("/delete_message/<int:index>", methods=["POST"])
def delete_message(index):
    df = load_csv(DATA_MESSAGES)
    if 0 <= index < len(df):
        df = df.drop(index)
        df.reset_index(drop=True, inplace=True)
        save_csv(DATA_MESSAGES, df)
        flash("🗑️ 메시지가 삭제되었습니다.", "info")
    return redirect(url_for("professor_page"))



# ───────────── 질문 페이지 ─────────────
# ───────────── 질문 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)
    popup_msg = None   # ✅ 추가 (교수 메시지 팝업용)

    # 🔹 교수 메시지 CSV 중 confirmed='yes'인 최신 메시지 가져오기
    if os.path.exists(DATA_MESSAGES):
        msg_df = load_csv(DATA_MESSAGES)
        confirmed_msgs = msg_df[msg_df["confirmed"] == "yes"]
        if not confirmed_msgs.empty:
            popup_msg = confirmed_msgs.iloc[-1]["message"]

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        uploaded_files = request.files.getlist("files")
        saved_files = []
        for file in uploaded_files:
            if file and file.filename:
                filename = safe_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                saved_files.append(filename)
        files_str = ';'.join(saved_files)

        new_id = int(df["id"].max()) + 1 if not df.empty else 1
        new_row = pd.DataFrame([{
            "id": str(new_id),
            "email": email,
            "content": content,
            "files": files_str,
            "date": date
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("📘 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions_page"))

    return render_template(
        "questions.html",
        questions=df.to_dict("records"),
        email=session["email"],
        role=session["role"],
        popup_msg=popup_msg  # ✅ 추가
    )


# ───────────── 질문 수정 ─────────────
@app.route("/edit_question/<int:index>", methods=["POST"])
def edit_question(index):
    if "email" not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)
    if index < 0 or index >= len(df):
        flash("잘못된 접근입니다.", "danger")
        return redirect(url_for("questions_page"))

    if df.at[index, "email"] != session["email"] and session.get("role") != "professor":
        flash("⛔ 수정 권한이 없습니다.", "danger")
        return redirect(url_for("questions_page"))

    old_files = str(df.at[index, "files"]) if pd.notna(df.at[index, "files"]) else ""
    old_file_list = [f.strip() for f in old_files.split(";") if f.strip()]

    uploaded_files = request.files.getlist("files")
    new_file_list = []
    for file in uploaded_files:
        if file and file.filename:
            filename = safe_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            new_file_list.append(filename)

    merged_files = list(dict.fromkeys(old_file_list + new_file_list))
    files_str = ";".join(merged_files)

    df.at[index, "content"] = str(request.form.get("content", "").strip())
    df.at[index, "files"] = files_str
    df.at[index, "date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    save_csv(DATA_QUESTIONS, df)
    flash("✅ 질문이 수정되었습니다.", "success")
    return redirect(url_for("questions_page"))

# ───────────── 질문 삭제 ─────────────
@app.route("/delete_question/<int:index>", methods=["POST"])
def delete_question(index):
    if "email" not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)
    if index < 0 or index >= len(df):
        flash("잘못된 접근입니다.", "danger")
        return redirect(url_for("questions_page"))

    if df.at[index, "email"] != session["email"] and session.get("role") != "professor":
        flash("⛔ 삭제 권한이 없습니다.", "danger")
        return redirect(url_for("questions_page"))

    df = df.drop(index)
    df.reset_index(drop=True, inplace=True)
    save_csv(DATA_QUESTIONS, df)
    flash("🗑️ 질문이 삭제되었습니다.", "info")
    return redirect(url_for("questions_page"))

# ───────────── 파일 다운로드 ─────────────
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(
        UPLOAD_FOLDER,
        filename,
        as_attachment=True,
        download_name=filename.encode("utf-8").decode("latin1")
    )

# ───────────── 실행 ─────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

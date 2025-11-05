# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Final Stable Version)
- 교수: 메시지 등록/수정/삭제/게시 확정 (팝업 표시)
- 학생: 질문 등록/수정/삭제 (파일 유지 및 추가 가능)
- Render 환경 절대경로 대응 및 CSV 안정 저장
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import pandas as pd
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "key_flask_secret"

# ───────────── 경로 설정 ─────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_EMAILS = os.path.join(BASE_DIR, "employed_allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_MESSAGES = os.path.join(BASE_DIR, "professor_messages.csv")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ───────────── 유틸리티 함수 ─────────────
def load_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, encoding="utf-8")
        return df
    except Exception:
        df = pd.read_csv(path, encoding="utf-8-sig", on_bad_lines="skip")
        return df

def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")

def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        print(f"[⚠] 이메일 파일이 없습니다: {DATA_EMAILS}")
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

# ───────────── 이메일 로드 ─────────────
allowed_emails = load_allowed_emails()
professor_email = allowed_emails[0] if allowed_emails else None

# ───────────── 기본 페이지 ─────────────
@app.route("/", methods=["GET", "POST"])
def home():
    if not allowed_emails:
        flash("⚠ 이메일 등록 파일이 없습니다.", "danger")
        return render_template("home.html")

    if request.method == "POST":
        email = request.form["email"].strip()
        if email not in allowed_emails:
            flash("❌ 등록되지 않은 이메일입니다.", "danger")
            return render_template("home.html")

        session["email"] = email
        session["role"] = "professor" if email == professor_email else "student"

        if session["role"] == "professor":
            flash(f"✅ 교수 로그인 성공: {email}", "success")
            return redirect(url_for("professor_page"))
        else:
            flash(f"✅ 취업생 로그인 성공: {email}", "success")
            return redirect(url_for("questions_page"))

    return render_template("home.html")

# ───────────── 교수 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다. (교수 전용)", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_MESSAGES)
    if df.empty or "id" not in df.columns:
        df = pd.DataFrame(columns=["id", "content", "date", "status"])

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        edit_id = request.form.get("edit_id")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        if edit_id:  # 수정
            edit_id = int(edit_id)
            df.loc[df["id"] == edit_id, ["content", "date", "status"]] = [content, date, "pending"]
            flash("✏️ 메시지가 수정되었습니다. (다시 게시 확정 필요)", "info")
        else:  # 새 등록
            new_id = df["id"].max() + 1 if not df.empty else 1
            new_row = pd.DataFrame([{"id": new_id, "content": content, "date": date, "status": "pending"}])
            df = pd.concat([df, new_row], ignore_index=True)
            flash("💬 메시지가 등록되었습니다.", "success")

        save_csv(DATA_MESSAGES, df)
        return redirect(url_for("professor_page"))

    # 게시 확정 / 삭제 처리
    confirm_id = request.args.get("confirm")
    delete_id = request.args.get("delete")

    if confirm_id:
        confirm_id = int(confirm_id)
        df.loc[df["id"] == confirm_id, "status"] = "confirmed"
        save_csv(DATA_MESSAGES, df)
        flash("✅ 메시지가 게시되었습니다.", "success")
        return redirect(url_for("professor_page"))

    if delete_id:
        delete_id = int(delete_id)
        df = df[df["id"] != delete_id]
        save_csv(DATA_MESSAGES, df)
        flash("🗑️ 메시지가 삭제되었습니다.", "info")
        return redirect(url_for("professor_page"))

    return render_template("professor.html", messages=df.to_dict("records"))

# ───────────── 질문 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 접근 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)
    if df.empty or "id" not in df.columns:
        df = pd.DataFrame(columns=["id", "email", "content", "files", "date"])

    # ⚙ NaN 방지 (핵심 오류 해결)
    if "files" in df.columns:
        df["files"] = df["files"].fillna("").astype(str)

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        edit_id = request.form.get("edit_id")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        email = session["email"]

        filenames = []
        if "files" in request.files:
            for file in request.files.getlist("files"):
                if file.filename:
                    safe_name = secure_filename(file.filename)
                    path = os.path.join(UPLOAD_FOLDER, safe_name)
                    file.save(path)
                    filenames.append(safe_name)

        # 수정 시 기존 파일 유지 + 새 파일 추가
        if edit_id:
            edit_id = int(edit_id)
            if not df.empty and edit_id in df["id"].values:
                old_files = df.loc[df["id"] == edit_id, "files"].iloc[0]
                new_files = ";".join(filenames)
                combined = ";".join(filter(None, [old_files, new_files]))
                df.loc[df["id"] == edit_id, ["content", "files", "date"]] = [content, combined, date]
                flash("✏️ 질문이 수정되었습니다.", "info")
            else:
                flash("⚠ 수정 대상 질문을 찾을 수 없습니다.", "warning")
        else:
            new_id = df["id"].max() + 1 if not df.empty else 1
            new_row = pd.DataFrame([{
                "id": new_id,
                "email": email,
                "content": content,
                "files": ";".join(filenames),
                "date": date
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            flash("📘 질문이 등록되었습니다.", "success")

        save_csv(DATA_QUESTIONS, df)
        return redirect(url_for("questions_page"))

    # 삭제 처리
    delete_id = request.args.get("delete")
    if delete_id:
        delete_id = int(delete_id)
        df = df[df["id"] != delete_id]
        save_csv(DATA_QUESTIONS, df)
        flash("🗑️ 질문이 삭제되었습니다.", "info")
        return redirect(url_for("questions_page"))

    # 교수 메시지 팝업
    popup_msg = None
    msg_df = load_csv(DATA_MESSAGES)
    if not msg_df.empty and "status" in msg_df.columns:
        confirmed = msg_df[msg_df["status"] == "confirmed"]
        if not confirmed.empty:
            latest = confirmed.sort_values("date", ascending=False).iloc[0]
            popup_msg = latest["content"]

    return render_template("questions.html",
                           email=session["email"],
                           questions=df.to_dict("records"),
                           popup_msg=popup_msg)

# ───────────── 업로드된 파일 접근 ─────────────
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))

# ───────────── 메인 실행 ─────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

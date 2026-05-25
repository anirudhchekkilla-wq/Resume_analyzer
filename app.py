from flask import Flask, flash, render_template, request, session, redirect, send_file
import os
import io
from PyPDF2 import PdfReader
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = '12345'

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:pandu%402006@localhost/pr3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ------------------ ROLE SKILLS ------------------

ROLE_SKILLS = {
    "python developer": ["python", "flask", "sql", "django"],
    "web developer": ["html", "css", "javascript", "react"],
    "data analyst": ["python", "pandas", "excel", "sql"]
}

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ------------------ FUNCTIONS ------------------

def extract_text_from_pdf(file_path):

    text = ""

    try:
        reader = PdfReader(file_path)

        for page in reader.pages:
            text += page.extract_text() or ""

    except Exception as e:
        text = f"Error reading PDF: {e}"

    return text


def analyze_resume(text, role):

    text = text.lower()

    required_skills = ROLE_SKILLS.get(role, [])

    matched = []
    missing = []

    for skill in required_skills:

        if skill in text:
            matched.append(skill)

        else:
            missing.append(skill)

    # ---------------- SKILL SCORE ----------------

    skill_score = (
        (len(matched) / len(required_skills)) * 100
        if required_skills else 0
    )

    # ---------------- QUALITY CHECKS ----------------

    strengths = []
    issues = []

    if "@" in text:
        strengths.append("Email present")
    else:
        issues.append("Email missing")

    if any(char.isdigit() for char in text):
        strengths.append("Phone number present")
    else:
        issues.append("Phone number missing")

    if "project" in text:
        strengths.append("Projects section found")
    else:
        issues.append("No projects mentioned")

    if "skills" in text:
        strengths.append("Skills section present")
    else:
        issues.append("Skills section missing")

    if "education" in text:
        strengths.append("Education section present")
    else:
        issues.append("Education section missing")

    # ---------------- QUALITY SCORE ----------------

    quality_score = (len(strengths) / 5) * 100

    # ---------------- FINAL SCORE ----------------

    final_score = round(
        (skill_score * 0.7) + (quality_score * 0.3),
        2
    )

    return matched, missing, final_score, strengths, issues


def generate_suggestions(missing_skills):

    return [f"Learn {skill}" for skill in missing_skills]


# ------------------ MODELS ------------------

class User(db.Model):

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100))

    email = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(355),
        nullable=False
    )

    resumes = db.relationship(
        'Resume',
        backref='user',
        cascade="all, delete"
    )

    feedbacks = db.relationship(
        'Feedback',
        backref='user',
        cascade="all, delete"
    )


class Resume(db.Model):

    __tablename__ = 'resumes'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )

    file_name = db.Column(db.String(255))

    file_path = db.Column(db.String(255))

    extracted_text = db.Column(db.Text)

    upload_date = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )

    analyses = db.relationship(
        'AnalysisResult',
        backref='resume',
        cascade="all, delete"
    )


class AnalysisResult(db.Model):

    __tablename__ = 'analysis_results'

    id = db.Column(db.Integer, primary_key=True)

    resume_id = db.Column(
        db.Integer,
        db.ForeignKey('resumes.id'),
        nullable=False
    )

    job_role = db.Column(db.String(100))

    score = db.Column(db.Float)

    matched_skills = db.Column(db.Text)

    missing_skills = db.Column(db.Text)

    suggestions = db.Column(db.Text)

    quality_strengths = db.Column(db.Text)

    quality_issues = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )


class Feedback(db.Model):

    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id')
    )

    name = db.Column(db.String(100))

    email = db.Column(db.String(100))

    issue_type = db.Column(db.String(100))

    message = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )


# ------------------ ROUTES ------------------

@app.route('/')
def index():

    return render_template('index.html')


# ------------------ SIGNUP ------------------

@app.route('/signup', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # ❌ EMAIL EXISTS
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:

            flash(
                "Email already exists ❌",
                "danger"
            )

            return render_template('signup.html')

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        flash(
            "Account created successfully ✅ Please login",
            "success"
        )

        return redirect('/login')

    return render_template('signup.html')


# ------------------ LOGIN ------------------

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        # ❌ NO USER
        if not user:

            flash(
                "No user found with this email ❌",
                "danger"
            )

            return render_template('login.html')

        # ❌ WRONG PASSWORD
        if not check_password_hash(user.password, password):

            flash(
                "Invalid credentials ❌",
                "danger"
            )

            return render_template('login.html')

        # ✅ LOGIN SUCCESS
        session['user_id'] = user.id

        flash(
            "Login successful ✅",
            "success"
        )

        return redirect('/')

    return render_template('login.html')


# ------------------ LOGOUT ------------------

@app.route('/logout')
def logout():

    session.pop('user_id', None)

    return redirect('/login')

# ------------------ COMPARE ------------------

@app.route('/compare', methods=['GET', 'POST'])
def compare():

    if 'user_id' not in session:
        return redirect('/login')

    resumes = Resume.query.filter_by(
        user_id=session['user_id']
    ).all()

    result = None

    if request.method == 'POST':

        r1_id = request.form.get('resume1')

        r2_id = request.form.get('resume2')

        a1 = AnalysisResult.query.filter_by(
            resume_id=r1_id
        ).first()

        a2 = AnalysisResult.query.filter_by(
            resume_id=r2_id
        ).first()

        if a1 and a2:

            if a1.score > a2.score:

                result = (
                    f"Resume 1 wins with "
                    f"{a1.score}% 🎉"
                )

            elif a2.score > a1.score:

                result = (
                    f"Resume 2 wins with "
                    f"{a2.score}% 🎉"
                )

            else:

                result = "It's a Tie 🤝"

    return render_template(
        'compare.html',
        resumes=resumes,
        result=result
    )
# ------------------ UPLOAD ------------------

@app.route('/upload', methods=['GET', 'POST'])
def upload():

    if 'user_id' not in session:
        return redirect('/login')

    extracted_text = ""

    matched = []

    missing = []

    score = 0

    suggestions = []

    strengths = []

    issues = []

    if request.method == 'POST':

        role = request.form.get('role')

        user_id = session['user_id']

        file = request.files.get('resume')

        filename = None

        path = None

        # ❌ NO FILE + NO TEXT
        if (
            (not file or file.filename == "")
            and
            not request.form.get('resume_text')
        ):

            flash(
                "Please upload resume or paste resume text ❌",
                "danger"
            )

            return redirect('/upload')

        # ✅ FILE UPLOAD
        if file and file.filename != "":

            # ❌ INVALID FILE TYPE
            if not file.filename.lower().endswith('.pdf'):

                flash(
                    "Only PDF files are allowed ❌",
                    "danger"
                )

                return redirect('/upload')

            filename = file.filename.replace(" ", "_")

            path = os.path.join(
                app.config['UPLOAD_FOLDER'],
                filename
            )

            file.save(path)

            extracted_text = extract_text_from_pdf(path)

            # ❌ CORRUPTED PDF
            if "Error reading PDF" in extracted_text:

                flash(
                    "Inappropriate or corrupted PDF file ❌",
                    "danger"
                )

                return redirect('/upload')

            # ❌ VERY LESS TEXT
            if len(extracted_text.strip()) < 80:

                flash(
                    "PDF contains very little text ❌",
                    "danger"
                )

                return redirect('/upload')

            # ❌ RESUME CHECK
            text_lower = extracted_text.lower()

            resume_keywords = [
                "education",
                "skills",
                "experience",
                "projects",
                "internship",
                "certifications",
                "objective",
                "summary",
                "technical skills"
            ]

            matches_count = 0

            for keyword in resume_keywords:

                if keyword in text_lower:
                    matches_count += 1

            if matches_count < 3:

                flash(
                    "Uploaded PDF is not a resume ❌",
                    "danger"
                )

                return redirect('/upload')

        # ✅ MANUAL TEXT
        manual_text = request.form.get('resume_text')

        if manual_text:
            extracted_text = manual_text

        # ✅ ANALYZE
        if extracted_text and role:

            matched, missing, score, strengths, issues = analyze_resume(
                extracted_text,
                role
            )

            suggestions = generate_suggestions(missing)

            resume = Resume(
                user_id=user_id,
                file_name=filename,
                file_path=path,
                extracted_text=extracted_text
            )

            db.session.add(resume)
            db.session.commit()

            analysis = AnalysisResult(
                resume_id=resume.id,
                job_role=role,
                score=score,
                matched_skills=",".join(matched),
                missing_skills=",".join(missing),
                suggestions=",".join(suggestions),
                quality_strengths=",".join(strengths),
                quality_issues=",".join(issues)
            )

            db.session.add(analysis)
            db.session.commit()

            flash(
                "Resume uploaded successfully ✅ Check results in dashboard",
                "success"
            )

    return render_template(
        'upload.html',
        text=extracted_text,
        matched=matched,
        missing=missing,
        score=score,
        suggestions=suggestions,
        strengths=strengths,
        issues=issues
    )


# ------------------ DASHBOARD ------------------

@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    resumes = Resume.query.filter_by(
        user_id=session['user_id']
    ).all()

    data = []

    for resume in resumes:

        analysis = AnalysisResult.query.filter_by(
            resume_id=resume.id
        ).first()

        if analysis:

            data.append({

                "id": resume.id,

                "file_name": resume.file_name,

                "role": analysis.job_role,

                "score": analysis.score,

                "matched": analysis.matched_skills,

                "missing": analysis.missing_skills,

                "suggestions": analysis.suggestions,

                "strengths": analysis.quality_strengths,

                "issues": analysis.quality_issues,

                "date": resume.upload_date
            })

    return render_template(
        'dashboard.html',
        data=data
    )


# ------------------ DOWNLOAD PDF ------------------

@app.route('/download/<int:resume_id>')
def download(resume_id):

    if 'user_id' not in session:
        return redirect('/login')

    resume = Resume.query.get(resume_id)

    if not resume:

        flash(
            "Resume not found ❌",
            "danger"
        )

        return redirect('/dashboard')

    if resume.user_id != session['user_id']:

        flash(
            "Unauthorized ❌",
            "danger"
        )

        return redirect('/dashboard')

    analysis = AnalysisResult.query.filter_by(
        resume_id=resume_id
    ).first()

    if not analysis:

        flash(
            "Analysis not found ❌",
            "danger"
        )

        return redirect('/dashboard')

    data = {

        "role": analysis.job_role,

        "score": analysis.score,

        "matched": analysis.matched_skills,

        "missing": analysis.missing_skills,

        "suggestions": analysis.suggestions,

        "strengths": analysis.quality_strengths,

        "issues": analysis.quality_issues
    }

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    content = []

    content.append(
        Paragraph(
            "Resume Analysis Report",
            styles['Title']
        )
    )

    content.append(Spacer(1, 12))

    content.append(
        Paragraph(
            f"Role: {data['role']}",
            styles['Normal']
        )
    )

    content.append(
        Paragraph(
            f"Score: {data['score']}%",
            styles['Normal']
        )
    )

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            f"Matched Skills: {data['matched']}",
            styles['Normal']
        )
    )

    content.append(
        Paragraph(
            f"Missing Skills: {data['missing']}",
            styles['Normal']
        )
    )

    content.append(
        Paragraph(
            f"Suggestions: {data['suggestions']}",
            styles['Normal']
        )
    )

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            f"Strengths: {data['strengths']}",
            styles['Normal']
        )
    )

    content.append(
        Paragraph(
            f"Issues: {data['issues']}",
            styles['Normal']
        )
    )

    doc.build(content)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"report_{resume_id}.pdf",
        mimetype='application/pdf'
    )


# ------------------ FEEDBACK ------------------

@app.route('/feedback', methods=['POST'])
def feedback():

    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    fb = Feedback(

        user_id=user.id,

        name=user.name,

        email=user.email,

        issue_type=request.form.get('issue_type'),

        message=request.form.get('message')
    )

    db.session.add(fb)

    db.session.commit()

    flash(
        "Feedback submitted successfully ✅",
        "success"
    )

    return redirect('/dashboard')

# ------------------ DELETE RESUME ------------------

@app.route('/delete/<int:resume_id>')
def delete_resume(resume_id):

    if 'user_id' not in session:
        return redirect('/login')

    resume = Resume.query.get(resume_id)

    # ❌ Resume not found
    if not resume:

        flash("Resume not found ❌", "danger")

        return redirect('/dashboard')

    # ❌ Unauthorized access
    if resume.user_id != session['user_id']:

        flash("Unauthorized access ❌", "danger")

        return redirect('/dashboard')

    # ✅ Delete PDF file from uploads folder
    if resume.file_path and os.path.exists(resume.file_path):

        os.remove(resume.file_path)

    # ✅ Delete from database
    db.session.delete(resume)

    db.session.commit()

    flash("Resume deleted successfully ✅", "success")

    return redirect('/dashboard')


# ------------------ RUN ------------------

if __name__ == '__main__':

    app.run(debug=True)
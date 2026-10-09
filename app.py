import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gallery.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'กรุณาเข้าสู่ระบบเพื่อใช้งานส่วนนี้'

# --- ฐานข้อมูล (Database Models) ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, nullable=True, default='นักศึกษา / นักพัฒนาซอฟต์แวร์')
    projects = db.relationship('Project', backref='author', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tech_stack = db.Column(db.String(200), nullable=False)
    github_link = db.Column(db.String(255), nullable=True)
    image_file = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Routes ---
@app.route('/')
def index():
    query = request.args.get('q', '')
    if query:
        projects = Project.query.filter(
            (Project.title.contains(query)) | 
            (Project.tech_stack.contains(query)) |
            (Project.description.contains(query))
        ).all()
    else:
        projects = Project.query.order_by(Project.id.desc()).all()
    return render_template('index.html', projects=projects, query=query)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('ชื่อผู้ใช้นี้ถูกใช้งานแล้ว', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('อีเมลนี้ถูกใช้งานแล้ว', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('เข้าสู่ระบบสำเร็จ', 'success')
            return redirect(url_for('index'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ออกจากระบบเรียบร้อยแล้ว', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.email = request.form.get('email')
        current_user.bio = request.form.get('bio')
        db.session.commit()
        flash('อัปเดตข้อมูลโปรไฟล์เรียบร้อยแล้ว', 'success')
        return redirect(url_for('profile'))
    user_projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', user=current_user, projects=user_projects)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        tech_stack = request.form.get('tech_stack')
        github_link = request.form.get('github_link')
        file = request.files.get('file')

        if not file or file.filename == '':
            flash('กรุณาเลือกไฟล์รูปภาพผลงาน', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            project = Project(
                title=title,
                description=description,
                tech_stack=tech_stack,
                github_link=github_link,
                image_file=filename,
                author=current_user
            )
            db.session.add(project)
            db.session.commit()
            flash('เพิ่มผลงานเข้าสู่คลังเรียบร้อยแล้ว!', 'success')
            return redirect(url_for('index'))
        else:
            flash('รองรับเฉพาะไฟล์รูปภาพ (.png, .jpg, .jpeg, .gif, .webp)', 'danger')

    return render_template('upload.html')

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template('project_detail.html', project=project)

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.author != current_user:
        flash('คุณไม่มีสิทธิ์แก้ไขผลงานนี้', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        project.title = request.form.get('title')
        project.description = request.form.get('description')
        project.tech_stack = request.form.get('tech_stack')
        project.github_link = request.form.get('github_link')

        file = request.files.get('file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            project.image_file = filename

        db.session.commit()
        flash('แก้ไขข้อมูลผลงานเรียบร้อยแล้ว', 'success')
        return redirect(url_for('project_detail', project_id=project.id))

    return render_template('edit_project.html', project=project)

@app.route('/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.author != current_user:
        flash('คุณไม่มีสิทธิ์ลบผลงานนี้', 'danger')
        return redirect(url_for('index'))

    db.session.delete(project)
    db.session.commit()
    flash('ลบผลงานออกจากระบบเรียบร้อยแล้ว', 'success')
    return redirect(url_for('profile'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
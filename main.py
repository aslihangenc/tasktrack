from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import humanize

app = Flask(__name__)
app.config['SECRET_KEY'] = 'asla tahmin edemezsin'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    tasks = db.relationship('Task', backref='owner',
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.name}>'

    def get_task_status(self):
        total_tasks = len(self.tasks)
        if (total_tasks == 0):
            return "Başlamadı"

        completed_tasks = sum(task.completed for task in self.tasks)

        if completed_tasks == 0:
            return "Başlamadı"
        elif completed_tasks < total_tasks:
            return "Devam ediyor"
        else:
            return "Bitti"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    __tablename__ = 'task'
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(
        timezone.utc))
    date_posted = db.Column(db.DateTime, nullable=False,
                            default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id', ondelete='CASCADE'), nullable=False)
    completed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Task('{self.url}', '{self.due_date}', '{self.completed}')"


@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        task_content = request.form.get('task')

        if not task_content:
            flash('Görev içeriği boş olamaz!',
                  category='error')
        else:
            new_task = Task(
                content=task_content,
                due_date=datetime.now(timezone.utc),
                user_id=current_user.id
            )
            db.session.add(new_task)
            db.session.commit()
            flash('Görev başarıyla eklendi!', category='success')

    tasks = Task.query.filter_by(
        user_id=current_user.id).order_by(Task.id.desc()).all()
    return render_template('index.html', tasks=tasks, user=current_user)


@app.route('/get-tasks')
@login_required
def get_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': task.id,
        'content': task.content,
        'due_date': task.due_date,
        'completed': task.completed
    } for task in tasks])


@app.route('/toggle-complete-task', methods=['POST'])
@login_required
def toggle_complete_task():
    task_id = request.json.get('taskId')
    completed = request.json.get('completed')
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        task.completed = completed
        db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')

        user = User.query.filter_by(name=name).first()

        if user:
            if check_password_hash(user.password, password):
                flash('Başarıyla giriş yapıldı!', category='success')
                login_user(user, remember=True)

                if user.name == 'Admin':
                    return redirect(url_for('admin'))
                else:
                    return redirect(url_for('home'))
            else:
                flash('Yanlış şifre, tekrar deneyin.',
                      category='error')
        else:
            flash('Kullanıcı mevcut değil.', category='error')
    return render_template("login.html", user=current_user)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_name = request.form.get('new_name')
        new_email = request.form.get('new_email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        profile_by_email = User.query.filter_by(
            email=new_email).first()
        profile_by_name = User.query.filter_by(
            name=new_name).first()

        if new_email != current_user.email:
            profile_by_email = User.query.filter_by(email=new_email).first()
            if profile_by_email:
                flash('Bu e-posta zaten var.', category='error')
                
        if new_name != current_user.name:
            profile_by_name = User.query.filter_by(name=new_name).first()    
            if profile_by_name:
                flash('Bu isim zaten var.', category='error')
                
        if new_password != confirm_password:
            flash('Şifreler eşleşmiyor.', category='error')
        else:
            current_user.name = new_name
            current_user.email = new_email
            if new_password and new_password == confirm_password:
                current_user.password = generate_password_hash(new_password)
            db.session.commit()

            flash('Profil bilgileri güncellendi!', category='success')
            return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        user_by_email = User.query.filter_by(
            email=email).first()
        user_by_name = User.query.filter_by(
            name=name).first()

        if user_by_email:
            flash('Bu e-posta zaten var.', category='error')
        elif user_by_name:
            flash('Bu isim zaten var.', category='error')
        elif password1 != password2:
            flash('Şifreler eşleşmiyor.', category='error')
        else:
            new_user = User(name=name, email=email,
                            password=generate_password_hash(password1))
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user, remember=True)
            flash('Hesap oluşturuldu!', category='success')
            return redirect(url_for('login'))

    return render_template('register.html', title='Kayıt Ol', form_title='Kayıt Ol', button_text='Kayıt Ol')


@app.route('/admin')
@login_required
def admin():
    if current_user.name != 'Admin':
        flash('Bu sayfayı görüntüleme yetkiniz yok.', category='error')
        return redirect(url_for('home'))

    users = User.query.all()
    return render_template('admin.html', users=users, user=current_user)


@app.route('/admin/delete-user', methods=['POST'])
@login_required
def delete_user():
    if current_user.name != 'Admin':
        flash('Bu işlemi yapma yetkiniz yok.', category='error')
        return redirect(url_for('admin'))

    user_id = request.form.get('user_id')
    user_to_delete = User.query.get(user_id)

    if user_to_delete:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash('Kullanıcı başarıyla silindi!', category='success')
    else:
        flash('Kullanıcı bulunamadı veya silinemedi.', category='error')

    return redirect(url_for('admin'))


@app.route('/admin/new-user', methods=['GET', 'POST'])
@login_required
def new_user():
    if current_user.name != 'Admin':
        flash('Bu işlemi yapma yetkiniz yok.', category='error')
        return redirect(url_for('admin'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        user_by_email = User.query.filter_by(email=email).first()
        user_by_name = User.query.filter_by(name=name).first()

        if user_by_email:
            flash('Email zaten var.', category='error')
        elif user_by_name:
            flash('Kullanıcı adı zaten var.', category='error')
        elif password1 != password2:
            flash('Şifreler eşleşmiyor.', category='error')
        else:
            new_user = User(name=name, email=email,
                            password=generate_password_hash(password1))
            db.session.add(new_user)
            db.session.commit()

            flash('Kullanıcı hesabı oluşturuldu!', category='success')
            return redirect(url_for('admin'))

    return render_template('register.html', title='Yeni Kullanıcı', form_title='Yeni Kullanıcı Ekle', button_text='Kullanıcı Ekle', user=current_user)


@app.route('/admin/user/<int:user_id>')
@login_required
def user_tasks(user_id):
    if current_user.name != 'Admin':
        flash('Bu sayfayı görüntüleme yetkiniz yok.', category='error')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)
    tasks = Task.query.filter_by(user_id=user.id).all()
    return render_template('user_tasks.html', user=user, tasks=tasks)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/new-task', methods=['GET', 'POST'])
@login_required
def new_task():
    users = User.query.all()

    if request.method == 'POST':
        content = request.form['content']
        due_date_str = request.form['due_date']
        assignee_id = request.form.get('assignee_id')

        user_id = current_user.id

        if not content:
            flash('Görevleri yazın', category='error')
        elif not assignee_id:
            flash('Görev atananını seçin', category='error')
        else:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                flash('Geçersiz tarih formatı', category='error')
                return redirect(url_for('new_task'))

            tasks = content.split('\n')

            for task_content in tasks:
                if task_content.strip():
                    task = Task(
                        content=task_content.strip(), due_date=due_date,
                        user_id=assignee_id
                    )
                    db.session.add(task)

            db.session.commit()
            flash('Görevler başarıyla oluşturuldu!', category='success')
            return redirect(url_for('admin'))

    return render_template('new-task.html', users=users)


@app.route('/delete-task', methods=['POST'])
@login_required
def delete_task():
    task_id = request.json.get('taskId')
    task = Task.query.get(task_id)
    if task and (task.user_id == current_user.id or current_user.name == 'Admin'):
        db.session.delete(task)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'fail'})


@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('server_error.html'), 500


@app.route('/test-server-error')
def test_server_error():
    return render_template('server_error.html'), 500


@app.context_processor
def utility_processor():
    return dict(humanize=humanize)


if __name__ == '__main__':
    app.run(debug=True)

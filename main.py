from flask import Flask, render_template, redirect, url_for, flash, abort
from flask import request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import BadRequestKeyError
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_gravatar import Gravatar
import os

from forms import CreatePostForm, CreateUserForm, LoginForm, CommentForm

app = Flask(__name__)
# app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# CONFIGURE LOGIN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
                    base_url=None)



def forbidden():
    return abort(403)


def admin_only(func):
    def wrapper(*args, **kwargs):
        try:
            print(current_user.id)
            if current_user.id == 1:
                return func(*args, **kwargs)
            else:
                return forbidden()
        except AttributeError as ae:
            print(ae)
            return forbidden()

    wrapper.__name__ = func.__name__
    return wrapper


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    name = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), unique=False, nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    post = relationship("BlogPost", back_populates="comments")


db.create_all()
db.session.commit()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = CreateUserForm()
    if register_form.validate_on_submit():
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            # User already exists
            # Will redirect with 'email' argument.
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login', email=email))

        hash_and_salted_password = generate_password_hash(
            request.form.get('password'),
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=request.form.get('email'),
            name=request.form.get('name'),
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=register_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """
        When were redirected from 'registered' method (i.e. user's we tried to register email exists in DB)
        we come here with arg 'email' set. We'll preset 'email' form field.
        Otherwise, it is a plain 'login' route. No preset.
    """
    try:
        email = request.args['email']
        login_form = LoginForm(email=email)
    except BadRequestKeyError:
        login_form = LoginForm()
    if login_form.validate_on_submit():
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        hash_and_salted_password = generate_password_hash(
            request.form.get('password'),
            method='pbkdf2:sha256',
            salt_length=8
        )
        # Email doesn't exist or password incorrect.
        if not user:
            flash("That email does not exist, please try again.")
            return render_template("login.html", form=login_form)
        elif not check_password_hash(user.password, request.form.get('password')):
            flash('Password incorrect, please try again.')
            return render_template("login.html", form=login_form)
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", form=login_form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    logged_in = current_user.is_authenticated
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    if not logged_in:
        flash("Please login to leave a comment!")
        return render_template("post.html", post=requested_post, comment_form=comment_form)
    if comment_form.validate_on_submit():
        comment = Comment(
            text=comment_form.comment.data,
            author_id=current_user.id,
            post_id=post_id
        )
        db.session.add(comment)
        db.session.commit()
        comment_form.comment.data = ""
    return render_template("post.html", post=requested_post, comment_form=comment_form)



@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author.name,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author_id = current_user.id
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

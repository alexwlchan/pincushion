# -*- encoding: utf-8
"""
Contains helpers for implementing security around the search wrapper.

These are intended to be single-user applications, so this implements a
single-user login page.  You provide a password, and users need to provide
that password before they can access the rest of the site.
"""

import datetime as dt

import attr
from flask import abort, render_template, redirect, request, session
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField
from wtforms.validators import DataRequired


def configure_login(app, password):
    """
    Adds login capabilities to a Flask app, if desired.
    """
    login_manager = LoginManager()
    login_manager.init_app(app)

    class LoginForm(FlaskForm):
        password = PasswordField('password', validators=[DataRequired()])

    @attr.s
    class User:
        password = attr.ib()

        is_active = True
        is_anonymous = False

        @property
        def is_authenticated(self):
            return self.password == password

        def get_id(self):
            return 1

    @login_manager.user_loader
    def load_user(user_id):
        return User(password=password)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            user = User(form.data['password'])
            if not user.is_authenticated:
                return abort(401)

            session['logged_in'] = True
            login_user(user, remember=True, duration=dt.timedelta(days=365))
            return redirect('/')
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect('/')

    @app.errorhandler(401)
    def page_forbidden(error):
        message = (
            "The server could not verify that you are authorized to access "
            "the URL requested. You either supplied the wrong credentials "
            "(e.g. a bad password), or your browser doesn't understand how to "
            "supply the credentials required."
        )
        return render_template(
            'error.html',
            title='401 Not Authorized',
            message=message), 401

    @app.before_request
    def check_valid_login():
        login_valid = session.get('logged_in')

        if (
            request.endpoint and
            'static' not in request.endpoint and
            request.endpoint != 'login' and
            not login_valid
        ):
            return redirect('/login')

import os
from re import M
import re
from flask import Flask, render_template, request, url_for, session
from functools import wraps
from flask.helpers import flash
from flask_mysqldb import MySQL
from werkzeug.utils import redirect, secure_filename
import yaml
from datetime import datetime

app = Flask(__name__, static_folder='static')


db = yaml.safe_load(open('db.yaml'))

app.config['MYSQL_HOST'] = db['mysql_host']
app.config['MYSQL_USER'] = db['mysql_user']
app.config['MYSQL_PASSWORD'] = db['mysql_password']
app.config['MYSQL_DB'] = db['mysql_db']
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

app.config['UPLOAD_FOLDER'] = 'static/uploads/'

mysql = MySQL(app)

@app.route('/')
def startpage():
    return render_template('start.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        client_details = request.form

        login_id = client_details['login_id']
        name = client_details['name']
        password = client_details['password']

        if login_id == '' or password == '' or name == '':
            flash('No input detected','message')
            return render_template('register.html')

        cur = mysql.connection.cursor()
        
        cur.execute("SELECT * FROM clients WHERE login_id = %s", [login_id])
        result = cur.fetchone()

        if result == 0:
            cur.execute("INSERT INTO clients(name, login_id, password) VALUES (%s, %s, %s)", (name, login_id, password))
            mysql.connection.commit()
        else:
            flash('Please choose a different Login ID, already taken')
            return render_template("register.html")
        
        cur.close()
        return redirect('/')

    return render_template("register.html") 

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        login_details = request.form

        login_id = login_details['login_id']
        password_entered = login_details['password']

        if login_id == '' or password_entered == '':
            flash('No input detected', 'message')
            return render_template('login.html')

        cur = mysql.connection.cursor()

        result = cur.execute("SELECT * FROM clients WHERE login_id = %s", [login_id])
        if result > 0:
            details = cur.fetchone()
            password = details['password']

            if password == password_entered:
                session['logged_in'] = True
                session['login_id'] = login_details['login_id']
                session['is_admin'] = False
                session['client_id'] = details['client_id']

                return redirect(url_for('homepage'))

        else:
            flash('Incorrect password or id', 'message')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/login/admin', methods=['GET','POST'])
def login_admin():
    if request.method == 'POST':
        login_details = request.form

        login_id = login_details['login_id']
        password_entered = login_details['password']

        if login_id == '' or password_entered == '':
            flash('No input detected', 'message')
            return render_template('login.html')

        cur = mysql.connection.cursor()

        result = cur.execute("SELECT * FROM admin WHERE login_id = %s", [login_id])
        if result > 0:
            details = cur.fetchone()
            password = details['password']

            if password == password_entered:
                session['logged_in'] = True
                session['login_id'] = login_details['login_id']
                session['is_admin'] = True
                result = cur.execute("SELECT * FROM admin WHERE login_id = %s", [login_id])
                if result > 0:
                    details = cur.fetchone()
                    session['admin_id'] = details['admin_id']

                return redirect(url_for('homepage'))
        else:
            flash('Incorrect password or id', 'message')
            return render_template('login_admin.html')

    return render_template('login_admin.html')

def check_logged_in(arg):
    @wraps(arg)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return arg(*args, **kwargs)
        else:
            flash('Log in or Register please', 'message')
            return redirect('/')
    return wrap

@app.route('/logout')
@check_logged_in
def logout():
    session.clear()
    return redirect(url_for('startpage'))  

@app.route('/home')
@check_logged_in
def homepage():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM videos ORDER BY upload_date DESC")
    videos = cur.fetchall()

    if result > 0:
        return render_template('home.html', videos=videos)
    else:
        flash('No videos to display', 'message')
        cur.close()
        return render_template('home.html')

@app.route('/upload_video', methods=['POST'])
@check_logged_in
def upload_video(): 
    if 'file' not in request.files:
        flash('No file')
        return redirect('/home')
    
    file = request.files['file']
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    title = request.form
    title = title['title']
    uploader_id = session['client_id']
    date_uploaded = datetime.now()
    login_id = session['login_id']

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO videos(title, uploader_id, upload_date, filename, login_id) VALUES (%s, %s, %s, %s, %s)", (title, uploader_id, date_uploaded, filename, login_id))
    mysql.connection.commit()
    cur.close()

    return render_template('profile.html', login_id=session['login_id'], filename=filename)

@app.route('/search', methods=['POST'])
@check_logged_in
def search():
    search = request.form
    search_request = search['search']
    search_request = search_request.split(" ")
    videos = ()

    if search_request == "":
        flash('Please enter search parameters')
        return redirect(url_for('homepage'))

    cur = mysql.connection.cursor()
    for i in range(len(search_request)):
        search_request[i] = "%" + search_request[i] + "%"
        cur.execute("SELECT * FROM videos WHERE title LIKE %s OR login_id LIKE %s ORDER BY upload_date DESC", (search_request[i], search_request[i]))
        result = cur.fetchall()
        videos = videos + result
    cur.close()

    if videos == ():
        flash('No search results found')
        return redirect(url_for('homepage'))

    return render_template('home.html', videos=videos)

@app.route('/display_video/<filename>')
@check_logged_in
def display_video(filename):
    return redirect(url_for('static', filename='uploads/' + filename), code=301)

@app.route('/video/<video_id>')
@check_logged_in
def video(video_id):
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM videos WHERE video_id = %s", [video_id])
    video_details = cur.fetchone()
    cur.close()
    
    return render_template('video.html', video_details=video_details)

@app.route('/profile/<login_id>')
@check_logged_in
def profile(login_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM videos WHERE login_id = %s", [login_id])
    videos = cur.fetchall()
    cur.close()

    return render_template('profile.html', login_id=login_id, videos=videos)

@app.route('/like/<video_id>')
@check_logged_in
def like(video_id):
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM videos WHERE video_id = %s", [video_id])
    video_details = cur.fetchone()
    
    likes = video_details['num_likes']
    likes+=1

    result_likes = cur.execute("SELECT * FROM likes WHERE client_id = %s AND video_id = %s", ([session['client_id']], [video_id]))
    if result_likes == 0:
        cur.execute("UPDATE videos SET num_likes = %s WHERE video_id = %s", (likes, video_id))
        cur.execute("INSERT INTO likes(video_id, client_id) VALUES (%s, %s)", (video_id, session['client_id']))
        mysql.connection.commit()
        flash('Liked video')
    else:
        likes-=2
        cur.execute("UPDATE videos SET num_likes = %s WHERE video_id = %s", (likes, video_id))
        cur.execute("DELETE FROM likes WHERE video_id = %s AND client_id = %s", (video_id, session['client_id']))
        mysql.connection.commit()
        flash('Unliked video')

    cur.close()

    return redirect(url_for('video', video_id=video_details['video_id']))

@app.route('/subscribe/<client_id>/<video_id>')
@check_logged_in
def subscribe(client_id, video_id):
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM clients WHERE client_id = %s", [client_id])
    client_details = cur.fetchone()
    
    result_vid = cur.execute("SELECT * FROM videos WHERE video_id = %s", [video_id])
    video_details = cur.fetchone()

    subscribers = client_details['num_subs']
    subscribers+=1

    result_subs = cur.execute("SELECT * FROM subscribers WHERE client_id = %s AND subscriber_id = %s", ([client_id], [session['client_id']]))
    if result_subs == 0:
        cur.execute("UPDATE clients SET num_subs = %s WHERE client_id = %s", (subscribers, client_id))
        cur.execute("INSERT INTO subscribers(client_id, subscriber_id) VALUES (%s, %s)", ([client_id], [session['client_id']]))
        mysql.connection.commit()

    cur.close()
    flash("Subscribed")

    return redirect(url_for('video', video_id=video_details['video_id']))


def check_is_admin(arg):
    @wraps(arg)
    def wrap(*args, **kwargs):
        if 'is_admin' in session:
            return arg(*args, **kwargs)
        else:
            flash('You do not have admin access', 'message')
            return redirect('/')
    return wrap

@app.route('/admin/delete/<video_id>')
@check_logged_in
@check_is_admin
def delete(video_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM videos WHERE video_id = %s", [video_id])
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('homepage'))

@app.route('/user/delete/<video_id>')
@check_logged_in
def delete_video(video_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM videos WHERE video_id = %s", [video_id])
    result = cur.fetchone()
    client_id = result['uploader_id']

    if client_id == session['client_id']:
        cur.execute("DELETE FROM videos WHERE video_id = %s", [video_id])
        mysql.connection.commit()
        flash('Video removed successfully')

    cur.close()

    return redirect(url_for('profile', login_id=session['login_id']))

@app.route('/ban/<client_id>')
@check_logged_in
@check_is_admin
def ban(client_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM clients WHERE client_id = %s", [client_id])
    cur.execute("INSERT INTO banned_users(admin_id, client_id) VALUES (%s, %s)", (session['admin_id'], session['client_id']))
    mysql.connection.commit()
    cur.close()
    
    return redirect(url_for('homepage'))

if __name__ == "__main__":
    app.secret_key = "WBDJSBALFkjdabd"
    app.run(debug=True)
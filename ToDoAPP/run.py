#dependencies
from flask import Flask, render_template, request, session, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import time as time
import pandas as pd
from plyer import notification
import hashlib
import base64
from password_strength import PasswordPolicy
from celery import Celery
from twilio.rest import Client
import re
import random
import threading



app = Flask(__name__)
app.secret_key="Hello"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'



#twilioconfig
account_sid = 'yur-sid-here'
auth_token = 'your-auth-token-here'
client = Client(account_sid, auth_token)
celery = Celery(app.name, broker='redis://localhost:6379/0')




#database creation
db = SQLAlchemy(app)
with app.app_context():
        db.create_all()
        
        
        
#User model to store username and pass
class User(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    username = db.Column(db.String(50), unique= True, nullable= False)
    password = db.Column(db.String(50), nullable= False)
    u_key = db.Column(db.String(10),unique= True , nullable= False)
    tasks = db.relationship('Task', backref= 'user', lazy= True)
    notes = db.relationship('Notes', backref= 'user', lazy= True)
    phoneno = db.Column(db.String(13), nullable=False)
    verified = db.Column(db.Integer, default=0)         #default to 0 if not verified , verified = 1
        
#Task table
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    priority = db.Column(db.Integer, nullable=False)
    taskname = db.Column(db.String(100), nullable=False)
    datetime_scheduled = db.Column(db.DateTime, nullable=False)
    done = db.Column(db.Integer, default=0)
    M_sent =db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    typeoftask = db.Column(db.String(100), nullable=False)

#Notes table
class Notes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50), nullable=False)
    note = db.Column(db.String(1000))
    datetaken = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

#Project Page
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    users = db.relationship('User', secondary='user_project_association', backref='projects')
    chats = db.relationship('Chat', backref='project', lazy=True)

class UserProjectAssociation(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), primary_key=True)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(500), nullable=False)
    sent_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)



#passwordchecker
policy = PasswordPolicy.from_names(
    length=8, 
    uppercase=1,  
    numbers=1,  
    special=1, 
    nonletters=1,
)
#if policy is not empty->password-fail


def is_valid_phone_number(number):
    # Remove all non-digit characters from the phone number
    number = re.sub('[^0-9]', '', number)
    if len(number) == 10:
        return True
    else:
        return False
    


    
#SignIn block
@app.route('/', methods=('GET','POST'))
def home():
    
    session['current_url'] = request.url
    session['a'] = 0 #erroridentifier 
    
    if request.method == "POST":
        if "bsignin" in request.form and ((len(request.form['username']) == 0 and len(request.form['password']) == 0) ):
            session['a'] = 14
            return redirect('/error')

        elif "bsignin" in request.form and (len(request.form['username']) < 1 or len(request.form['password']) < 1) :
            session['a'] = 14
            return redirect('/error')
        
        elif "bsignin" in request.form:
            username = request.form['username']
            password = request.form['password']
            user_db = User.query.filter_by(username=username).first()
            if user_db and password == user_db.password:
                session['username'] = username
                session['password'] = password
                
                session['bg_img'] = 'Light.png' #default bg
                
                notification.notify(
                    title='Login Success',
                    message='You have successfully logged in as '+"\""+username+"\"",
                    app_name='My Flask App',
                    app_icon='app_icons/ToDo2.ico',
                )
                return redirect('/homepage/alltask')
            else:
                session['a'] = 1
                return redirect('/error')
            
        elif "bsignup" in request.form:
            return redirect('/signup')
        else:
            session['a'] = 0
            return redirect('/error')
    else:    
        return render_template('login.html')






#Error Message
@app.route('/error',methods=('GET','POST'))
def Error():
          
    ab = session['a']
        
    err = [ "empty",                                               #default = 0
            "Invalid Username or Password",                         #1   
            "Username Doesn't Exists",                              #2
            "Old Password And New Password Are Similar",            #3
            "Incomplete Entry",                                     #4
            "Referred User Does not Exist",                         #5
            "Invalid Password Length \n Passowrd Must Consist of : \n Length=8, Uppercase=1, Numbers=1, Special Characters=1, Non Letters=1",    #6
            "Username Already Exists",                              #7
            "Passowrds Do not match",                               #8
            "Min Task Name Length : 3",                             #9
            "Min Project Name Length : 3",                          #10
            "Username can't be empty",                              #11
            "Notes Title, minimum length : 3",                      #12
            "Invalid Username or Password or Unique-Key",           #13
            "Empty Username or Password field",                     #14
          ]
    
    error = err[ab]
    
    if request.method == "POST":
        if "goback" in request.form:
            return redirect(session['current_url'])
    else:
        return render_template('error.html',error=error)



#SignUp Tab
@app.route('/signup', methods=('GET','POST'))
def signu():

    db.create_all()
    
    session['current_url'] = request.url
    
    if "BtnSubmit" in request.form and len(policy.test(request.form['password1']))!=0:
        session['a'] = 6
        return redirect('/error')
    elif "BtnSubmit" in request.form and len(request.form['username']) < 1 :
        session['a'] = 11
        return redirect('/error')
    elif "BtnSubmit" in request.form and (len(request.form['username']) < 1 or len(request.form['password1']) < 1) :
        session['a'] = 14
        return redirect('/error')
    
    
    elif "BtnSubmit" in request.form and (request.form['password1'] == request.form['password2']) and len(request.form['username']) > 0 and len(policy.test(request.form['password1'])) == 0  :
        username=request.form['username']
        password=request.form['password1']
        phone_number=request.form['phone_number']
        existing_user = User.query.filter_by(username=username).first()
        
        if existing_user :
            session['a'] = 7
            return redirect('/error')
        else:
            current_time = str(int(time.time()*1000))
            key_string = username + password + current_time
            keyobj = hashlib.sha256(key_string.encode())
            key = keyobj.digest()
            u_key = base64.urlsafe_b64encode(key).decode()[:10]
            
            new_user = User(username=username, password=password,u_key=u_key,phoneno=phone_number)
            db.session.add(new_user)
            db.session.commit()
            
            notification.notify(
                title='Sign Up Success',
                message='Successfully Signed Up as '+"\""+username+"\"",
                app_name='ToDo',
                app_icon='app_icons/ToDo2.ico',
            )     
            return redirect('/')
    elif 'BtnSignIn' in request.form:
        return redirect('/')
    else:
        return render_template("signup.html")


#alltask-Remaining task
@app.route('/homepage/alltask', methods=['GET', 'POST'])
def homepage():
 
    db.create_all()
    name = session['username']
    user = User.query.filter_by(username=name).first()
    tasks = Task.query.filter_by(user_id=user.id,done=0).order_by(Task.datetime_scheduled, Task.priority).all()
    Totaltask = Task.query.filter_by(user_id=user.id).all()
    
    LenTaskDone = len(tasks)
    LenTotalTask = len(Totaltask)
    
    session['LenTotalTask'] = LenTotalTask
    session['flagT']=False
    
    
    if session['flagT']==False and user.verified == 1:
        session['flagT']=True
        t = threading.Thread(target=start_task_scheduler, args=(session['username'],))
        t.start()  
        
    
     
    '''if 'beat_schedule_updated' not in session:
        user_id = user.id
        celery.conf.beat_schedule = {
            f'send-reminder-sms-{user_id}': {
                'task': 'send_reminder_sms',
                'schedule': timedelta(minutes=1),
                'args': (user_id,)
            }
        }
        celery.conf.timezone = 'Asia/Kolkata'
        session['beat_schedule_updated'] = True
        print("Beat schedule updated for user:", user_id)'''
    
    
    if LenTotalTask == 0 or LenTotalTask < 0:
        progress =0
    elif LenTotalTask > 0 :
        progress = 100 - int((LenTaskDone / LenTotalTask) * 100)
    else: 
        progress = 0
    

    
    # Get the current month from the session or default to the current month
    current_date = datetime.now().strftime("%B %d, %Y")
    
    
    if "createtask" in request.form:
        return redirect('/homepage/createtask')  
    elif 'categories' in request.form:
        return redirect('/categories') 
    elif 'alltasks' in request.form:
        return redirect('/homepage/totaltask')  
    elif 'notes' in request.form:
        return redirect('/homepage/notes')  
    elif 'projects' in request.form:
        return redirect('/homepage/project')
    elif 'settings' in request.form:
        return redirect('/settings')
    elif 'UploadExcel' in request.form and request.files['file'] is None:
        session['a'] = 15
        return redirect('/error')
        
        
    #excel to database    
    elif 'UploadExcel' in request.form:    
        file = request.files['file']
        if file is None:
            session['a'] = 15 
            return redirect('/error')
        
        df = pd.read_excel(file)
        print(df)
        user_id = user.id
        for index, column in df.iterrows():
            taskname = column['taskname']
            priority = column['priority']
            datetime_scheduled = column['datetime']
            typeoftask = column['typeoftask']
 
            if taskname is None or priority is None or datetime_scheduled is None:
                session['a'] = 16
                return redirect('/error')
            
            print(taskname)
            print(priority)
            print(datetime_scheduled)
            new_task = Task(taskname=taskname, priority=priority, datetime_scheduled=datetime_scheduled, typeoftask=typeoftask ,user_id=user_id)
            db.session.add(new_task)
            db.session.commit()
            
        notification.notify(
            title='Tasks Added',
            message="Added tasks through Excel file",
            app_name='ToDo',
            app_icon='app_icons/ToDo2.ico',
        ) 
        
        return redirect('/homepage/alltask')
    
    elif 'logout' in request.form:
        session.clear()
        return redirect('/')  
    else:
        pass
    
    
    return render_template('alltasks.html', 
                           current_date=current_date,
                           progress_percentage=progress, 
                           today_day=datetime.now().day, usr=name,
                           Total_tasks=session['LenTotalTask'], 
                           tasks=tasks, LenTotalTask=LenTotalTask,
                           LenTaskDone=LenTaskDone, 
                           bg_img=session['bg_img'])


'''def send_notification(taskname):
    notification.notify(
        title='Task Reminder',
        message=f'Task "{taskname}" is due soon!',
        app_name='ToDo',
        app_icon='app_icons/ToDo2.ico',
    )'''



@app.route('/homepage/createtask', methods=['GET', 'POST'])
def createtask(): 
    

    
    session['current_url'] = request.url
    
    if "currenttasks" in request.form:
        return redirect('/homepage/alltask')
    elif "todaytask" in request.form:
        return redirect('/homepage/alltask')
    elif "alltasks" in request.form:
        return redirect('/homepage/totaltask')
    elif "notes" in request.form:
        return redirect('/homepage/notes')
    elif "projects" in request.form:
        return redirect('/homepage/project')
    elif "settings" in request.form:
        return redirect('/settings')
    elif 'logout' in request.form:
        session.clear()

        return redirect('/')
    elif "submit" in request.form:
        
        #ENTRIES
        task_name = request.form['task_name']
        if len(task_name) < 3:
            session['a']=9
            return redirect('/error')
              
        priority = request.form['priority']
        datetime_scheduled_str = request.form['datetime']
        #CONVERT
        datetime_scheduled = datetime.strptime(datetime_scheduled_str, '%Y-%m-%dT%H:%M')
        #GET ID OF THE USER
        username = session['username']
        user = User.query.filter_by(username=username).first()
        
        typeoftask = request.form['typeoftask']
        
        task = Task(priority=priority, taskname=task_name, datetime_scheduled=datetime_scheduled, typeoftask=typeoftask)
        
        user.tasks.append(task)
        db.session.commit()

        return redirect('/homepage/alltask')
    else:
        LenTotalTask=session['LenTotalTask']
        return render_template('createtask.html',
                               current_date=datetime.now().strftime("%B %d, %Y"),
                               today_day=datetime.now().day, 
                               usr=session['username'],
                               Total_tasks=LenTotalTask,
                               bg_img=session['bg_img'])


#when task is done 
@app.route('/homepage/alltask/<int:task_id>/markdone', methods=['POST','GET'])
def markdone(task_id):
    task = Task.query.get(task_id)
    task.done = 1
    db.session.commit()
    return redirect('/homepage/alltask#done')


@app.route('/homepage/totaltask/<int:task_id>/markdone', methods=['POST','GET'])
def Markdonetotaltask(task_id):
    task = Task.query.get(task_id)
    task.done = 1
    db.session.commit()
    return redirect('/homepage/totaltask')


#projectpage
@app.route('/homepage/project', methods=['GET', 'POST'])
def project():

    db.create_all()
    bg_img=session['bg_img']
    username = session['username']
    user = User.query.filter_by(username=username).first()
    projects = user.projects
    session['current_url'] = request.url
    #chat_messages = Chat.query.filter_by(project_id=project_id).all()
    
    if "submitt" in request.form:
        
        username2 = request.form['user2']
        username3 = request.form['user3']
        if len(username2) == 0 or len(username3) ==0:
            session['a'] = 11
            return redirect('/error')
        
        user2 = User.query.filter_by(username=username2).first()
        user3 = User.query.filter_by(username=username3).first()

        if user2 and user3 :

            
            proname = request.form['pro_name']
            descrip = request.form['descrip']
            
            if len(proname) < 4:
                session['a'] = 10
                return redirect('/error')
        
            
            new_project = Project(name=proname, description=descrip)
            
            new_project.users.append(user)
            new_project.users.append(user2)
            new_project.users.append(user3)
            
            db.session.add(new_project)
            db.session.commit()
            
            return render_template('project.html',
                                   current_date=datetime.now().strftime("%B %d, %Y"),
                                   usr=session['username'],
                                   Total_tasks=session['LenTotalTask'],
                                   projects=projects,bg_img=bg_img)
        else:
            session['a'] = 5
            return redirect('/error')
        
    if request.args.get('currenttasks') == 'currenttasks':
        return redirect('/homepage/alltask')
    elif request.args.get('todaytask') == 'todaytask':
        return redirect('/homepage/alltask')
    elif request.args.get('alltasks') == 'alltasks':
        return redirect('/homepage/totaltask')
    elif request.args.get('notes') == 'notes':
        return redirect('/homepage/notes')
    elif request.args.get('projects') == 'projects':
        return redirect('/homepage/project')
    elif request.args.get('settings') == 'settings':
        return redirect('/settings')
    elif request.args.get('logout') == 'logout':
        return redirect('/logout')
    return render_template('project.html',
                           current_date=datetime.now().strftime("%B %d, %Y"),
                           usr=session['username'],
                           Total_tasks=session['LenTotalTask'],
                           projects=projects,bg_img=bg_img)


#addnotes
@app.route('/homepage/notes', methods=['GET', 'POST'])
def notes():
    
    username = session['username']
    user = User.query.filter_by(username=username).first()
    notesss = Notes.query.filter_by(user_id=user.id).order_by(Notes.datetaken).all()
    TotalNotes = Notes.query.filter_by(user_id=user.id).all()
    LenTotalNotes = len(TotalNotes)
    session['LenTotalNotes'] = LenTotalNotes
    session['current_url'] = request.url
    
    if request.args.get('currenttasks') == 'currenttasks':
        return redirect('/homepage/alltask')
    elif request.args.get('todaytask') == 'todaytask':
        return redirect('/homepage/alltask')
    elif request.args.get('alltasks') == 'alltasks':
        return redirect('/homepage/totaltask')
    elif request.args.get('notes') == 'notes':
        return redirect('/homepage/notes')
    elif request.args.get('projects') == 'projects':
        return redirect('/homepage/project')
    elif request.args.get('settings') == 'settings':
        return redirect('/settings')
    elif request.args.get('logout') == 'logout':
        return redirect('/logout')
    elif 'submitnotes' in request.form :   
        db.create_all()
        title = request.form['title_name'];
        if len(title) < 3:
            session['a'] = 12
            return redirect('/error')
        else:    
            note = request.form['notes']    
            datetaken_str = datetime.now().strftime("%B %d, %Y %H:%M:%S")
            datetaken = datetime.strptime(datetaken_str, "%B %d, %Y %H:%M:%S")
            username = session['username']
            user = User.query.filter_by(username=username).first()
            new_note = Notes(title=title, note=note, datetaken=datetaken)
            user.notes.append(new_note)
            db.session.commit()
            return redirect('/homepage/notes')
           
           
           
             
    return render_template('notes.html',
                           current_date=datetime.now().strftime("%B %d, %Y"),
                           usr=session['username'],
                           LenTotalNotes=session['LenTotalNotes'],
                           notesss=notesss,
                           bg_img=session['bg_img'])


@app.route('/homepage/totaltask', methods=['GET', 'POST'])
def TTASKS():
   
    if request.args.get('currenttasks') == 'currenttasks':
        return redirect('/homepage/alltask')
    elif request.args.get('todaytask') == 'todaytask':
        return redirect('/homepage/alltask')
    elif request.args.get('alltasks') == 'alltasks':
        return redirect('/homepage/totaltask')
    elif request.args.get('notes') == 'notes':
        return redirect('/homepage/notes')
    elif request.args.get('projects') == 'projects':
        return redirect('/homepage/project')
    elif request.args.get('settings') == 'settings':
        return redirect('/settings')
    elif request.args.get('logout') == 'logout':
        return redirect('/logout')

    user = User.query.filter_by(username=session['username']).first()
    tasks = Task.query.filter_by(user_id=user.id, done=0).order_by(Task.datetime_scheduled, Task.priority).all()
    rtasks = Task.query.filter_by(user_id=user.id, done=1).order_by(Task.datetime_scheduled, Task.priority).all() 
    
    return render_template('Totaltask.html',tasks=tasks,
                           rtasks=rtasks,
                           current_date=datetime.now().strftime("%B %d, %Y"),
                           usr=session['username'],
                           Total_tasks=session['LenTotalTask'],
                           bg_img=session['bg_img'])

#update-page ig
@app.route('/homepage/totaltask/<int:task_id>/update',methods=['GET','POST'])
def updatetask(task_id):
    
    username = session['username']
    user = User.query.filter_by(username=username).first()   
    task = Task.query.filter_by(id=task_id,user_id=user.id).first()
    session['current_url'] = request.url
    
    if 'submitt' in request.form :
        username = session['username']
        user = User.query.filter_by(username=username).first()
        task = Task.query.filter_by(id=task_id,user_id=user.id).first()
        
        if len(request.form['task_name']) < 3 :
            session['a'] = 9
            return redirect('/error')
        else:                
            task.taskname = request.form['task_name']
            task.priority = request.form['priority']
            datetime_scheduled_str = request.form['datetime']
            datetime_scheduled = datetime.strptime(datetime_scheduled_str, '%Y-%m-%dT%H:%M')
            task.datetime_scheduled = datetime_scheduled
            task.typeoftask = request.form['typeoftask']
            db.session.commit()
            return redirect('/homepage/totaltask')
        
    elif "currenttasks" in request.form:
        return redirect('/homepage/alltask')
    elif "todaytask" in request.form:
        return redirect('/homepage/alltask')
    elif "alltasks" in request.form:
        return redirect('/homepage/totaltask')
    elif "notes" in request.form:
        return redirect('/homepage/notes')
    elif "projects" in request.form:
        return redirect('/homepage/project')
    elif "settings" in request.form:
        return redirect('/settings')
    elif "logout" in request.form:
        return redirect('/logout')
    elif 'delete' in request.form :
        db.session.delete(task)
        db.session.commit()
        return redirect('/homepage/alltask')
    return render_template('updatetask.html',
                           current_date=datetime.now().strftime("%B %d, %Y"),
                           task_name=task.taskname,
                           priority=task.priority,
                           usr=session['username'],
                           Total_tasks=session['LenTotalTask'],
                           bg_img=session['bg_img'])
    

@app.route('/homepage/alltask/<int:task_id>/update',methods=['GET','POST'])
def UpdatetaskAllTask(task_id):
    
    username = session['username']
    user = User.query.filter_by(username=username).first()   
    task = Task.query.filter_by(id=task_id,user_id=user.id).first()
    session['current_url'] = request.url
    
    if 'submitt' in request.form :
        username = session['username']
        user = User.query.filter_by(username=username).first()
        task = Task.query.filter_by(id=task_id,user_id=user.id).first()
        
        if len(request.form['task_name']) < 3 :
            session['a'] = 9
            return redirect('/error')
        else:
            task.taskname = request.form['task_name']
            task.priority = request.form['priority']
            datetime_scheduled_str = request.form['datetime']
            datetime_scheduled = datetime.strptime(datetime_scheduled_str, '%Y-%m-%dT%H:%M')
            task.datetime_scheduled = datetime_scheduled
            task.typeoftask = request.form['typeoftask']
            db.session.commit()
            return redirect('/homepage/alltask')
        
    elif "currenttasks" in request.form:
        return redirect('/homepage/alltask')
    elif "todaytask" in request.form:
        return redirect('/homepage/alltask')
    elif "alltasks" in request.form:
        return redirect('/homepage/totaltask')
    elif "notes" in request.form:
        return redirect('/homepage/notes')
    elif "settings" in request.form:
        return redirect('/settings')
    elif "projects" in request.form:
        return redirect('/homepage/project')
    elif "logout" in request.form:
        return redirect('/logout')
    elif 'delete' in request.form :
        db.session.delete(task)
        db.session.commit()
        return redirect('/homepage/alltask')
    return render_template('updatetask.html',
                           current_date=datetime.now().strftime("%B %d, %Y"),
                           task_name=task.taskname,
                           priority=task.priority,
                           usr=session['username'],
                           Total_tasks=session['LenTotalTask'],
                           bg_img=session['bg_img'])


#update block for notes
@app.route('/homepage/notes/<int:notes_id>/update',methods=['GET','POST'])
def UpdateNotes(notes_id):
    
    username = session['username']
    user = User.query.filter_by(username=username).first()   
    notess = Notes.query.filter_by(id=notes_id,user_id=user.id).first()
    session['current_url'] = request.url
    
    if request.args.get('currenttasks') == 'currenttasks':
        return redirect('/homepage/alltask')
    elif request.args.get('todaytask') == 'todaytask':
        return redirect('/homepage/alltask')
    elif request.args.get('alltasks') == 'alltasks':
        return redirect('/homepage/totaltask')
    elif request.args.get('notes') == 'notes':
        return redirect('/homepage/notes')
    elif request.args.get('projects') == 'projects':
        return redirect('/homepage/project')
    elif request.args.get('settings') == 'settings':
        return redirect('/settings')
    elif request.args.get('logout') == 'logout':
        return redirect('/logout')
    
    if 'updatenotes' in request.form:
        notess.note = request.form['notes']
        
        if len(request.form['title_name']) < 3:
            session['a'] = 12
            return redirect('/error')
        else:
            notess.title = request.form['title_name']
            db.session.commit()
            return redirect('/homepage/notes')
    
    if 'deletenotes' in request.form:
        db.session.delete(notess)
        db.session.commit()
        return redirect('/homepage/notes')
    
    return render_template('UpdateNotes.html',
                           current_date=datetime.now().strftime("%B %d, %Y"),
                           usr=username,
                           notes=notess.note,
                           title=notess.title,
                           LenTotalNotes=session['LenTotalNotes'],
                           bg_img=session['bg_img'])


@app.route('/homepage/projects/<int:project_id>/more',methods=['GET','POST'])
def abt_project(project_id):
    
    username = session['username']
    user = User.query.filter_by(username=username).first()
    project = Project.query.get(project_id)
    
    session['current_url'] = request.url
    
    pro_name = project.name
    pro_descrip = project.description
    pro_created_date = project.created_date
    users = project.users
    chats = Chat.query.filter_by(project_id=project_id).order_by(Chat.sent_date.desc()).all()
    
    
    if "submitt" in request.form:
        sendmsg=request.form['sendmsg']
        if sendmsg == "":
            return redirect(request.url)
        else:
            msg = Chat(user_id=user.id, project_id = project_id, message=sendmsg)
            db.session.add(msg)
            db.session.commit()
            return redirect(request.url)
    
    if "currenttasks" in request.form:
        return redirect('/homepage/alltask')
    elif "todaytask" in request.form:
        return redirect('/homepage/alltask')
    elif "alltasks" in request.form:
        return redirect('/homepage/totaltask')
    elif "notes" in request.form:
        return redirect('/homepage/notes')
    elif "projects" in request.form:
        return redirect('/homepage/project')
    elif "settings" in request.form:
        return redirect('/settings')
    elif 'logout' in request.form:
        return redirect('/logout')
    
    
    return render_template('abt_project.html',
                           current_date=datetime.now().strftime("%B %d, %Y"),
                           usr=username,
                           chats=chats,
                           pro_name=pro_name,
                           users=users,
                           pro_descrip=pro_descrip,
                           pro_created_date=pro_created_date,
                           bg_img=session['bg_img'])


@app.route('/settings',methods=['GET','POST'])
def Settings():

    username = session['username']
    user = User.query.filter_by(username=username).first()
    
    TotalNotes = Notes.query.filter_by(user_id=user.id).all()
    LenTotalNotes = len(TotalNotes)
    session['LenTotalNotes'] = LenTotalNotes
    TotalTask = Task.query.filter_by(user_id=user.id).all()
    LenTotalTask = len(TotalTask)
    session['LenTotalTask'] = LenTotalTask
   
    if "currenttasks" in request.form:
        return redirect('/homepage/alltask')
    elif "settings" in request.form:
        return redirect('/settings')
    elif "todaytask" in request.form:
        return redirect('/homepage/alltask')
    elif "alltasks" in request.form:
        return redirect('/homepage/totaltask')
    elif "notes" in request.form:
        return redirect('/homepage/notes')
    elif "projects" in request.form:
        return redirect('/homepage/project')
    elif 'verifybutton' in request.form:
        
        session.pop('otp', None)
    
        if 'otp' not in session:
            otp = str(random.randint(1000, 9999))
            session['otp'] = otp
            print("verify block\n\n")
            
            username = session['username']
            user = User.query.filter_by(username=username).first()
            userphonenumber = user.phoneno
            otp = str(random.randint(1000, 9999))
            session['otp'] = otp
            
            print(otp)
            
            message = f'\n\nYour OTP for the ToDo App is : {otp}. Your OTP is valid for 5 mins'
            message = client.messages.create(to=f'+{userphonenumber}', from_='+16073884159', body=message)
            
        return redirect('/verification')
    
    
    elif "themesubmit" in request.form:
        ch_bgcolor = request.form['bgcolor']
        if  ch_bgcolor == "1":
            session['bg_img'] = 'Light.png'
        elif ch_bgcolor == "2":
            session['bg_img'] = 'Paper.png'
        elif ch_bgcolor == "3":
            session['bg_img'] = 'Material.png'
        elif ch_bgcolor == "4":
            session['bg_img'] = 'SolidPurple.png'
        elif ch_bgcolor == "5":
            session['bg_img'] = 'SolidGrey.png'
        elif ch_bgcolor == "6":
            session['bg_img'] = 'Ocean.png'
        return redirect('/settings')
    elif 'logout' in request.form:
        return redirect('/logout')
    if "chsubmit" in request.form:
        change_up = request.form['change_up']
        if  change_up == "1":
            return redirect('/settings/resestpass/oldpass')
        elif change_up == "2":
            return redirect('/settings/resestpass/UniqueCode')
        elif change_up == "3":
            return redirect('/settings/resestusername/withpass')
    

    return render_template('settings.html',usr=username,u_key=user.u_key,
                           tasks_assn = session['LenTotalTask'],
                           notes_assn = session['LenTotalNotes'],
                           bg_img=session['bg_img'],
                           phoneno= user.phoneno,
                           user_verify= user.verified)




#VERIFICATION PAGE
@app.route('/verification',methods=['GET','POST'])
def verification():
    
    otp=session['otp']
    username = session['username']
    user = User.query.filter_by(username=username).first()

    notification.notify(
        title = 'OTP Sent',
        message = 'Successfully Sent OTP to yout phone number',
        app_name = 'ToDo',
        app_icon = 'app_icons/ToDo2.ico',
    )
    
    
    if "submitverify" in request.form and otp != request.form['otp']:
        print("here\n\n")
        notification.notify(
            title = 'Incorrect OTP',
            message = 'OTP submitted is incorrect',
            app_name = 'ToDo',
            app_icon = 'app_icons/ToDo2.ico',
        )
        return redirect('/settings')
    
    elif "submitverify" in request.form and otp == request.form['otp']:
        
        user.verified = 1
        db.session.commit()
        
        notification.notify(
            title = 'Successfully Verified',
            message = 'Successfully Verified your phone number',
            app_name = 'ToDo',
            app_icon = 'app_icons/ToDo2.ico',
        )
        t = threading.Thread(target=start_task_scheduler, args=(session['username'],))
        t.start()     
        return redirect('/settings')
    
    else:
        return render_template('verify.html')




@app.route('/settings/<string:usr>/clearall',methods=['GET','POST'])
def ClearAll(usr):
    
    user = User.query.filter_by(username=usr).first()
    tasks = Task.query.filter_by(user_id=user.id).all()
    notes = Notes.query.filter_by(user_id=user.id).all()
    for task in tasks:
        db.session.delete(task)
    for note in notes:
        db.session.delete(note)
    db.session.commit()

    session['LenTotalTask']=0
    session['LentotalNotes']=0
    
    return redirect('/settings')




@app.route('/settings/resestusername/withpass',methods=['GET','POST'])
def resetusername():
    
    session['current_url'] = request.url
    
    if 'pass-submit' in request.form:
        user_name = request.form['username']
        password = request.form['password']
        user1 = request.form['user1']
        user2 = request.form['user2']
        user_db = User.query.filter_by(username=user_name).first()
        
        if user_db and password == user_db.password and user1 == user2:
            user_db.username = user1
            session['username'] = user1
            db.session.commit()
            return redirect('/settings')
        else:
            session['a'] = 12
            return redirect('/error')
        
    elif 'settings' in request.form:
        return redirect ('/settings')
    
    return render_template('ResetUsername.html')




@app.route('/settings/resestpass/oldpass',methods=['GET','POST'])
def resetpass1():
    
    session['current_url'] = request.url
    
    if 'pass-submit' in request.form:
        user_name = request.form['username']
        old_pass = request.form['oldpass']
        pass1 = request.form['pass1']
        pass2 = request.form['pass2']
        user_db = User.query.filter_by(username=user_name).first()
        
        
        if len(user_name)<1 or len(old_pass)<1 or len(pass1)<1 or len(pass2)<1:
            session['a'] = 14
            return redirect('error')     
        if user_db and old_pass == user_db.password and pass1==pass2 and pass1 == user_db.password :
            session['a'] = 3
            return redirect('/error')
        if len(policy.test(request.form['pass1']))!=0:
            session['a'] = 6
            return redirect('/error')       
        elif user_db and old_pass == user_db.password and pass1==pass2 and len(policy.test(pass1)) == 0 :
            user_db.password = pass1
            db.session.commit()
            return redirect('/settings')  
        else:
            session['a'] = 1
            return redirect('/error')
              
    elif 'settings' in request.form:
        return redirect ('/settings')
    
    return render_template('Resetpass.html')
        
     
     
        
@app.route('/settings/resestpass/UniqueCode',methods=['GET','POST'])
def resetpass2():
    
    session['current_url'] = request.url
    
    if 'pass-submit' in request.form:
        user_name = request.form['username']
        u_code = request.form['u_code']
        pass1 = request.form['pass1']
        pass2 = request.form['pass2']
        user_db = User.query.filter_by(username=user_name).first()
       
        if len(user_name)<1 or len(u_code)<1 or len(pass1)<1 or len(pass2)<1:
            session['a'] = 14
            return redirect('error')      
        elif user_db and u_code == user_db.u_key and pass1==pass2 and pass1 == user_db.password:
            session['a'] = 3
            return redirect('/error')
        elif len(policy.test(pass1))!=0:
            session['a'] = 6
            return redirect('/error') 
        elif user_db and u_code == user_db.u_key and pass1==pass2  and len(policy.test(pass1))==0:
            user_db.password = pass1
            db.session.commit()
            return redirect('/settings')
        else:
            session['a']=13
            return redirect('/settings')
        
    elif 'settings' in request.form:
        return redirect ('/settings')
    
    return render_template('ResetpassUCode.html')




@app.route('/logout',methods=['GET','POST'])
def Logout():
    session.clear()
    notification.notify(
        title='Logged Out',
        message='Successfully Logged Out ',
        app_name='ToDo',
        app_icon='app_icons/ToDo2.ico',
    )
    return redirect('/') 



'''@celery.task
def send_reminder_sms(user_id):
    username = session['username']
    print(f"Username: {username}")
    user = User.query.filter_by(username=username).first()
    print(f"User: {user}")
    current_time = datetime.now()
    print(f"Current Time: {current_time}")
    pending_tasks = Task.query.filter(Task.datetime_scheduled <= current_time , user_id=user.id).all()
    print(f"Pending Tasks: {pending_tasks}")
    for task in pending_tasks:
        user = task.user
        phone_no = user.phoneno
        message = f'Reminder: {task.taskname} is scheduled for {task.datetime_scheduled}.'
        message = client.messages.create(to=f'+{phone_no}', from_='+16073884159', body=message)
        print(f"Message sent to phone number {phone_no}: {message}")'''

last_checked = None

def check_tasks(username):
    global last_checked
    
    with app.app_context():
        print("thread")
        user = User.query.filter_by(username=username).first()
        print(user)
        if not user:
            print("return reached")
            return
        current_time = datetime.now().replace(microsecond=0, second=0)
        current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S.000000')
        print(current_time_str)
        pending_tasks = Task.query.filter(Task.M_sent==0,Task.datetime_scheduled == current_time_str,Task.user_id==user.id).order_by(Task.datetime_scheduled.asc()).first()
        print(pending_tasks)
        if pending_tasks is not None: 
            print(pending_tasks.taskname)
            print(pending_tasks.datetime_scheduled)
            print("inside for loop")
            user = pending_tasks.user
            phone_no = user.phoneno
            
            notification.notify(
                title='Task Alert',
                message="Task About To Due",
                app_name='ToDo',
                app_icon='app_icons/ToDo2.ico',
            )
            
            message = '\n\n  :: Task About To Due ::      Reminder: ' +pending_tasks.taskname+ ' is scheduled for ' + str(pending_tasks.datetime_scheduled)
            message = client.messages.create(to=f'+{phone_no}', from_='+16073884159', body=message)
            pending_tasks.M_sent=1
            db.session.commit()
            
            print(f"Message sent to phone number {phone_no}: {message}")
        last_checked = current_time
        
        
        
        
        
def start_task_scheduler(username):
    global last_checked
    with app.app_context():
        while True:
            current_time = datetime.now().replace(microsecond=0, second=0)
            if last_checked is None or (current_time - last_checked).seconds >= 45:
                check_tasks(username)
                last_checked = current_time
            time.sleep(1)


'''@app.route('/homepage/excel',methods=['GET','POST'])
def''' 

'''API_KEY = '898d9bef9a1f804b571b35eb19b73092'

@app.route('/weather')
def weather():
    city = request.args.get('city')
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        temperature = data['main']['temp']
        description = data['weather'][0]['description']'''
     
'''prior=None
@app.route('/categories',methods=['GET','POST'])
def categories():

    if prior is None:
        prior="high"
    
    LenTaskDone = session['LenTaskDone']
    username = session['username']
    LenTotalTask = session['LenTotalTask']
    user = User.query.filter_by(username=username).first()
    
    if 'priorsubmit' in request.form :
        prior = session.form['prior']
    
    tasks = Task.query.filter_by(user_id=user.id,prioirty=prior).order_by(Task.datetime_scheduled).all()
    
    if "currenttasks" in request.form:
        return redirect('/homepage/alltask')
    elif "settings" in request.form:
        return redirect('/settings')
    elif "todaytask" in request.form:
        return redirect('/homepage/alltask')
    elif "alltasks" in request.form:
        return redirect('/homepage/totaltask')
    elif "notes" in request.form:
        return redirect('/homepage/notes')
    elif "projects" in request.form:
        return redirect('/homepage/project')
    
    
    return render_template('categories.html', 
                            today_day=datetime.now().day, 
                            usr=user,
                            Total_tasks=session['LenTotalTask'], 
                            tasks=tasks, 
                            LenTotalTask=LenTotalTask,
                            LenTaskDone=LenTaskDone, 
                            bg_img=session['bg_img'],
                            prior=prior)'''
     
     
   
if __name__ == '__main__':
    app.run(debug=True)
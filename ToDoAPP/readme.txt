1. Create virtual enivroment with terminal in the folder where project is stored :
'''
  Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
  ./env/Scripts/activate.ps1
'''

2. install all dependencies in virtual env

    >>> pip install flask 
    >>> pip install flask_sqlalchemy
    >>> pip install hashlib
    >>> pip install twilio.rest
    >>> pip install pandas
    >>> pip install plyer
    >>> pip install password_strength
  
 3. Create a twilio account which gives required auth and token
 
 4. Run "run.py" file and host it locally on "http://127.0.0.1:5000"

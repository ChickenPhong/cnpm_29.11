from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import quote

app = Flask(__name__)

app.secret_key = "k8HDLZbie2T8UWvC70S7f-SukGY"
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:%s@localhost/manadb?charset=utf8mb4" % quote("123456")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
# app.config["MIN_AGE"]=15
# app.config["MAX_AGE"]=20
# app.config["SI_SO"]=2

db = SQLAlchemy(app)
login = LoginManager(app=app)
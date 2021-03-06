import os
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)

import navi.views
import navi.models

if os.environ['ENV'] == 'dev':
	db.drop_all()
	db.create_all()
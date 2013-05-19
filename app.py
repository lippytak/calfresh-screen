import os
import pprint
import logging
import twilio.twiml
from sets import Set
from twilio.rest import TwilioRestClient
from flask import Flask, request, redirect, session
from flask.ext.sqlalchemy import SQLAlchemy
from flask import render_template
from database import init_db, db_session, Base, force_drop_all
#from programs import Calfresh, Medicaid, IHHS
from models import *

#setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
#db = SQLAlchemy(app)

#constants
data = {
	'5102068727':{
		'house_size':1,
		'kids':0,
		'senior_disabled':0,
		'income':100,
		'resources':100,
		},
	'5552068727':{
		'house_size':1,
		'kids':0,
		'senior_disabled':0,
		'income':100,
		'resources':100,
		},
}
programs = [Calfresh()]
question_texts = ["How many people live in your household?",
	"Are there any kids under 18 in your household?",
	"Is anyone in your household disabled or over the age of 60?",
	"What is the total monthly income of everyone in your household?",
	"What is the total savings (checking and savings accounts) of everyone in your household?"]

@app.before_first_request
def setup():
	#add users
	user1 = User('5102068727')
	user2 = User('5552068727')
	db_session.add(user1)
	db_session.add(user2)

	#add questions
	for text in question_texts:
		q = Question(text)
		db_session.add(q)

	#add programs
	program_subclasses = Program.__subclasses__()
	for c in program_subclasses:
		program = c()
		db_session.add(program)

	#add relationships


	db_session.commit()

# @app.route('/add-user')
# def addUser():
# 	name = request.args.get('name', None)
# 	email = request.args.get('email', None)
# 	u = User(name, email)
# 	db_session.add(u)
# 	db_session.commit()
# 	return str(name)

@app.teardown_request
def shutdown_session(exception=None):
	db_session.remove()

@app.route('/')
def index():
	users = User.query.all()
	return str(users)

def getEligiblePrograms(data):
	app.logger.info('Calculating eligibility for %s' % data)
	eligible_programs = []

	for p in programs:
		app.logger.info('Calculating eligibility for %s' % p)
		if p.calculateEligibility(data):
			eligible_programs.append(p)

	app.logger.info('Eligible for: %s' % eligible_programs)
	return eligible_programs

# #constants
# app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
# SECRET_KEY = 'a secret key'
# BASE_INCOME_THRESHOLD = 1484
# STD_RESOURCE_THRESHOLD = 2000
# SENIOR_RESOURCE_THRESHOLD = 3000

# #db
# required = Set(['house_size','kids','senior_disabled','income','resources'])
# questions = {
# 	'house_size':"How many people live in your household?",
# 	'kids' : "Are there any kids under 18 in your household?",
# 	'senior_disabled' : "Is anyone in your household disabled or over the age of 60?",
# 	'income' : "What is the total monthly income of everyone in your household?",
# 	'resources' : "What is the total savings (checking and savings accounts) of everyone in your household?"
# }

# households = {}
# #households[number][q_id] = answer to question

# @app.route('/')
# def index():
# 	from_number = request.values.get('From')
# 	body = request.values.get('Body')
# 	app.logger.warning('RECEIVED BODY: %s\nHOUSEHOLDS: %s' % (body, households))

# 	#server restarted > new session
# 	if from_number not in households:
# 		session['convo'] = None
# 		session['prev_qid'] = None

# 	#clear
# 	if body == 'Clear' or body == 'clear':
# 		session['convo'] = None
# 		session['prev_qid'] = None

# 	#new convo
# 	convo = session.get('convo', None)
# 	if not convo:
# 		app.logger.warning('STARTING NEW CONVO')
# 		session['convo'] = 1
# 		households[from_number] = {}
# 		qid = 'house_size'
# 		session['prev_qid'] = qid
# 		msg = questions[qid]
# 		return respond(msg)
	
# 	#existing convo
# 	elif convo:
# 		#add data
# 		prev_qid = session['prev_qid']
# 		households[from_number][prev_qid] = cleanValue(body)
# 		app.logger.warning('HOUSEHOLDS UPDATED: %s' % (households))

# 		#ask next missing question
# 		existing = Set(households[from_number].keys())
# 		missing = list(required - existing)
# 		app.logger.warning('REQUIRED - EXISTING = MISSING: %s - %s = %s' % (required, existing, missing))

# 		if missing:
# 			qid = missing.pop(0)
# 			session['prev_qid'] = qid
# 			msg = questions[qid]
# 			return respond(msg)

# 		#none missing - calculate eligibility
# 		elif not missing:
# 			elig = calcEligibility(**households[from_number])
# 			app.logger.warning('CALCULATING ELIGIBILITY: %s ==> %s' % (households, elig))
# 			if elig:
# 				msg = 'Looks like you might be eligible for CalFresh. You should try applying!'
# 			else:
# 				msg = str("Looks like you're probably not eligible for CalFresh.")
# 			return respond(msg)

# def cleanValue(val):
# 	if val.isdigit():
# 		return int(val)
# 	elif val[0] == 'Y' or val[0] == 'y':
# 		return 1
# 	elif val[0] == 'N' or val[0] == 'n':
# 		return 0

# def respond(msg):
# 	resp = twilio.twiml.Response()
# 	resp.sms(msg)
# 	return str(resp)

if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	force_drop_all()
	init_db()
	app.run(host='0.0.0.0', port=port, debug=os.environ['DEBUG'])
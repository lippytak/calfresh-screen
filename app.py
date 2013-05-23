import os
import pprint
import logging
import twilio.twiml
import json
import urllib2
import urllib
from questions import questions_data
from test_data import test_data
from sets import Set
from twilio.rest import TwilioRestClient
from flask import Flask, request, redirect, session, url_for
from flask.ext.sqlalchemy import SQLAlchemy
from flask import render_template
from database import init_db, db_session, Base, force_drop_all
from models import *

#setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']

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

@app.before_first_request
def setup():
	# load questions into DB
	yesnoquestions = questions_data['yesnoquestions']
	for q_data in yesnoquestions:
		key = q_data['key']
		order = q_data['order']
		question_text = q_data['question_text']
		q = YesNoQuestion(key=key, question_text=question_text, order=order, id=order)
		db_session.add(q)
	
	rangequestions = questions_data['rangequestions']
	for q_data in rangequestions:
		key = q_data['key']
		order = q_data['order']
		question_text = q_data['question_text']
		q = RangeQuestion(key=key, question_text=question_text, order=order, id=order)
		db_session.add(q)

	# load programs into DB
	program_subclasses = Program.__subclasses__()
	for c in program_subclasses:
		program = c()
		db_session.add(program)

	# load user test data into DB
	# user_data = test_data['users']
	# for u_data in user_data:
	# 	phone_number = u_data['phone_number']
	# 	u = User(phone_number=phone_number)
	# 	db_session.add(u)

	db_session.commit()

@app.teardown_request
def shutdown_session(exception=None):
	db_session.remove()

@app.route('/')
def index():
	questions = json.dumps(questions_data)
	return str(data)

def getEligiblePrograms(data):
	app.logger.info('Calculating eligibility for %s' % data)
	eligible_programs = []

	for p in programs:
		app.logger.info('Calculating eligibility for %s' % p)
		if p.calculateEligibility(data):
			eligible_programs.append(p)

	app.logger.info('Eligible for: %s' % eligible_programs)
	return eligible_programs

@app.route('/text')
def text():
	from_number = request.args.get('From')
	msg = request.args.get('Body')
	u = User.query.filter_by(phone_number=from_number).first()
	
	# new user - add to DB and send first Q
	if not u:
		app.logger.warning('Adding user to DB with phone number: %s' % from_number)
		u = User(phone_number=from_number)
		db_session.add(u)
		db_session.commit()

		q = Question.query.filter_by(order=0).first()
		sendQuestion(u, q)

	# existing user - parse response and send next Q if valid
	else:
		app.logger.warning('Found user %s' % u)
		last_question = u.last_question
		normalized_response = last_question.normalizeResponse(msg)
		
		# valid response, add answer to DB and ask next Q
		if normalized_response:
			app.logger.warning('Adding user %s answer to DB: %s' % (u, normalized_response))
			a = Answer(key=last_question.key, value=normalized_response, question=last_question)
			u.answers.append(a)
			db_session.add(a)
			db_session.add(u)
			db_session.commit()

			# get question with next highest order
			next_question = Question.query.filter(Question.order > last_question.order).order_by(Question.order).first()
			if next_question:
				sendQuestion(u, next_question)
			else:
				app.logger.warning('User %s finished all questions' % u)
				eligible_programs = calculateAndGetEligibility(u)
				return str(eligible_programs)
		
		# else invalid response, re-send question for now
		else:
			sendQuestion(u, last_question)
	
	return 'hi'

def sendQuestion(user, question):
	app.logger.warning('Sending user %s the question: %s' % (user, question))
	user.last_question = question
	db_session.add(user)
	db_session.commit()
	sendMessage(user.phone_number, question.question_text)

def sendMessage(phone_number, message):
	app.logger.warning('Sending phone %s the msg: %s' % (phone_number, message))
	account_sid = os.environ['ACCOUNT_SID']
	auth_token = os.environ['AUTH_TOKEN']
	client = TwilioRestClient(account_sid, auth_token)
	message = client.sms.messages.create(to=phone_number, from_="+14155346272",
                                     body=message)

def calculateAndGetEligibility(user):
	app.logger.warning('Calculating eligibility for %s' % user)
	programs = Program.query.all()
	data = getUserDataDict(user)
	for p in programs:
		if p.calculateEligibility(data):
			user.eligible_programs.append(p)
	db_session.add(user)
	db_session.commit()
	eligible_programs = user.eligible_programs
	app.logger.warning('Eligible programs for %s are: %s' % (user, eligible_programs))
	return eligible_programs

def getUserDataDict(user):
	app.logger.warning('Getting data dict for %s' % user)
	answers = user.answers
	data = {}
	for a in answers:
		data[a.key] = int(a.value)
	app.logger.warning('Data dict for %s is: %s' % (user, data))
	return data

if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	force_drop_all()
	init_db()
	app.run(host='0.0.0.0', port=port, debug=os.environ['DEBUG'])
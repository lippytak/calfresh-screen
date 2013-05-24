import os
import time
import pprint
import logging
import twilio.twiml
import json
from questions import questions_data
from test_data import test_data
from sets import Set
from twilio.rest import TwilioRestClient
from flask import Flask, request, redirect, session, url_for, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from database import init_db, db_session, Base, force_drop_all
from models import *

#setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']

#globals
question_set = []

@app.before_first_request
def setup():
	# load questions
	yesnoquestions = questions_data['yesnoquestions']
	for q_data in yesnoquestions:
		key = q_data['key']
		order = q_data['order']
		question_text = q_data['question_text']
		q = YesNoQuestion(key=key, question_text=question_text, order=order, id=order)
		question_set.append(q)
	
	rangequestions = questions_data['rangequestions']
	for q_data in rangequestions:
		key = q_data['key']
		order = q_data['order']
		question_text = q_data['question_text']
		q = RangeQuestion(key=key, question_text=question_text, order=order, id=order)
		question_set.append(q)

	# load programs
	program_subclasses = Program.__subclasses__()
	for c in program_subclasses:
		program = c()
		db_session.add(program)

	db_session.commit()

@app.teardown_request
def shutdown_session(exception=None):
	db_session.remove()

@app.route('/')
def index():
	return render_template('index.html')

@app.route('/text')
def text():
	from_number = request.args.get('From')
	msg = request.args.get('Body')
	user = User.query.filter_by(phone_number=from_number).first()
	
	#new user - add to DB and send first Q
	if not user:
		user = addAndGetNewUser(from_number)

		#send welcome msg and first question
		welcome_message = sendMessageTemplate(user, 'welcome.html')
		message = sendNextQuestion(user)
		return 'welcome:%s | first question: %s' % (welcome_message, message)

	#existing user - parse response and send next Q if valid
	else:
		app.logger.warning('Found user %s' % user)
		normalized_response = user.last_question.normalizeResponse(msg)
		
		# valid response, add answer to DB and ask next Q
		if normalized_response:
			addNewAnswer(user, normalized_response)

			# get question with next highest order
			next_question = user.getNextQuestion()
			if next_question:
				return sendQuestion(user, next_question)

			# no more questions, all done!
			else:
				app.logger.warning('User %s finished all questions' % user)
				eligible_programs = calculateAndGetEligibility(user)

				# respond with eligible programs
				if eligible_programs:
					context = {'eligible_programs':eligible_programs}
					message = sendMessageTemplate(user, 'eligible.html', **context)
					
					#respond with more program info
					for p in eligible_programs:
						template = str(p.name.lower()) + '.html'
						sendMessageTemplate(user, template)
					return message

				# no eligible programs
				else:
					return sendMessageTemplate(user, 'not-eligible.html')

		# invalid response, re-send question for now
		else:
			return sendQuestion(user, user.last_question)

def addNewAnswer(user, answer):
	app.logger.warning('Adding user %s answer to DB: %s' % (user, answer))
	user.last_question.answer = answer
	db_session.add(user)
	db_session.commit()

def addAndGetNewUser(phone_number):
	app.logger.warning('Adding user to DB with phone number: %s' % phone_number)
	user = User(phone_number=phone_number, questions=question_set)
	db_session.add(user)
	db_session.commit()
	return user

def sendNextQuestion(user):
	next_question = user.getNextQuestion()
	message = sendQuestion(user, next_question)
	return message

def sendQuestion(user, question):
	app.logger.warning('Sending user %s the question: %s' % (user, question))
	user.last_question = question
	db_session.add(user)
	db_session.commit()
	message = question.question_text
	sendMessage(user.phone_number, message)
	return message

def sendMessageTemplate(user, template, **kwargs):
	phone_number = user.phone_number
	app.logger.warning('Sending phone %s the template: %s' % (phone_number, template))
	
	context = {}
	for key, value in kwargs.iteritems():
		context[key] = value
	message = render_template(template, **context)
	sendMessage(phone_number, message)
	return message

def sendMessage(phone_number, message):
	app.logger.warning('Sending phone %s the msg: %s' % (phone_number, message))
	account_sid = os.environ['ACCOUNT_SID']
	auth_token = os.environ['AUTH_TOKEN']
	client = TwilioRestClient(account_sid, auth_token)
	client.sms.messages.create(to=phone_number, from_="+14155346272",
                                     body=message)
	time.sleep(2)

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
	questions = user.questions
	data = {}
	for q in questions:
		data[q.key] = int(q.answer)
	app.logger.warning('Data dict for %s is: %s' % (user, data))
	return data

if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	force_drop_all()
	init_db()
	app.run(host='0.0.0.0', port=port, debug=os.environ['DEBUG'])
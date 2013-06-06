import os
import time
import twilio.twiml
import json
import random
import collections
from questions import questions_data
from twilio.rest import TwilioRestClient
from flask import Flask, request, redirect, session, url_for, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from database import init_db, db_session, Base, force_drop_all
from models import *

#setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
env = os.environ['ENV']

@app.before_first_request
def setup():
	# load questions
	for indx, q in enumerate(questions_data):
		key = q['key']
		question_text = q['question_text']
		clarification_text = q['clarification_text']
		q_type = q['type']
		
		order = indx
		if q_type == 'yesnoquestion':
			q = YesNoQuestion(key=key, question_text=question_text, order=order, clarification_text=clarification_text)
		elif q_type == 'rangequestion':
			q = RangeQuestion(key=key, question_text=question_text, order=order, clarification_text=clarification_text)
		elif q_type == 'freeresponsequestion':
			q = FreeResponseQuestion(key=key, question_text=question_text, order=order, clarification_text=clarification_text)
		db_session.add(q)

	# load programs
	programs = [Calfresh(), Medical(), HealthySF(), FreeSchoolMeals(), CAP(), WIC()]
	for p in programs:
		db_session.add(p)
	
	#commit everything
	db_session.commit()

@app.teardown_request
def shutdown_session(exception=None):
	db_session.remove()

@app.route('/')
def index():
	data = collections.OrderedDict()
	programs = Program.query.all()
	users = User.query.all()

	#programs as keys
	for p in programs:
		data[p] = random.randint(10, 50)

	#add ref counts
	for u in users:
		for p in u.eligible_programs:
			data[p] = data[p.name] + 1

	#create two lists
	program_names = []
	elig_count = []
	for p, v in data.iteritems():
		program_names.append(str(p.name))
		elig_count.append(int(v))

	user_count = len(users) + random.randint(20, 50)
	match_count = random.randint(80, 120)

	return render_template('index.html', programs=program_names, data=elig_count, user_count=user_count, match_count = match_count)


@app.route('/text')
def text():
	# get info from twilio
	from_number = request.args.get('From')
	user = User.query.filter_by(phone_number=from_number).first()
	incoming_message = request.args.get('Body')

	#handle global text
	response = handleGlobalText(user, incoming_message)

	while True:
		#new user
		if not user:
			app.logger.info('ENTER STATE: NEW-USER')
			user = addAndGetNewUser(from_number)
			welcome_message = sendMessageTemplate(user, 'welcome.html')
			message = sendNextQuestion(user)
			user.state = 'ANSWERING-QUESTIONS'
			db_session.add(user)
			db_session.commit()
			return message

		elif user.state == 'ANSWERING-QUESTIONS':
			app.logger.info('ENTER STATE: ANSWERING-QUESTIONS')
			normalized_response = user.last_question.normalizeResponse(response)
			user.state = 'VALID-RESPONSE' if normalized_response else 'INVALID-RESPONSE'
			db_session.add(user)
			db_session.commit()
			
		elif user.state == 'VALID-RESPONSE':
			app.logger.info('ENTER STATE: VALID-RESPONSE')
			
			#log answer
			normalized_response = user.last_question.normalizeResponse(response)
			addNewAnswer(user, normalized_response)

			#next q
			next_question = sendNextQuestion(user)
			if next_question:
				user.state = 'ANSWERING-QUESTIONS'
				db_session.add(user)
				db_session.commit()
				return next_question
			else:
				user.state = 'DONE-WITH-QUESTIONS'
				db_session.add(user)
				db_session.commit()

		elif user.state == 'INVALID-RESPONSE':
			app.logger.info('ENTER STATE: INVALID-RESPONSE')
			user.state = 'ANSWERING-QUESTIONS'
			db_session.add(user)
			db_session.commit()
			return sendClarification(user, user.last_question)

		elif user.state == 'DONE-WITH-QUESTIONS':
			app.logger.info('DONE-WITH-QUESTIONS')
			#send eligibility info
			eligible_programs = calculateAndGetEligibility(user)
			user.state = 'ELIGIBLE' if eligible_programs else 'NOT-ELIGIBLE'
			db_session.add(user)
			db_session.commit()

		elif user.state == 'ELIGIBLE':
			app.logger.info('ENTER STATE: ELIGIBLE')
			eligible_programs_description = stringifyPrograms(eligible_programs)
			context = {'eligible_programs_description':eligible_programs_description}
			message = sendMessageTemplate(user, 'eligible.html', **context)
			user.state = 'FEEDBACK'
			db_session.add(user)
			db_session.commit()
			
			for p in eligible_programs:
				template = str(p.name.replace(' ', '').lower()) + '.html'
				sendMessageTemplate(user, template)
			return message

		elif user.state == 'NOT-ELIGIBLE':
			app.logger.info('ENTER STATE: NOT-ELIGIBLE')
			user.state = 'FEEDBACK'
			db_session.add(user)
			db_session.commit()
			return sendMessageTemplate(user, 'not-eligible.html')

		elif user.state == 'FEEDBACK':
			app.logger.info('ENTER STATE: FEEDBACK')
			return sendMessageTemplate(user, 'feedback.html')

	db_session.add(user)
	db_session.commit()

# utils

def handleGlobalText(user, response):
	app.logger.info('Handling incoming msg %s' % response)

	#new user
	if not user:
		return response

	#existing user
	response = response.strip().lower()
	if response == 'help':
		sendMessageTemplate(user, 'help.html')
	elif response == 'reset':
		db_session.delete(user)
		db_session.commit()
	return response

def stringifyPrograms(eligible_programs):
	#32 char max
	descrip_words = []

	count = len(eligible_programs)
	last = count - 1
	if count == 1:
		return eligible_programs[0].name
	
	for indx, p in enumerate(eligible_programs):
		if indx == last:
			descrip_words.append('and ')
			descrip_words.append(p.name)
		else:
			descrip_words.append(p.name)
			descrip_words.append(', ')

	descrip = ''.join(descrip_words)
	if len(descrip) > 30:
		return 'a few city services'
	else:
		return descrip

def getEligibilityTemplate(eligible_programs):
	context = {'eligible_programs':eligible_programs}
	if len(eligible_programs) == 1:
		return 'eligible-single.html'
	elif len(render_template('eligible.html', **context)) > 160:
		return 'eligible-multiple.html'
	else:
		return 'eligible.html'

def addNewAnswer(user, answer):
	app.logger.info('Adding ANSWER to DB: %s' % answer)
	user.last_question.answer = answer
	db_session.add(user)
	db_session.commit()

def addAndGetNewUser(phone_number):
	app.logger.info('Adding USER to DB with phone: %s' % phone_number)
	user = User(phone_number=phone_number, questions=question_set)
	db_session.add(user)
	db_session.commit()
	return user

def sendNextQuestion(user):
	next_question = user.getNextQuestion()
	if next_question:
		message = sendQuestion(user, next_question)
		return message
	else:
		user.finished = 1
		db_session.add(user)
		db_session.commit()
		return None

def sendQuestion(user, question):
	app.logger.info('Sending the question: %s' % question)
	user.last_question = question
	db_session.add(user)
	db_session.commit()
	message = question.question_text
	sendMessage(user, message)
	return message

def sendClarification(user, question):
	app.logger.info('Sending user %s question clarification: %s' % (user, question))
	db_session.add(user)
	db_session.commit()
	message = question.clarification_text
	if not message:
		message = question.question_text
	sendMessage(user, message)
	return message


def sendMessageTemplate(user, template, **kwargs):
	phone_number = user.phone_number
	app.logger.info('Sending phone %s the template: %s' % (phone_number, template))
	
	context = {}
	for key, value in kwargs.iteritems():
		context[key] = value
	message = render_template(template, **context)
	sendMessage(user, message)
	return message

def sendMessage(user, message):
	# twilio setup
	account_sid = os.environ['ACCOUNT_SID']
	auth_token = os.environ['AUTH_TOKEN']
	client = TwilioRestClient(account_sid, auth_token)
	phone_number = user.phone_number
	app.logger.info('Sending phone %s the msg: %s' % (phone_number, message))
	client.sms.messages.create(to=phone_number, from_="+14155346272",
                                     body=message)
	time.sleep(3)

def calculateAndGetEligibility(user):
	app.logger.info('Calculating eligibility for %s' % user)
	programs = Program.query.all()
	data = getUserDataDict(user)
	for p in programs:
		if p.calculateEligibility(data):
			user.eligible_programs.append(p)
	db_session.add(user)
	db_session.commit()
	eligible_programs = user.eligible_programs
	app.logger.info('Eligible programs are: %s' % eligible_programs)
	return eligible_programs

def getUserDataDict(user):
	app.logger.info('Getting data dict for %s' % user)
	questions = user.questions
	data = {}
	for q in questions:
		try:
			data[q.key] = int(q.answer)
		except ValueError:
			data[q.key] = q.answer
	app.logger.info('Data dict for is: %s' % data)
	return data

if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	#if env=='dev':
	app.logger.warning('DROPPING ALL DB TABLES')
	force_drop_all()
	init_db()
	app.run(host='0.0.0.0', port=port, debug=os.environ['DEBUG'])
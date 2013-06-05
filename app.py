import os
import time
import twilio.twiml
import json
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

#globals
question_set = []

@app.before_first_request
def setup():
	# load questions
	last = len(questions_data) - 1
	for indx, q in enumerate(questions_data):
		key = q['key']
		question_text = q['question_text']
		clarification_text = q['clarification_text']
		q_type = q['type']
		
		order = indx
		if indx == last:
			order = 99

		if q_type == 'yesnoquestion':
			q = YesNoQuestion(key=key, question_text=question_text, order=order, clarification_text=clarification_text)
		elif q_type == 'rangequestion':
			q = RangeQuestion(key=key, question_text=question_text, order=order, clarification_text=clarification_text)
		elif q_type == 'freeresponsequestion':
			q = FreeResponseQuestion(key=key, question_text=question_text, order=order, clarification_text=clarification_text)
		db_session.add(q)
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
			break
		
		elif user.state == 'ANSWERING-QUESTIONS':
			app.logger.info('ENTER STATE: ANSWERING-QUESTIONS')
			normalized_response = user.last_question.normalizeResponse(response)
			user.state = 'VALID-RESPONSE' if normalized_response else 'INVALID-RESPONSE'
			
		elif user.state == 'VALID-RESPONSE':
			app.logger.info('ENTER STATE: VALID-RESPONSE')
			#log answer
			addNewAnswer(user, normalized_response)

			#next q
			next_question = sendNextQuestion(user)
			if next_question:
				user.state = 'ANSWERING-QUESTIONS'
				return next_question
			else:
				user.state = 'DONE-WITH-QUESTIONS'

		elif user.state == 'INVALID-RESPONSE':
			app.logger.info('ENTER STATE: INVALID-RESPONSE')
			return sendClarification(user, user.last_question)

		elif user.state == 'DONE-WITH-QUESTIONS':
			app.logger.info('DONE-WITH-QUESTIONS')
			#send eligibility info
			eligible_programs = calculateAndGetEligibility(user)
			user.state = 'ELIGIBLE' if eligible_programs else 'NOT-ELIGIBLE'

		elif user.state == 'ELIGIBLE':
			app.logger.info('ENTER STATE: ELIGIBLE')
			eligible_programs_description = stringifyPrograms(eligible_programs)
			context = {'eligible_programs_description':eligible_programs_description}
			message = sendMessageTemplate(user, 'eligible.html', **context)
			user.state = 'FEEDBACK'
			
			for p in eligible_programs:
				template = str(p.name.replace(' ', '').lower()) + '.html'
				sendMessageTemplate(user, template)
			return message

		elif user.state == 'NOT-ELIGIBLE':
			app.logger.info('ENTER STATE: NOT-ELIGIBLE')
			user.state = 'FEEDBACK'
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
	app.logger.info('Adding user %s answer to DB: %s' % (user, answer))
	user.last_question.answer = answer
	db_session.add(user)
	db_session.commit()

def addAndGetNewUser(phone_number):
	app.logger.info('Adding user to DB with phone number: %s' % phone_number)
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
	app.logger.info('Sending user %s the question: %s' % (user, question))
	user.last_question = question
	user.state == 'answering-questions'
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
	app.logger.info('Eligible programs for %s are: %s' % (user, eligible_programs))
	return eligible_programs

def getUserDataDict(user):
	app.logger.info('Getting data dict for %s' % user)
	questions = user.questions
	data = {}
	for q in questions:
		data[q.key] = int(q.answer)
	app.logger.info('Data dict for %s is: %s' % (user, data))
	return data

if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	if env=='dev':
		app.logger.warning('DROPPING ALL DB TABLES')
		force_drop_all()
	init_db()
	app.run(host='0.0.0.0', port=port, debug=os.environ['DEBUG'])
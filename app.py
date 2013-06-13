import os
import time
import random
import collections
from twilio.rest import TwilioRestClient
from flask import Flask, request, redirect, session, url_for, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from database import init_db, db_session, force_drop_all
from seed import question_set
from models import *

#setup
app = Flask(__name__)

@app.teardown_request
def shutdown_session(exception=None):
	db_session.commit()
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
	incoming_message = request.args.get('Body')
	user = createOrGetUser(phone_number = from_number)

	#handle global text
	response = handleGlobalText(user, incoming_message)

	while True:
		if user.state == 'BEGIN':
			welcome_message = sendMessageTemplate(user, 'welcome.html')
			message = sendNextQuestion(user)
			user.state = 'ANSWERING-QUESTIONS'
			return message

		elif user.state == 'ANSWERING-QUESTIONS':
			app.logger.info('ENTER STATE: ANSWERING-QUESTIONS')
			normalized_response = user.last_question.normalizeResponse(response)
			user.state = 'VALID-RESPONSE' if normalized_response else 'INVALID-RESPONSE'
			
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
				return next_question
			else:
				user.state = 'DONE-WITH-QUESTIONS'

		elif user.state == 'INVALID-RESPONSE':
			app.logger.info('ENTER STATE: INVALID-RESPONSE')
			user.state = 'ANSWERING-QUESTIONS'
			db_session.add(user)
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
			db_session.add(user)
			
			for p in eligible_programs:
				template = str(p.name.replace(' ', '').lower()) + '.html'
				sendMessageTemplate(user, template)
			return message

		elif user.state == 'NOT-ELIGIBLE':
			app.logger.info('ENTER STATE: NOT-ELIGIBLE')
			user.state = 'FEEDBACK'
			db_session.add(user)
			return sendMessageTemplate(user, 'not-eligible.html')

		elif user.state == 'FEEDBACK':
			app.logger.info('ENTER STATE: FEEDBACK')
			return sendMessageTemplate(user, 'feedback.html')

		else:
			return 'user not in a recognized state'

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
	elif response == 'reset' or response == 'restart':
		user.state = ''
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

def createOrGetUser(phone_number):
	app.logger.info('Adding USER to DB with phone: %s' % phone_number)
	user = User(phone_number=phone_number, questions=question_set)
	db_session.add(user)
	return user

def sendNextQuestion(user):
	next_question = user.getNextQuestion()
	if next_question:
		message = sendQuestion(user, next_question)
		return message
	else:
		user.finished = 1
		db_session.add(user)
		return None

def sendQuestion(user, question):
	app.logger.info('Sending the question: %s' % question)
	user.last_question = question
	db_session.add(user)
	message = question.question_text
	sendMessage(user, message)
	return message

def sendClarification(user, question):
	app.logger.info('Sending user %s question clarification: %s' % (user, question))
	db_session.add(user)
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
	app.logger.warning('DROPPING ALL DB TABLES')
	#force_drop_all()
	init_db()
	app.run(host='0.0.0.0', port=port, debug=os.environ['DEBUG'])
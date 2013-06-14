from navi import app, db
import time
import os
from models import *
from question_data import question_data
from flask import render_template
from twilio.rest import TwilioRestClient

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
		db.session.delete(user)
		db.session.commit()
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
	db.session.add(user)

def createOrGetUser(phone_number):
	found_user = User.query.filter_by(phone_number = phone_number).first()
	if found_user:
		app.logger.info('Found user: %s' % found_user)
		return found_user
	else:
		app.logger.info('Adding USER to DB with phone: %s' % phone_number)
		questions = createQuestionSet()
		user = User(phone_number=phone_number, questions=questions)
		db.session.add(user)
		return user

def sendNextQuestion(user):
	next_question = user.getNextQuestion()
	if next_question:
		message = sendQuestion(user, next_question)
		return message
	else:
		user.finished = 1
		db.session.add(user)
		return None

def sendQuestion(user, question):
	app.logger.info('Sending the question: %s' % question)
	user.last_question = question
	db.session.add(user)
	message = question.question_text
	sendMessage(user, message)
	return message

def sendClarification(user, question):
	app.logger.info('Sending user %s question clarification: %s' % (user, question))
	db.session.add(user)
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
	programs = createProgramSet()
	data = getUserDataDict(user)
	for p in programs:
		if p.calculateEligibility(data):
			user.eligible_programs.append(p)
	db.session.add(user)
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

def createQuestionSet():
	question_set = []
	for indx, q in enumerate(question_data):
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
		question_set.append(q)
		db.session.add(q)
	return question_set

def createProgramSet():
	classes = [cls for cls in globals()['Program'].__subclasses__()]
	return [c() for c in classes]
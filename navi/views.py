from navi import app
import collections
import random
from utils import *
from flask import request, render_template

@app.teardown_request
def shutdown_session(exception=None):
	db.session.commit()
	db.session.remove()

@app.route('/')
def dashboard():
	data = collections.OrderedDict()
	programs = createProgramSet()
	for p in programs:
		data[p] = random.randint(10, 50)

	#create two lists
	program_names = []
	elig_count = []	
	for p, v in data.iteritems():
		program_names.append(str(p.name))
		elig_count.append(int(v))

	user_count = random.randint(20, 50)
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
			app.logger.info('ENTER STATE: BEGIN')
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
				db.session.add(user)
				return next_question
			else:
				user.state = 'DONE-WITH-QUESTIONS'

		elif user.state == 'INVALID-RESPONSE':
			app.logger.info('ENTER STATE: INVALID-RESPONSE')
			user.state = 'ANSWERING-QUESTIONS'
			db.session.add(user)
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
			db.session.add(user)
			
			for p in eligible_programs:
				template = str(p.name.replace(' ', '').lower()) + '.html'
				sendMessageTemplate(user, template)
			return message

		elif user.state == 'NOT-ELIGIBLE':
			app.logger.info('ENTER STATE: NOT-ELIGIBLE')
			user.state = 'FEEDBACK'
			db.session.add(user)
			return sendMessageTemplate(user, 'not-eligible.html')

		elif user.state == 'FEEDBACK':
			app.logger.info('ENTER STATE: FEEDBACK')
			return sendMessageTemplate(user, 'feedback.html')

		else:
			return 'user not in a recognized state'
import os
import pprint
import logging
import twilio.twiml
from program import *
from sets import Set
from twilio.rest import TwilioRestClient
from flask import Flask, request, redirect, session
from test_data import *

#setup
app = Flask(__name__)

#constants
programs = [Calfresh(), Medicaid()]
data = {
	'house_size':1,
	'kids':0,
	'senior_disabled':0,
	'income':100,
	'resources':100,
}

@app.route('/')
def index():
	eligible_programs = []

	for p in programs:
		if p.calculateEligibility(data):
			eligible_programs.append(p)

	return 'Data: %s, Eligibility: %s' % (data, eligible_programs)

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

# def calcEligibility(house_size, kids, senior_disabled, income, resources):
# 	income_threshold = calcIncomeThreshold(house_size)
# 	resource_threshold = calcResourceThreshold(kids, senior_disabled)
# 	print 'income threshold: %s' % income_threshold
# 	print 'resource threshold: %s' % resource_threshold
# 	if income <= income_threshold and resources <= resource_threshold:
# 		return True
# 	return False

# def calcResourceThreshold(kids, senior_disabled):
# 	if kids > 0:
# 		return float("inf")
# 	elif kids == 0 and senior_disabled > 0:
# 		return SENIOR_RESOURCE_THRESHOLD
# 	elif kids == 0 and senior_disabled == 0:
# 		return STD_RESOURCE_THRESHOLD

# def calcIncomeThreshold(house_size):
# 	return BASE_INCOME_THRESHOLD + ((house_size-1) * 377)

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
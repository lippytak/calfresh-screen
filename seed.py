from database import db_session
from models import *
from questions import questions_data

question_set = []
def load_seed_data():
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
		question_set.append(q)
		db_session.add(q)

	# load programs
	programs = [Calfresh(), Medical(), HealthySF(), FreeSchoolMeals(), CAP(), WIC()]
	for p in programs:
		db_session.add(p)

	# commit seed data
	db_session.commit()
	db_session.remove()
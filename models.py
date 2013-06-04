from sqlalchemy import Table, Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship, backref
from database import Base
import datetime

user_programs = Table('user_programs_association', Base.metadata,
	Column('users_id', Integer, ForeignKey('users.id')),
	Column('programs_id', Integer, ForeignKey('programs.id'))
)

user_questions = Table('user_questions_association', Base.metadata,
	Column('users_id', Integer, ForeignKey('users.id')),
	Column('question_id', Integer, ForeignKey('questions.id'))
)

program_questions = Table('program_questions_association', Base.metadata,
	Column('program_id', Integer, ForeignKey('programs.id')),
	Column('question_id', Integer, ForeignKey('questions.id'))
)

class User(Base):
	__tablename__ = 'users'
	id = Column(Integer, primary_key=True)
	phone_number = Column(String(50), unique=True)
	state = Column(String(50))
	
	last_question_id = Column(Integer, ForeignKey('questions.id'))
	last_question = relationship('Question')

	questions = relationship('Question',
							secondary=user_questions,
							backref='questions')
	
	eligible_programs = relationship('Program',
							secondary=user_programs,
							backref='programs')

	def __init__(self, phone_number, questions):
		self.phone_number = phone_number
		self.questions = questions
		self.state = 'answering-questions'

	def __repr__(self):
		return '<User phone: %r last_question: %r>' % (
			self.phone_number,
			self.last_question_id)

	def getNextQuestion(self):
		last_question_order = self.last_question.order if self.last_question else -1
		future_questions = sorted([q for q in self.questions if q.order > last_question_order], key=lambda question: question.order)
		next_question = future_questions[0] if future_questions else None
		return next_question

	def reset(self):
		self.questions = []
		self.state == 'reset'
		self.last_question = None

class Question(Base):
	__tablename__ = 'questions'
	id = Column(Integer, primary_key=True)
	key = Column(String(160))
	question_text = Column(String(160))
	clarification_text = Column(String(160))
	
	answer = Column(Integer)
	order = Column(Integer)
	discriminator = Column('type', String(50))

	__mapper_args__ = {'polymorphic_on': discriminator}

	def __init__(self, key, question_text, id=None, clarification_text=None, order=None):
		self.key = key
		self.question_text = question_text
		self.clarification_text = clarification_text
		self.order = order

	def __repr__(self):
		return '<Question: %r (%r)>' % (self.key, self.order)

	def normalizeResponse(self, response):
		raise NotImplementedError("Should have implemented this")

class YesNoQuestion(Question):
	__tablename__ = 'yesnoquestions'
	id = Column(Integer, ForeignKey('questions.id'), primary_key=True)

	__mapper_args__ = {'polymorphic_identity': 'yesnoquestions'}

	def normalizeResponse(self, response):
		response = response.strip().lower()
		if response.isdigit():
			return response
		elif response[0] == 'y':
			return 1
		elif response[0] == 'n':
			return -1
		else:
			return False

class RangeQuestion(Question):
	__tablename__ = 'rangequestions'
	id = Column(Integer, ForeignKey('questions.id'), primary_key=True)
	answer_min = Column(Integer)
	answer_max = Column(Integer)

	__mapper_args__ = {'polymorphic_identity': 'rangequestions'}

	def normalizeResponse(self, response):
		response = response.strip().replace(',', '').lower()
		if response.isdigit():
			response = int(round(float(response)))
			return response
		else:
			if response=='none' or response=='zero':
				return -1
		return False

class FreeResponseQuestion(Question):
	__tablename__ = 'freeresponsequestions'
	id = Column(Integer, ForeignKey('questions.id'), primary_key=True)

	__mapper_args__ = {'polymorphic_identity': 'freeresponsequestions'}

	def normalizeResponse(self, response):
		return True

# program classes
class Program(Base):
	__tablename__ = 'programs'
	id = Column(Integer, primary_key=True)
	name = description = Column(String(50), unique=True)
	discriminator = Column('type', String(50))

	__mapper_args__ = {'polymorphic_on': discriminator}
	
	# required_questions = relationship('Question',
	# 						secondary=program_questions)

	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return '<Program: %r>' % (self.name)

	def calculateEligibility(self):
		raise NotImplementedError("Should have implemented this")

class Calfresh(Program):
	__tablename__ = 'calfresh'
	id = Column(Integer, ForeignKey('programs.id'), primary_key=True)
	__mapper_args__ = {'polymorphic_identity': 'calfresh'}

	BASE_INCOME_THRESHOLD = 1484

	def __init__(self):
		self.name = 'CalFresh'

	def calculateEligibility(self, data):
		house_size = data['house_size']
		monthly_income = data['monthly_income']
		income_threshold = self.calcIncomeThreshold(house_size)
		if monthly_income <= income_threshold:
			return True
		return False

	def calcIncomeThreshold(self, house_size):
		return self.BASE_INCOME_THRESHOLD + ((house_size-1) * 377)

class Medical(Program):
	__tablename__ = 'medicaid'
	id = Column(Integer, ForeignKey('programs.id'), primary_key=True)
	__mapper_args__ = {'polymorphic_identity': 'medicaid'}

	def __init__(self):
		self.name = 'Medi-Cal'

	def calculateEligibility(self, data):
		annual_income = data['monthly_income'] * 12
		health_insurance = data['health_insurance']
		house_size = data['house_size']
		income_threshold = FPL(house_size) * 1.33
		
		if annual_income <= income_threshold and health_insurance == -1:
			return True
		else:
			return False

class FreeSchoolMeals(Program):
	__tablename__ = 'freeschoolmeals'
	id = Column(Integer, ForeignKey('programs.id'), primary_key=True)
	__mapper_args__ = {'polymorphic_identity': 'freeschoolmeals'}

	def __init__(self):
		self.name = 'Free School Meals'

	def calculateEligibility(self, data):
		annual_income = data['monthly_income'] * 12
		house_size = data['house_size']
		kid_school = data['kid_school']
		income_threshold = FPL(house_size) * 1.85
		if kid_school == 1 and annual_income <= income_threshold:
			return True
		return False

class IHHS(Program):
	__tablename__ = 'ihhs'
	id = Column(Integer, ForeignKey('programs.id'), primary_key=True)
	__mapper_args__ = {'polymorphic_identity': 'ihhs'}

	def __init__(self):
		self.name = 'IHHS'

	def calculateEligibility(self, data):
		senior_disabled_care = data['senior_disabled_care']

		if senior_disabled_care == 1:
			return True
		else:
			return False

def FPL(household_size):
	household_size = int(household_size)
	FPL = {
		1:11490,
		2:15510,
		3:19530,
		4:23550,
		5:27570,
		6:31590,
		7:35610,
		8:39630
		}
	if household_size <= 8:
		return FPL[household_size]
	else:
		return FPL[household_size] + (4020 * household_size-8)
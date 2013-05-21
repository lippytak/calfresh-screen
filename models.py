from sqlalchemy import Table, Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship, backref
from database import Base

user_programs = Table('user_programs_association', Base.metadata,
	Column('users_id', Integer, ForeignKey('users.id')),
	Column('programs_id', Integer, ForeignKey('programs.id'))
)

user_answers = Table('user_answers_association', Base.metadata,
	Column('users_id', Integer, ForeignKey('users.id')),
	Column('answers_id', Integer, ForeignKey('answers.id'))
)

program_questions = Table('program_questions_association', Base.metadata,
	Column('program_id', Integer, ForeignKey('programs.id')),
	Column('question_id', Integer, ForeignKey('questions.id'))
)

class User(Base):
	__tablename__ = 'users'
	id = Column(Integer, primary_key=True)
	phone_number = Column(String(50), unique=True)
	last_question_id = Column(Integer, ForeignKey('questions.id'))
	last_question = relationship('Question')
	
	eligible_programs = relationship('Program',
							secondary=user_programs,
							backref='programs')

	answers = relationship('Answer',
							secondary=user_answers,
							backref='answers')

	def __init__(self, phone_number=None):
		self.phone_number = phone_number

	def __repr__(self):
		return 'User phone: %r last_question: %r eligible_programs: %r answers: %r' % (
			self.phone_number,
			self.last_question_id,
			self.eligible_programs,
			self.answers)

# question classes
class Question(Base):
	__tablename__ = 'questions'
	id = Column(Integer, primary_key=True)
	question_text = Column(String(50), unique=True)
	clarification_text = Column(String(50), unique=True)
	order = Column(Integer)
	discriminator = Column('type', String(50))

	__mapper_args__ = {'polymorphic_on': discriminator}

	def __init__(self, question_text, clarification_text=None, order=None):
		self.question_text = question_text
		self.clarification_text = clarification_text
		self.order = order

	def __repr__(self):
		return 'Question: %r' % (self.question_text)

	def normalizeResponse(self, response):
		raise NotImplementedError("Should have implemented this")

class YesNoQuestion(Question):
	__tablename__ = 'yesnoquestions'
	id = Column(Integer, ForeignKey('questions.id'), primary_key=True)

	__mapper_args__ = {'polymorphic_identity': 'yesnoquestions'}

	def normalizeResponse(self, response):
		return False

class RangeQuestion(Question):
	__tablename__ = 'rangequestions'
	id = Column(Integer, ForeignKey('questions.id'), primary_key=True)
	answer_min = Column(Integer)
	answer_max = Column(Integer)

	__mapper_args__ = {'polymorphic_identity': 'rangequestions'}

	def __init__(self, question_text, clarification_text, order, answer_min, answer_max):
		self.question_text = question_text
		self.clarification_text = clarification_text
		self.order = order
		self.answer_min = answer_min
		self.answer_max = answer_max

	def normalizeResponse(self, response):
		return response

# answer classes
class Answer(Base):
	__tablename__ = 'answers'
	id = Column(Integer, primary_key=True)
	value = Column(String(50))
	question_id = Column(Integer, ForeignKey('questions.id'))
	question = relationship('Question')

	def __init__(self, value, question):
		self.value = value
		self.question = question

	def __repr__(self):
		return 'Answer: %r' % (self.value)

# program classes
class Program(Base):
	__tablename__ = 'programs'
	id = Column(Integer, primary_key=True)
	description = Column(String(50))
	discriminator = Column('type', String(50))

	__mapper_args__ = {'polymorphic_on': discriminator}
	
	required_questions = relationship('Question',
							secondary=program_questions,
							backref='questions')

	def __init__(self, description):
		self.description = description

	def __repr__(self):
		return 'Program: %r' % (self.description)

	def calculateEligibility(self):
		raise NotImplementedError("Should have implemented this")

class Calfresh(Program):
	__tablename__ = 'calfresh'
	id = Column(Integer, ForeignKey('programs.id'), primary_key=True)
	__mapper_args__ = {'polymorphic_identity': 'calfresh'}

	BASE_INCOME_THRESHOLD = 1484
	STD_RESOURCE_THRESHOLD = 2000
	SENIOR_RESOURCE_THRESHOLD = 3000

	def __init__(self):
		self.description = 'This is an instance of Calfresh program'

	def calculateEligibility(self, data):
		house_size = data['house_size']
		kids = data['kids']
		senior_disabled = data['senior_disabled']
		income = data['income']

		income_threshold = self.calcIncomeThreshold(house_size)
		resource_threshold = self.calcResourceThreshold(kids, senior_disabled)
		if income <= income_threshold and resources <= resource_threshold:
			return True
		return False

	def calcResourceThreshold(self, kids, senior_disabled):
		if kids > 0:
			return float("inf")
		elif kids == 0 and senior_disabled > 0:
			return self.SENIOR_RESOURCE_THRESHOLD
		elif kids == 0 and senior_disabled == 0:
			return self.STD_RESOURCE_THRESHOLD

	def calcIncomeThreshold(self, house_size):
		return self.BASE_INCOME_THRESHOLD + ((house_size-1) * 377)

class Medicaid(Program):
	__tablename__ = 'medicaid'
	id = Column(Integer, ForeignKey('programs.id'), primary_key=True)
	__mapper_args__ = {'polymorphic_identity': 'medicaid'}

	def __init__(self):
		self.description = 'This is an instance of Medicaid program'

	def calculateEligibility(self, data):
		return False
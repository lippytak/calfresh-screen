from sqlalchemy import Table, Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship, backref
from database import Base

user_programs = Table('user_programs_association', Base.metadata,
	Column('user_id', Integer, ForeignKey('users.id')),
	Column('program_id', Integer, ForeignKey('programs.id'))
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

	def __init__(self, phone_number=None):
		self.phone_number = phone_number

	def __repr__(self):
		return 'User %r' % (self.phone_number)

# question classes
class Question(Base):
	__tablename__ = 'questions'
	id = Column(Integer, primary_key=True)
	text = Column(String(50), unique=True)

	def __init__(self, text):
		self.text = text

	def __repr__(self, text):
		return 'Question: %r' % (self.text)

	def normalizeResponse(self, response):
		raise NotImplementedError("Should have implemented this")

# program classes
class Program(Base):
	__tablename__ = 'programs'
	id = Column(Integer, primary_key=True)
	name = Column(String(50), unique=True)
	required_questions = relationship('Question',
							secondary=program_questions,
							backref='questions')

	def __init__(self, name):
		self.name = name

	def __repr__(self, name):
		return 'Program: %r' % (self.name)

	def calculateEligibility(self):
		raise NotImplementedError("Should have implemented this")

class Calfresh(Program):
	BASE_INCOME_THRESHOLD = 1484
	STD_RESOURCE_THRESHOLD = 2000
	SENIOR_RESOURCE_THRESHOLD = 3000

	def __init__(self):
		self.name = 'Calfresh'

	def calculateEligibility(self, data):
		house_size = data['house_size']
		kids = data['kids']
		senior_disabled = data['senior_disabled']
		income = data['income']
		resources = data['resources']

		income_threshold = calcIncomeThreshold(house_size)
		resource_threshold = calcResourceThreshold(kids, senior_disabled)
		print 'income threshold: %s' % income_threshold
		print 'resource threshold: %s' % resource_threshold
		if income <= income_threshold and resources <= resource_threshold:
			return True
		return False

	def calcResourceThreshold(self, kids, senior_disabled):
		if kids > 0:
			return float("inf")
		elif kids == 0 and senior_disabled > 0:
			return SENIOR_RESOURCE_THRESHOLD
		elif kids == 0 and senior_disabled == 0:
			return STD_RESOURCE_THRESHOLD

	def calcIncomeThreshold(self, house_size):
		return BASE_INCOME_THRESHOLD + ((house_size-1) * 377)

class Medicaid(Program):
	def __init__(self):
		self.name = 'Medicaid'

	def calculateEligibility(self, data):
		return True

class IHHS(Program):
	def __init__(self):
		self.name = 'IHHS'

	def calculateEligibility(self, data):
		return False
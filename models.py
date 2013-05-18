from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
	__tablename__ = 'users'
	id = Column(Integer, primary_key=True)
	phone_number = Column(String(50), unique=True)
	# properties = relationship('Property')

	def __init__(self, phone_number=None):
		self.phone_number = phone_number

	def __repr__(self):
		return 'User %r' % (self.phone_number)

# class Property(Base):
# 	__tablename__ = 'properties'
# 	id = Column(Integer, primary_key=True)
# 	user_id = Column(Integer, ForeignKey('users.id'))
# 	kind = Column(String(50), unique=False)
# 	value = Column(Integer, unique=False)

# 	def __init__(self, user_id=None, kind=None, value=None):
# 		self.user_id = user_id
# 		self.kind = kind
# 		self.value = value

# 	def __repr__(self):
# 		return 'Property %r, %r, %r' % (self.user_id, self.kind, self.value)
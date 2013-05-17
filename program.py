class Calfresh():
	
	def __init__(self):
		self.BASE_INCOME_THRESHOLD = 1484
		self.STD_RESOURCE_THRESHOLD = 2000
		self.SENIOR_RESOURCE_THRESHOLD = 3000

	def __str__(self):
		return 'Calfresh'

	def __repr__(self):
		return '<Calfresh>'

	def calculateEligibility(self, data):
		house_size = data['house_size']
		kids = data['kids']
		senior_disabled = data['senior_disabled']
		income = data['income']
		resources = data['resources']

		income_threshold = self.calcIncomeThreshold(house_size)
		resource_threshold = self.calcResourceThreshold(kids, senior_disabled)
		print 'income threshold: %s' % income_threshold
		print 'resource threshold: %s' % resource_threshold
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

class Medicaid():
	def calculateEligibility(self, data):
		return True

	def __str__(self):
		return 'Medicaid'

	def __repr__(self):
		return '<Medicaid>'

class IHHS():
	def calculateEligibility(self, data):
		return False

	def __str__(self):
		return 'IHHS'

	def __repr__(self):
		return '<IHHS>'
class Booster(object):
	def __init__(self, cards):
		super(Booster, self).__init__()
		self.cards = cards
		
	def pick(self, card):
		self.cards.remove(card)
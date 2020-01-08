class Booster(object):
	def __init__(self, cards):
		super(Booster, self).__init__()
		self.cards = cards
	
	def __str__(self):
		return self.cards.__str__()
		
	def __repr__(self):
		return self.cards.__repr__()

	def pick(self, card):
		if card in self.cards:
			self.cards.remove(card)
			return card
		else:
			return None
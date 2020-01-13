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

	def pick_by_position(self, position):
		print("position: {p}".format(p=position))
		print(len(self.cards))
		print(self.cards[position-1])
		if len(self.cards) < position:
			return None
		return self.cards.pop(position-1)
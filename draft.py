from enum import Enum
import random
from booster import Booster
import utils
import logging


# create logger with 'spam_application'
logger = logging.getLogger('draft')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('test.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


PickReturn = Enum('PickReturn', 'pick_error, in_progress, next_booster, finished')


class Draft:
	def __init__(self, players, card_list):
		self.cards = card_list
		self.players = players
		random.shuffle(self.players)
		self.state = {}
		self.decks = { player:[] for player in players }

	def pack_of(self, player_id):
		return self.state[player_id]

	def deck_of(self, player_id):
		return self.decks[player_id]

	def start(self, number_of_packs, cards_per_booster, cube=None):
		self.number_of_packs = number_of_packs
		self.cards_per_booster = cards_per_booster
		random.shuffle(self.cards)
		self.booster_number = 0
		self.open_boosters()
		return self.state

	def open_boosters(self):
		for player in self.players:
			card_list = [self.cards.pop() for _ in range(0,self.cards_per_booster)]
			self.state[player] = Booster(card_list)
		self.booster_number += 1
		logger.info("Opening pack {num}".format(num=self.booster_number))
		self.picked = []

	def get_pending_players(self):
		return (set(self.players).difference(set(self.picked)))

	def pick(self, player, card_name=None, position=None):
		if player not in self.picked:
			if card_name is not None:
				card = self.state[player].pick(card_name)
			elif position is not None:
				card = self.state[player].pick_by_position(position)
			else:
				logger.info("Both card_name and position are None")
				return PickReturn.pick_error
			logger.info("Player {p} picked {c}".format(p=player,c=card))
			if card is None:
				return PickReturn.pick_error
			self.decks[player].append(card)
			self.picked.append(player)
		if len(self.picked) == len(self.players):
			logger.info("all players picked")
			logger.info(self.players)
			logger.info(self.state[self.players[0]])
			if len(self.state[self.players[0]].cards) > 0:
				logger.info("pass booster")
				self.pass_boosters()
				return PickReturn.next_booster
			elif self.booster_number < self.number_of_packs:
				logger.info("open new booster")
				self.open_boosters()
				return PickReturn.next_booster
			else:
				logger.info("Draft finished")
				return PickReturn.finished
		return PickReturn.in_progress

	def pass_boosters(self):
		if self.booster_number % 2 == 0:
			last = self.state[self.players[-1]]
			for i in range(len(self.players)-1, 0, -1):
		  		self.state[self.players[i]] = self.state[self.players[i-1]]
			self.state[self.players[0]] = last
		else:
			last = self.state[self.players[0]]
			for i in range(0, len(self.players)-1):
  				self.state[self.players[i]] = self.state[self.players[i+1]]
			self.state[self.players[-1]] = last
		self.picked = []

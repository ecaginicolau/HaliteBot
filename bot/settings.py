"""
# Monitor parameters
# Hyperparameters for nemesis calculation
"""
# score increase with the number of ship, so SHIP_WEIGHT > 0
SHIP_WEIGHT = 1.0
# score increase with the number of planets, so PLANET_WEIGHT > 0
PLANET_WEIGHT = 3.0
# score decrease as the distance increase, so PROXIMITY_WEIGHT < 0
PROXIMITY_WEIGHT = -0.05

"""
# Manager parameters
"""
# Some global
# Don't calculate ratio before this nb
#MIN_SHIP_PER_PLANET = 2
MIN_SHIP_PER_PLANET = 3
# Max ratio of ship sent to the same planet, avoid all ship going to the same planet
MAX_RATIO_SHIP_PER_PLANET = 0.5
# Always try to have at least 1 ship attacking (if not alone?)
MIN_SHIP_ATTACKERS = 1
# Even if there are still some available planet, send a portion of the ship to attack
MAX_RATIO_SHIP_ATTACKERS = 0.25
# NB of docked ship per planet
MAX_NB_DOCKED_SHIP = 10
# Radius inside which an enemy must be for a drone to become a defender
DEFENDER_RADIUS = 10
# Special radius for miner to react faster
MINER_DEFENDER_RADIUS = 10
# If the turn takes more than this, just exit
MAX_TURN_DURATION = 1.8
# Arbitrary threshold after which we need to sort ship by distance
NB_SHIP_THRESHOLD = 130
# Should a miner stop miner to become a defender
MINER_CAN_DEFEND =  False
"""
# Drone parameters
"""
# Nb of turn the ship is set to defender mode
MAX_TURN_DEFENDER = 5

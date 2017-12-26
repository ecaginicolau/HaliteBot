import hlt
import logging
from collections import OrderedDict
game = hlt.Game("Rampa-V6")
logging.info("Starting Rampa Bot")
logger = logging.getLogger(__name__)

#Some global
#Max ratio of ship sent to the same planet, avoid all ship going to the same planet
MAX_RATIO_SHIP_PER_PLANET= 0.5
#Always try to have at least 1 ship attacking (if not alone?)
MIN_SHIP_ATTACKERS = 1
#Even if there are still some available planet, send a portion of the ship to attack
MAX_RATIO_SHIP_ATTACKERS = 0.25
#NB of docked ship per planet
MAX_NB_DOCKED_SHIP = 5

#Store all the ships that are dedicated to the attacks between MIN_SHIP_ATTACKERS and MAX_RATIO_SHIP_ATTACKERS
ship_attackers = {}
#Store all ship that are dedicated to conquest, between MAX_RATIO_SHIP_ATTACKERS and (100%  -  MIN_SHIP_ATTACKERS)
ship_conquerors = {}
#Store new ship that has never been seen before (to allocate between attack & conquest)
new_ship =[]
try:
    while True:
        logger.debug("In new turn loop")
        game_map = game.update_map()
        command_queue = []

        #Count nb of owned planets:
        all_planets = game_map.all_planets()
        team_planets = []
        for planet in all_planets:
            #TODO check if planets is mine!
            if (planet.is_owned()) and (planet.owner.id == game_map.get_me().id):
                team_planets.append(planet)
        nb_owned_planets = len(team_planets)
        logger.info("OWN %s planets" % nb_owned_planets)

        #All the ship available this turn
        team_ships = game_map.get_me().all_ships()
        team_ships_dict =  {}
        for ship in team_ships:
            team_ships_dict[ship.id] = ship

        nb_attackers_died = 0
        #Check if attackers are still alive
        for ship_id in list(ship_attackers.keys()):
            dead = False
            try:
                ship = team_ships_dict[ship_id]
                if ship.health <= 0 or ship not in team_ships:
                    dead = True
            # The attacker is lost
            except KeyError:
                dead = True
            except:
                logger.exeception("Can't find ship ?")
            if dead:
                logger.debug("Attacker died")
                nb_attackers_died+=1
                del ship_attackers[ship_id]

        nb_conquerors_died = 0
        #Check if attackers are still alive
        for ship_id in list(ship_conquerors.keys()):
            dead = False
            try:
                ship = team_ships_dict[ship_id]
                if ship.health <= 0 or ship not in team_ships:
                    dead = True
            # The conquero is lost
            except KeyError:
                dead = True
            except:
                logger.exeception("Can't find ship ?")
            if dead:
                logger.debug("Conqueror died")
                nb_conquerors_died+=1
                del ship_conquerors[ship_id]

        #Now check for new ships
        for ship in team_ships:
            #Don't use docked ship at all!
            if ship.docking_status != ship.DockingStatus.UNDOCKED:
                # Skip this ship
                continue
            found = False
            try:
                t = ship_attackers[ship.id]
                found = True
            except:
                pass
            try:
                t = ship_conquerors[ship.id]
                found = True
            except:
                pass
            if not found:
                logger.info("New ship, need to allocate it")
                new_ship.append(ship)

        logger.info("Lost %s attackers & %s conquerors" %  (nb_attackers_died, nb_conquerors_died))
        logger.info("Found %s new ship" %  len(new_ship))
        #Split in two: Attackers & Conquerors

        #If there are not enough attackers, take some ship in the new ship list
        #TODO if there are not empty planet left, send all to attack
        nb_attackers = len(ship_attackers)
        current_ratio = nb_attackers / float(len(team_ships))
        logger.debug("nb_attackers: %s, current_ratio: %s" % (nb_attackers,current_ratio))
        while ((nb_attackers < MIN_SHIP_ATTACKERS) or (current_ratio < MAX_RATIO_SHIP_ATTACKERS)) and (len(new_ship)>0) :
            logger.info("Need new attackers")
            #TODO  look for the closest ship to an enemy
            #Take the first new ship
            ship = new_ship.pop()
            logger.debug("Take ship: %s " % ship.id)
            logger.debug("Removed from new_ship: %s " % ship.id)
            #Add to attackers
            ship_attackers[ship.id] = 1
            logger.debug("Added to attackers: %s " % ship.id)
            nb_attackers = len(ship_attackers)
            current_ratio = nb_attackers / float(len(team_ships))
            logger.debug("nb_attackers: %s, current_ratio: %s" % (nb_attackers,current_ratio))

        #Add all the other new_ship to conquerors
        for ship in new_ship:
            #Add to attackers
            ship_conquerors[ship.id] = 1

        #Reset new_ship
        new_ship = []

        #HANDLE all attackers
        for ship_id in ship_attackers:
            ship = team_ships_dict[ship_id]
            entities_by_distance = game_map.nearby_entities_by_distance(ship)
            entities_by_distance = OrderedDict(sorted(entities_by_distance.items(), key=lambda t: t[0]))
            closest_enemy_ships = []
            #Loop through all entities by distance check if they are an enemy, stop at the closest
            target_ship = None
            for distance in entities_by_distance:
                entity = entities_by_distance[distance][0]
                if isinstance(entity, hlt.entity.Ship) and not entity in team_ships:
                    target_ship = entity
                    break
            if target_ship is not None:
                navigate_command = ship.navigate(
                    ship.closest_point_to(target_ship),
                    game_map,
                    speed=int(hlt.constants.MAX_SPEED),
                    ignore_ships=False)
                if navigate_command:
                    command_queue.append(navigate_command)


        #HANDLE all conquerors
        nb_ship_per_planet = {}

        for ship_id in ship_conquerors:
            ship = team_ships_dict[ship_id]

            entities_by_distance = game_map.nearby_entities_by_distance(ship)
            entities_by_distance = OrderedDict(sorted(entities_by_distance.items(), key=lambda t: t[0]))

            closest_empty_planets = []
            closest_enemy_ships = []
            closest_planets = []
            #Loop through all entities by distance, separate in 2 list : empty planets & enemy ship
            for distance in entities_by_distance:

                entity = entities_by_distance[distance][0]
                if isinstance(entity, hlt.entity.Planet):
                    closest_planets.append(entity)
                if isinstance(entity, hlt.entity.Planet) and not entity.is_owned():
                    closest_empty_planets.append(entity)
                if isinstance(entity, hlt.entity.Ship) and not entity in team_ships:
                    closest_enemy_ships.append(entity)

            #If there are no empty planets: ATTACK
            if len(closest_empty_planets) == 0:
                target_ship = closest_enemy_ships[0]
                navigate_command = ship.navigate(
                            ship.closest_point_to(target_ship),
                            game_map,
                            speed=int(hlt.constants.MAX_SPEED),
                            ignore_ships=False)
                if navigate_command:
                    command_queue.append(navigate_command)
                continue

            #First, make sure the ship can dock
            if ship.can_dock(closest_empty_planets[0]):
                command_queue.append(ship.dock(closest_empty_planets[0]))
                continue


            #if less than NB_DOCKED_SHIP docked to the cloest planet, dock
            if ship.can_dock(closest_planets[0]):
                if len(closest_planets[0].all_docked_ships()) < min(MAX_NB_DOCKED_SHIP,nb_owned_planets):
                    command_queue.append(ship.dock(closest_planets[0]))
                    continue

            #If there is only 1 ship left, no need to coordinate them, go to the closest planet
            if len(ship_conquerors) == 1:
                navigate_command = ship.navigate(
                    ship.closest_point_to(target_planet),
                    game_map,
                    speed=int(hlt.constants.MAX_SPEED),
                    ignore_ships=False)
                if navigate_command:
                    command_queue.append(navigate_command)
                continue

            #Now, look for a suitable planet
            for target_planet in closest_empty_planets:
                try:
                    nb_ship_per_planet[target_planet]+=1
                except:
                    nb_ship_per_planet[target_planet] = 1

                #Only send a ship if there is less than half of the current ship going to this destination
                if nb_ship_per_planet[target_planet] > int(len(team_ships)*MAX_RATIO_SHIP_PER_PLANET):
                    logger.debug("Reroute the ship to another planet, too many ship already going there")
                    #This ship is not going there anymore, remove from the counter
                    nb_ship_per_planet[target_planet] -= 1
                    #Skip to next planet in the list
                    continue
                else:
                    navigate_command = ship.navigate(
                                ship.closest_point_to(target_planet),
                                game_map,
                                speed=int(hlt.constants.MAX_SPEED),
                                ignore_ships=False)
                    if navigate_command:
                        command_queue.append(navigate_command)
                    #Exit target planet loop
                    break

        game.send_command_queue(command_queue)
        # TURN END
    # GAME END
except:
    logger.exception("BIG CRASH")
from bot.settings import SHIP_INFLUENCE, PLANET_INFLUENCE, INFLUENCE_STEP, INFLUENCE_ZONE, INFLUENCE_THRESHOLD
from PIL import Image, ImageDraw
from collections import defaultdict
import os
from hlt.entity import Ship
import logging

class Influence(object):

    width = 0
    height = 0
    defense_img = None
    __circle_to_draw_dict = defaultdict(list)
    player_id = 0
    turn = 0
    planet_img = None
    game_map = None

    @staticmethod
    def init(player_id):
        # Store the player id, will be used to distinguish ships
        Influence.player_id = player_id

    @staticmethod
    def add_circle_position(entity, influence, free_planet = False):
        # By default empty planet have a very thin influence zone
        if free_planet:
            min_x = entity.pos.x - entity.pos.radius - influence * 2
            min_y = entity.pos.y - entity.pos.radius - influence * 2
            max_x = entity.pos.x + entity.pos.radius + influence * 2
            max_y = entity.pos.y + entity.pos.radius + influence * 2
            color = entity.id + 1
            Influence.__circle_to_draw_dict[color].append([min_x, min_y, max_x, max_y])
        else:
            # Other planets or ships have a gradient of influence zone
            for i in range(INFLUENCE_STEP):
                min_x = entity.pos.x - entity.pos.radius - influence * (INFLUENCE_STEP - i)
                min_y = entity.pos.y - entity.pos.radius - influence * (INFLUENCE_STEP - i)
                max_x = entity.pos.x + entity.pos.radius + influence * (INFLUENCE_STEP - i)
                max_y = entity.pos.y + entity.pos.radius + influence * (INFLUENCE_STEP - i)
                color = INFLUENCE_ZONE * (i + 1)
                Influence.__circle_to_draw_dict[color].append([min_x, min_y, max_x, max_y])

    @staticmethod
    def update_game_map(game_map):
        Influence.width = game_map.width
        Influence.height = game_map.height
        Influence.game_map = game_map

        Influence.draw_defense_zone()
        Influence.draw_free_planet_zone()
        Influence.turn += 1

    @staticmethod
    def draw_defense_zone():

        Influence.__circle_to_draw_dict = defaultdict(list)
        Influence.defense_img = Image.new('L', (Influence.width, Influence.height))
        draw = ImageDraw.Draw(Influence.defense_img)

        # Get the influence zone of every ships
        for ship in Influence.game_map.get_me().all_ships():
            # Draw a circle for every ship that is docked
            if ship.docking_status != Ship.DockingStatus.UNDOCKED:
                Influence.add_circle_position(ship, SHIP_INFLUENCE, free_planet=False)

        # Get the influence zone of every planets
        for planet in Influence.game_map.all_planets():
            # Make sure it's our planet
            if planet.is_owned() and planet.owner.id == Influence.player_id:
                Influence.add_circle_position(planet, PLANET_INFLUENCE, free_planet=False)

        # Now draw , ordered by color
        for color in sorted(Influence.__circle_to_draw_dict.keys()):
            for circle in Influence.__circle_to_draw_dict[color]:
                draw.ellipse(circle, fill=color, outline=color)

        try:
            if os.environ['RAMPA_LOG_LEVEL'] == "DEBUG":
                Influence.defense_img.save("influence\\defense\\defense_influence_%s.png" % Influence.turn)
        except KeyError:
            pass

    @staticmethod
    def draw_free_planet_zone():
        from .monitor import Monitor

        Influence.__circle_to_draw_dict = defaultdict(list)
        Influence.planet_img = Image.new('L', (Influence.width, Influence.height))
        draw = ImageDraw.Draw(Influence.planet_img)

        # Get the influence zone of every ships
        for planet_id, planet in Monitor.get_all_planets_dict().items():
            # Draw a circle for every planet that is free
            if (not planet.is_owned() or planet.owner.id == Influence.player_id) and Monitor.get_nb_spots_for_miners(planet_id) > 0:
                Influence.add_circle_position(planet, SHIP_INFLUENCE, free_planet=True)

        # Now draw , ordered by color
        for color in sorted(Influence.__circle_to_draw_dict.keys()):
            for circle in Influence.__circle_to_draw_dict[color]:
                draw.ellipse(circle, fill=color, outline=color)

        try:
            if os.environ['RAMPA_LOG_LEVEL'] == "DEBUG":
                Influence.planet_img.save("influence\\planet\\planet_influence_%s.png" % Influence.turn)
        except KeyError:
            pass

    @staticmethod
    def get_point_defense_influence(pos):
        """
        Return the influence value of a single position (Circle)
        :param pos:
        :return: and int between 0 and 255
        """
        return Influence.defense_img.getpixel((pos.x, pos.y))
        # return Influence.img.getpixel((int(pos.x), int(pos.y)))

    @staticmethod
    def get_point_planet_influence(pos):
        """
        Return the influence value of a single position (Circle)
        :param pos:
        :return: and int between 0 and 255
        """
        return Influence.planet_img.getpixel((pos.x, pos.y))
        # return Influence.img.getpixel((int(pos.x), int(pos.y)))

    @staticmethod
    def is_in_influence_zone(pos):
        """
        Check if a position is inside the influence zone
        :param pos:
        :return:
        """
        return Influence.get_point_defense_influence(pos) > INFLUENCE_THRESHOLD

    @staticmethod
    def is_in_planet_zone(pos):
        return Influence.get_point_planet_influence(pos) > 0

    @staticmethod
    def get_planet_influence(pos):
        return Influence.get_point_planet_influence(pos) - 1
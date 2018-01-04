from bot.navigation import Circle, calculate_distance_between, segment_intersect

#DEBUG:root:navigate(ship=Circle(123.80, 91.19, 0.50), target=Circle(122.45, 85.11, 0.00), game_map, speed=7.0, max_corrections=90, angular_spep=1.0, ignore_ships=False, ignore_planets=False, ignore_ghosts=False, assassin=False)


line1 = (Circle(0, 0), Circle(10, 10))
line2 = (Circle(0, 10), Circle(10, 10))
print(segment_intersect(line1[0], line1[1], line2[0], line2[1]))


exit()
ship = Circle(123.80, 91.19, 0.50)
print("ship:%s " % ship)
target=Circle(122.45, 85.11, 0.00)
print("target: %s" % target)




new_target = ship + target
print("new_target: %s" % new_target)
new_target = ship - target
print("new_target: %s" % new_target)

new_target = ship * 2
print("new_target: %s" % new_target)

new_target = ship * target
print("new_target: %s" % new_target)


distance = calculate_distance_between(ship, target)
print("distance: %s" % distance)


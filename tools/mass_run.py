import subprocess
import json

nb=0
win=0

for i in range(10000):

    cmd = """halite.exe -r -q -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py" """
    output = subprocess.check_output(cmd).decode("ascii")
    data =json.loads(output)
    nb +=1
    if data["stats"]["0"]["last_frame_alive"] >data["stats"]["1"]["last_frame_alive"]:
        win +=1

    percent = (win / float(nb)) * 100.0
    print("Played %s games, won %s, for %.2f%%" % (nb, win, percent))


